"""
Unified Consensus Module for Decentralized Bundle Auctions (Choi, Brunet, How 2009).
Shared across all auction variants (CBBA, CBBA-PR, CC-CBBA, CBBA-Gossip, ACA).
Guarantees strict compliance with Choi 2009 Table 1 conflict resolution rules,
including task release propagation (preventing orphan tasks) and convergence.
"""

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from ..agents.robot import RobotAgent
from ..env.comm import CommunicationNetwork, Message


def resolve_task_consensus(
    receiver_id: int,
    sender_id: int,
    tid: int,
    y_i: float,
    z_i: int,
    y_k: float,
    z_k: int,
    s_i: Dict[int, int],
    s_k: Dict[int, int],
) -> Tuple[float, int, bool]:
    """
    Apply Choi 2009 Table 1 consensus conflict resolution for a single task tid.
    Returns (new_y_i, new_z_i, changed).
    """
    # Helper for tie-breaking: strictly lowest agent ID wins equal bids
    def k_beats_i(bid_k: float, id_k: int, bid_i: float, id_i: int) -> bool:
        if bid_k > bid_i + 1e-9:
            return True
        elif abs(bid_k - bid_i) <= 1e-9 and id_k < id_i:
            return True
        return False

    def k_beats_m(bid_k: float, id_k: int, bid_m: float, id_m: int) -> bool:
        if bid_k > bid_m + 1e-9:
            return True
        elif abs(bid_k - bid_m) <= 1e-9 and id_k < id_m:
            return True
        return False

    # Case 1: Receiver believes receiver won (z_i == receiver_id)
    if z_i == receiver_id:
        if z_k == receiver_id:
            # Both agree receiver won
            new_y = max(y_i, y_k)
            return new_y, receiver_id, (new_y != y_i)
        elif z_k == sender_id:
            # Sender claims to have won: outbid check
            if k_beats_i(y_k, sender_id, y_i, receiver_id):
                return y_k, sender_id, True
            else:
                return y_i, receiver_id, False
        elif z_k != -1:
            # Sender claims third party m won
            m = z_k
            if s_k.get(m, 0) > s_i.get(m, 0) and k_beats_i(y_k, m, y_i, receiver_id):
                return y_k, m, True
            else:
                return y_i, receiver_id, False
        else: # z_k == -1 (sender says no winner)
            # Receiver keeps its valid win
            return y_i, receiver_id, False

    # Case 2: Receiver believes sender won (z_i == sender_id)
    elif z_i == sender_id:
        if z_k == sender_id:
            # Both agree sender won: update bid
            return y_k, sender_id, (y_k != y_i)
        elif z_k == receiver_id:
            # Conflicting cross-claims: reset
            return 0.0, -1, True
        elif z_k != -1:
            # Sender updated to third party m
            return y_k, z_k, True
        else: # z_k == -1 (SENDER RELEASED TASK - Choi 2009 Table 1 Rule 6 & 14)
            # Receiver must acknowledge release and reset
            return 0.0, -1, True

    # Case 3: Receiver believes third party m won (z_i == m, m not in {i, k})
    elif z_i != -1:
        m = z_i
        if z_k == m:
            # Both agree m won: update bid if sender has newer info on m
            if s_k.get(m, 0) > s_i.get(m, 0):
                return y_k, m, (y_k != y_i)
            return y_i, m, False
        elif z_k == sender_id:
            # Sender claims to have outbid m
            if k_beats_m(y_k, sender_id, y_i, m) or (s_k.get(m, 0) > s_i.get(m, 0)):
                return y_k, sender_id, True
            return y_i, m, False
        elif z_k == receiver_id:
            # Sender thinks receiver won, but receiver thought m won: reset
            if s_k.get(m, 0) > s_i.get(m, 0):
                return 0.0, -1, True
            return y_i, m, False
        elif z_k != -1: # z_k == m' (different third party)
            m_prime = z_k
            if k_beats_m(y_k, m_prime, y_i, m) or (s_k.get(m, 0) > s_i.get(m, 0)):
                return y_k, m_prime, True
            return y_i, m, False
        else: # z_k == -1 (sender says no winner)
            # If sender has strictly newer info about m, reset
            if s_k.get(m, 0) > s_i.get(m, 0):
                return 0.0, -1, True
            return y_i, m, False

    # Case 4: Receiver has no winner (z_i == -1)
    else:
        if z_k != -1:
            return y_k, z_k, True
        return 0.0, -1, False


def execute_consensus_exchange(
    fleet_ids: List[int],
    robots: Dict[int, RobotAgent],
    comm_net: CommunicationNetwork,
    y: Dict[int, Dict[int, float]],
    z: Dict[int, Dict[int, int]],
    s: Dict[int, Dict[int, int]],
    current_step: int,
    robot_positions: Dict[int, Tuple[float, float]],
    msg_type: str = "CBBA_CONSENSUS",
    extra_payload_fn: Optional[Any] = None,
    handle_extra_payload_fn: Optional[Any] = None,
) -> bool:
    """
    Execute one full consensus round (broadcast + conflict resolution).
    Shared by CBBA, CBBA-PR, CC-CBBA, CBBA-Gossip, and ACA.
    """
    # Step 1: Broadcast state tables (y, z, s)
    for rid in fleet_ids:
        s[rid][rid] = current_step
        payload = {
            "y": dict(y[rid]),
            "z": dict(z[rid]),
            "s": dict(s[rid]),
        }
        if extra_payload_fn is not None:
            extra = extra_payload_fn(rid)
            payload.update(extra)

        byte_size = 32 + len(y[rid]) * 16 + len(fleet_ids) * 4
        msg = Message(
            sender_id=rid,
            recipient_id=-1,
            msg_type=msg_type,
            payload=payload,
            timestamp=current_step,
            size_bytes=byte_size,
        )
        comm_net.send(msg, robot_positions)

    # Step 2: Receive messages and apply Choi 2009 resolution rules
    changed = False
    for rid in fleet_ids:
        inbox = comm_net.receive(rid)
        for msg in inbox:
            if msg.msg_type != msg_type or not isinstance(msg.payload, dict):
                continue
            sender_k = msg.sender_id
            k_data = msg.payload
            y_k = k_data.get("y", {})
            z_k = k_data.get("z", {})
            s_k = k_data.get("s", {})

            if handle_extra_payload_fn is not None:
                handle_extra_payload_fn(rid, sender_k, k_data)

            # Update recipient's timestamp vector
            for k_id, t_val in s_k.items():
                if t_val > s[rid].get(k_id, 0):
                    s[rid][k_id] = t_val

            all_tasks = set(y[rid].keys()).union(set(y_k.keys()))
            first_outbid_idx = -1

            for tid in all_tasks:
                y_i_j = y[rid].get(tid, 0.0)
                z_i_j = z[rid].get(tid, -1)
                y_k_j = y_k.get(tid, 0.0)
                z_k_j = z_k.get(tid, -1)

                new_y, new_z, task_changed = resolve_task_consensus(
                    receiver_id=rid,
                    sender_id=sender_k,
                    tid=tid,
                    y_i=y_i_j,
                    z_i=z_i_j,
                    y_k=y_k_j,
                    z_k=z_k_j,
                    s_i=s[rid],
                    s_k=s_k,
                )

                if task_changed:
                    y[rid][tid] = new_y
                    z[rid][tid] = new_z
                    changed = True

                    # If receiver was winner but lost the task, check bundle truncation
                    if z_i_j == rid and new_z != rid:
                        if tid in robots[rid].bundle:
                            idx = robots[rid].bundle.index(tid)
                            if first_outbid_idx == -1 or idx < first_outbid_idx:
                                first_outbid_idx = idx

            # Bundle truncation rule: if lost task at index idx, release all subsequent tasks
            if first_outbid_idx != -1:
                released = robots[rid].bundle[first_outbid_idx:]
                robots[rid].bundle = robots[rid].bundle[:first_outbid_idx]
                for r_tid in released:
                    if z[rid].get(r_tid) == rid:
                        z[rid][r_tid] = -1
                        y[rid][r_tid] = 0.0

    return changed
