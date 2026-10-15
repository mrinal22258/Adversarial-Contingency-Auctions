"""
Standardized Local Recourse Execution Layer (Phase A.4 & Protocol v6).
Shared execution module across ALL allocators (ACA, CBBA, SSI, CC-CBBA, etc.).
Maintains immutable RecourseTreeNode cursor ensuring priced branch == executed branch.
Guarantees identical physical kinematics, edge progression, and multi-depth contingency pivot logic.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from .robot import RobotAgent

from ..env.adversaries import canonical_edge
from ..env.blockage_process import PersistentBlockageProcess


class LocalRecourseExecutor:
    """
    Shared execution engine ensuring level execution capability across all algorithms.
    Supports depth d in {0, 1, 2}.
    - When d = 0 (published baselines): detours are disabled; blockage triggers immediate replan.
    - When d > 0 (+LR variants): tracks tree cursor; pivots to child branch on blockage; replans on exhaustion.
    """

    @staticmethod
    def step_execution(
        robot: "RobotAgent",
        blockage_process: PersistentBlockageProcess,
        tasks_dict: Dict[int, Any],
        dt: float = 1.0,
    ) -> None:
        """
        Execute one physical simulation step for robot.
        """
        if robot.active_task_id is None or robot.status in ("EXHAUSTED_NEEDS_REPLAN",):
            return

        if robot.status == "IDLE":
            robot.status = "TRANSIT"

        if robot.path_index >= len(robot.active_path) - 1:
            # Arrived at task destination!
            robot.completed_tasks.append(robot.active_task_id)
            if robot.active_task_id in robot.bundle:
                robot.bundle.remove(robot.active_task_id)
            if robot.active_task_id in robot.assigned_plans:
                del robot.assigned_plans[robot.active_task_id]

            robot.tree_cursor = None
            # Move to next task in bundle
            robot.plan_task_bundle(tasks_dict)
            return

        u = robot.active_path[robot.path_index]
        v = robot.active_path[robot.path_index + 1]
        c_e = canonical_edge(u, v)
        edge_weight = robot.graph[u][v].get("weight", 1.0)

        # Check if approaching edge is blocked right before traversal or at current node
        if robot.edge_progress == 0.0 and blockage_process.is_blocked(u, v):
            # Check for precomputed recourse detour if contingency_depth > 0
            if robot.contingency_depth > 0:
                current_plan = robot.assigned_plans.get(robot.active_task_id)
                if current_plan is not None:
                    # Retrieve active cursor in the recourse tree
                    cursor = getattr(robot, "tree_cursor", None) or current_plan.tree
                    if cursor is not None:
                        child_node = cursor.detours.get(c_e, cursor.detours.get((u, v)))
                        if child_node is not None and not child_node.is_recovery and len(child_node.path) >= 2:
                            d_u, d_v = child_node.path[0], child_node.path[1]
                            if not blockage_process.is_blocked(d_u, d_v):
                                # LOCAL RECOURSE PIVOT (Alg. 1): Follow priced branch
                                robot.tree_cursor = child_node
                                robot.active_path = list(child_node.path)
                                robot.path_index = 0
                                robot.edge_progress = 0.0
                                robot.status = "PIVOTED"
                                return
                            else:
                                # First edge of child branch is also blocked; check for deeper planned detour
                                cd_e = canonical_edge(d_u, d_v)
                                deeper_child = child_node.detours.get(cd_e, child_node.detours.get((d_u, d_v)))
                                if deeper_child is not None and not deeper_child.is_recovery and len(deeper_child.path) >= 2:
                                    dd_u, dd_v = deeper_child.path[0], deeper_child.path[1]
                                    if not blockage_process.is_blocked(dd_u, dd_v):
                                        # Deeper multi-depth branch pivot
                                        robot.tree_cursor = deeper_child
                                        robot.active_path = list(deeper_child.path)
                                        robot.path_index = 0
                                        robot.edge_progress = 0.0
                                        robot.status = "PIVOTED"
                                        return
                    else:
                        # Fallback for flat plans without tree object
                        detour = current_plan.detours.get((u, v), current_plan.detours.get(c_e))
                        if detour is not None and len(detour) >= 2:
                            d_u, d_v = detour[0], detour[1]
                            if not blockage_process.is_blocked(d_u, d_v):
                                robot.active_path = list(detour)
                                robot.path_index = 0
                                robot.edge_progress = 0.0
                                robot.status = "PIVOTED"
                                return

            # All recourse branches exhausted or contingency_depth == 0
            robot.tree_cursor = None
            robot.status = "EXHAUSTED_NEEDS_REPLAN"
            robot.replan_requests.append(robot.active_task_id)
            if robot.active_task_id in robot.bundle:
                robot.bundle.remove(robot.active_task_id)
            robot.active_task_id = None
            return

        # Advance along edge (u, v)
        travel_step = robot.speed * dt
        robot.edge_progress += travel_step

        pos_u = np.array(robot.graph.nodes[u].get("pos", (0, 0)))
        pos_v = np.array(robot.graph.nodes[v].get("pos", (0, 0)))

        if robot.edge_progress >= edge_weight:
            # Completed traversal of edge (u, v)
            robot.current_node = v
            robot.pos = (float(pos_v[0]), float(pos_v[1]))
            robot.path_index += 1
            robot.edge_progress = 0.0
        else:
            # Interpolate position along edge
            frac = robot.edge_progress / max(1e-5, edge_weight)
            interpolated = pos_u + frac * (pos_v - pos_u)
            robot.pos = (float(interpolated[0]), float(interpolated[1]))
            robot.status = "TRANSIT"
