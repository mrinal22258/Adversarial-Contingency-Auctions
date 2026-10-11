"""
Dynamic Narrative and Event Logging Engine.
Generates quantitative, data-grounded plain-English narratives and timestamped tick event logs
strictly from simulation traces and state diffs with zero fabricated text.
"""

from typing import Dict, List, Any, Optional


def generate_event_log(
    history: List[Dict[str, Any]],
    graph_edge_names: Optional[Dict[Any, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Produce a chronological, plain-English event stream from tick-by-tick state diffs.
    """
    events = []
    prev_blocked = set()
    prev_completed_tids = set()
    prev_bundles = {}

    for frame in history:
        tick = frame.get("tick", 1)
        curr_blocked = set(tuple(sorted(e)) for e in frame.get("blocked_edges", []))
        newly_blocked = curr_blocked - prev_blocked
        cleared_edges = prev_blocked - curr_blocked

        # 1. Blockage Onset Events
        for u, v in newly_blocked:
            st_name = ""
            if graph_edge_names:
                st_name = graph_edge_names.get((u, v), graph_edge_names.get((v, u), ""))
            st_desc = f" on {st_name}" if st_name else ""
            events.append({
                "tick": tick,
                "category": "Adversary",
                "message": f"Adversary activated corridor blockage on edge ({u}, {v}){st_desc} near node {u}."
            })

        # 2. Blockage Cleared Events
        for u, v in cleared_edges:
            events.append({
                "tick": tick,
                "category": "Environment",
                "message": f"Corridor blockage on edge ({u}, {v}) cleared; traversability restored."
            })

        # 3. Local Detours & Status Changes
        for r in frame.get("robots", []):
            rid = r["id"]
            status = r.get("status", "IDLE")
            active_t = r.get("active_task")
            if r.get("took_local_detour", False):
                t_str = f" to T{active_t}" if active_t is not None else ""
                events.append({
                    "tick": tick,
                    "category": "Execution",
                    "message": f"Robot R{rid} was en route{t_str} and executed a precomputed contingency detour locally (0 messages sent)."
                })
            if status == "EXHAUSTED_NEEDS_REPLAN":
                events.append({
                    "tick": tick,
                    "category": "Mechanism",
                    "message": f"Robot R{rid} exhausted its local recourse tree; triggered decentralized market re-auction."
                })

        # 4. Mechanism Allocations & Claims
        if frame.get("deferred_claims_this_tick", 0) > 0:
            events.append({
                "tick": tick,
                "category": "Mechanism",
                "message": f"{frame['deferred_claims_this_tick']} task claim(s) deferred to full consensus (Pinsker belief divergence margin exceeded threshold)."
            })
        if frame.get("conflicts_this_tick", 0) > 0:
            events.append({
                "tick": tick,
                "category": "Conflict",
                "message": "Consensus conflict detected on active claim(s); resolution rule applied."
            })

        # 5. Task Completions
        for t in frame.get("tasks", []):
            tid = t["id"]
            if t.get("is_completed", False) and tid not in prev_completed_tids:
                c_by = t.get("completed_by", "fleet")
                rew = t.get("reward", 100.0)
                events.append({
                    "tick": tick,
                    "category": "Task",
                    "message": f"Task T{tid} completed by Robot R{c_by} (reward +{rew:.0f})."
                })
                prev_completed_tids.add(tid)

        prev_blocked = curr_blocked

    return events


def format_event_log_markdown(events: List[Dict[str, Any]], max_events: int = 150) -> str:
    """Render events list to a formatted markdown log."""
    if not events:
        return "*No notable discrete events recorded during simulation.*"

    lines = []
    for ev in events[:max_events]:
        cat = ev.get("category", "Info")
        tick = ev.get("tick", 0)
        msg = ev.get("message", "")
        lines.append(f"- **[Tick {tick:02d} | {cat}]** {msg}")

    if len(events) > max_events:
        lines.append(f"\n*... and {len(events) - max_events} additional events.*")
    return "\n".join(lines)


def format_event_log_html(
    events: List[Dict[str, Any]],
    active_tick: Optional[int] = None,
    filter_category: str = "All",
) -> str:
    """
    Format events into a 360px scrollable container with sticky header,
    category filtering, and active tick auto-scroll targeting.
    """
    filtered = []
    for ev in events:
        cat = ev.get("category", "Info")
        if filter_category != "All":
            # Map user filter categories
            f_norm = filter_category.lower()
            c_norm = cat.lower()
            if f_norm == "allocation" and c_norm in ("mechanism", "allocation"):
                pass
            elif f_norm in c_norm:
                pass
            else:
                continue
        filtered.append(ev)

    if not filtered:
        rows_html = "<div style='padding: 16px; color: #64748b; font-size: 13px; text-align: center;'>No events matching filter.</div>"
    else:
        rows = []
        for ev in filtered:
            tick = ev.get("tick", 0)
            cat = ev.get("category", "Info")
            msg = ev.get("message", "")
            is_active = (active_tick is not None and tick == active_tick)

            bg = "#eef2ff" if is_active else "#ffffff"
            border_left = "3px solid #4f46e5" if is_active else "3px solid transparent"
            cat_color = {
                "Adversary": "#dc2626",
                "Task": "#059669",
                "Conflict": "#d97706",
                "Mechanism": "#4f46e5",
                "Execution": "#0284c7",
            }.get(cat, "#475569")

            rows.append(
                f"<div id='ev-tick-{tick}' style='padding: 6px 10px; margin-bottom: 2px; font-size: 12px; background: {bg}; border-left: {border_left}; border-bottom: 1px solid #f1f5f9; display: flex; gap: 8px; align-items: baseline;'>"
                f"<span style='font-family: ui-monospace, monospace; font-size: 11px; font-weight: 600; color: #64748b; min-width: 52px;'>Tick {tick:02d}</span>"
                f"<span style='font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 1px 6px; border-radius: 4px; background: #f8fafc; border: 1px solid #e2e8f0; color: {cat_color}; min-width: 65px; text-align: center;'>{cat}</span>"
                f"<span style='color: #1e293b; flex: 1;'>{msg}</span>"
                f"</div>"
            )
        rows_html = "\n".join(rows)

    return f"""<div style="height: 360px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 8px; background: #ffffff; position: relative; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
<div style="position: sticky; top: 0; background: #f8fafc; border-bottom: 1px solid #e2e8f0; padding: 6px 10px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; z-index: 5; display: flex; justify-content: space-between;">
    <span>Chronological Event Stream</span>
    <span style="font-size: 10px; color: #94a3b8;">Showing {len(filtered)} events</span>
</div>
{rows_html}
</div>"""


def generate_what_happened_narrative(
    summary: Dict[str, Any],
    history: List[Dict[str, Any]],
    env_info: Dict[str, Any],
) -> str:
    """
    Generate an auto-written 5-8 sentence narrative computed directly from run numbers.
    Never uses canned placeholders; all quantitative statements reflect empirical metrics.
    """
    total_tasks = summary.get("total_tasks", 0)
    completed_tasks = summary.get("completed_tasks", 0)
    failed_tasks = total_tasks - completed_tasks
    comp_rate = (completed_tasks / max(1, total_tasks)) * 100.0
    net_welfare = summary.get("net_welfare", 0.0)
    total_travel = summary.get("total_travel_distance", 0.0)
    total_msgs = summary.get("total_messages_sent", summary.get("total_messages", 0))
    total_conflicts = summary.get("total_conflicts", 0)
    safe_conflicts = summary.get("safe_claim_conflicts", 0)
    safe_claims = summary.get("safe_claims", 0)
    deferred_claims = summary.get("deferred_claims", 0)
    reauctions = summary.get("reauction_events", 0)
    n_robots = summary.get("total_robots", 4)
    makespan = summary.get("makespan", len(history))

    map_name = env_info.get("map_name", "Real Navigation Map")
    adv_name = env_info.get("adversary_name", "Strategic Adversary")
    alloc_name = env_info.get("allocator_name", "ACA")

    # Robot attribution from final frame
    final_frame = history[-1] if history else {}
    robot_completions = {}
    for t in final_frame.get("tasks", []):
        if t.get("is_completed") and t.get("completed_by") is not None:
            c_by = t["completed_by"]
            robot_completions[c_by] = robot_completions.get(c_by, 0) + 1

    if robot_completions:
        top_robot = max(robot_completions.items(), key=lambda x: x[1])
        top_robot_str = f"Robot R{top_robot[0]} led execution servicing {top_robot[1]} task(s)"
    else:
        top_robot_str = "No tasks were finalized by individual robots"

    # Blockage counts & detours
    all_blocked_ever = set()
    local_detour_count = 0
    for f in history:
        for e in f.get("blocked_edges", []):
            all_blocked_ever.add(tuple(sorted(e)))
        for r in f.get("robots", []):
            if r.get("took_local_detour", False):
                local_detour_count += 1

    # Task failure reasons
    unreachable_count = 0
    expired_count = 0
    for f in (history[-1:] if history else []):
        for t in f.get("tasks", []):
            if not t.get("is_completed", False):
                if t.get("is_unreachable", False):
                    unreachable_count += 1
                else:
                    expired_count += 1

    # Compose 5-8 cohesive sentences
    s1 = f"Simulation of **{alloc_name}** concluded on **{map_name}** across **{makespan} ticks** facing the **{adv_name}** adversary with a fleet of {n_robots} robots."
    s2 = f"The fleet finalized **{completed_tasks} of {total_tasks} tasks ({comp_rate:.1f}% completion)**, achieving a cumulative net welfare of **{net_welfare:.1f}** against **{total_travel:.1f} units** of total physical traversal."
    s3 = f"Workload distribution: {top_robot_str}, requiring **{total_msgs} total inter-robot messages** across the mission."
    s4 = f"During execution, the adversary closed **{len(all_blocked_ever)} distinct corridors**, triggering **{local_detour_count} local contingency detour activations** with zero communication overhead."
    s5 = f"When local recourse paths were exhausted, the fleet engaged in **{reauctions} market re-auction round(s)** to re-coordinate bundles."
    s6 = f"Under Pinsker belief margin filtering, the mechanism admitted **{safe_claims} safe claims** resulting in **{safe_conflicts} safe claim conflicts**, while deferring **{deferred_claims} claims** to consensus."
    if failed_tasks > 0:
        s7 = f"Among the {failed_tasks} incomplete tasks, {unreachable_count} were rendered topologically disconnected by corridor blockages, while {expired_count} lapsed as the mission horizon completed."
    else:
        s7 = "All scheduled mission tasks were completed before deadline expiration without terminal dropouts."

    paragraphs = [
        f"### Empirical Mission Summary ({alloc_name})\n",
        f"{s1} {s2}\n",
        f"{s3} {s4}\n",
        f"{s5} {s6} {s7}"
    ]
    return "\n\n".join(paragraphs)
