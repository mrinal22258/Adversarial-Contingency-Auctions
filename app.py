"""
Interactive Web Application for Adversarial Contingency Auctions (ACA).
Built with Gradio and powered directly by the acalib simulation engine.
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import gradio as gr

# Ensure workspace root is in path
sys.path.insert(0, os.path.dirname(__file__))

from acalib.env.graph_families import generate_graph
from acalib.env.adversaries import AdversaryType
from acalib.sim.engine import SimulationEngine


def run_simulation_wrapper(
    num_robots: int,
    num_tasks: int,
    graph_family: str,
    num_nodes: int,
    adversary_str: str,
    allocator_str: str,
    random_seed: int,
):
    seed = int(random_seed)
    n_nodes = int(num_nodes)
    n_rob = int(num_robots)
    n_tsk = int(num_tasks)

    # 1. Generate environment graph
    graph = generate_graph(family=graph_family.lower(), n_nodes=n_nodes, seed=seed)

    # 2. Adversary mapping
    adv_map = {
        "Stochastic": AdversaryType.STOCHASTIC,
        "Reactive": AdversaryType.REACTIVE,
        "Budgeted Interdiction": AdversaryType.BUDGETED_INTERDICTION,
        "Cyclic Patrol": AdversaryType.CYCLIC_PATROL,
    }
    adv_enum = adv_map.get(adversary_str, AdversaryType.REACTIVE)

    # 3. Allocator mapping
    alloc_map = {
        "ACA (Ours)": "aca",
        "ACA (No Margin)": "aca_no_margin",
        "CBBA": "cbba",
        "CBBA-Partial": "cbba_partial",
        "CC-CBBA": "cc_cbba",
        "Implicit (No Margin)": "implicit",
        "Sequential Single-Item (SSI)": "ssi",
        "Pessimistic Robust": "pessimistic",
        "Centralized Oracle": "oracle",
    }
    alloc_type = alloc_map.get(allocator_str, "aca")

    # 4. Engine setup
    engine = SimulationEngine(
        graph=graph,
        adversary_type=adv_enum,
        allocator_type=alloc_type,
        n_robots=n_rob,
        n_tasks=n_tsk,
        task_deadline=60,
        max_steps=60,
        contingency_depth=1 if alloc_type in ("aca", "aca_no_margin", "implicit") else 0,
        seed=seed,
    )

    # Record tick-by-tick state history
    state_history = []
    max_steps = 60
    engine.reset(max_steps=max_steps)

    for step in range(max_steps):
        # Step simulation
        active_before = {tid: t.completed for tid, t in engine.tasks.items()}
        cont = engine.step()

        # Capture snapshots
        robot_snaps = []
        for r in engine.robots.values():
            loc = r.current_node
            robot_snaps.append({
                "id": r.robot_id,
                "location": loc,
                "status": r.status,
                "active_task": r.active_task_id,
                "bundle": list(r.bundle),
            })

        task_snaps = []
        for tid, t in engine.tasks.items():
            task_snaps.append({
                "id": tid,
                "location": t.destination,
                "reward": t.reward,
                "is_completed": t.completed,
                "completed_by": t.completed_by,
            })

        blocked_edges = list(engine.blockage_process.get_active_blockages())

        state_history.append({
            "tick": step + 1,
            "robots": robot_snaps,
            "tasks": task_snaps,
            "blocked_edges": blocked_edges,
            "completed_tasks": sum(1 for t in engine.tasks.values() if t.completed),
            "conflicts": engine.metrics.cumulative_conflicts,
            "messages": engine.metrics.total_messages,
            "travel": engine.metrics.total_travel_distance,
        })

    # Layout for visualization
    pos = {n: (data.get("x", 0.0), data.get("y", 0.0)) for n, data in graph.nodes(data=True)}
    if not pos or pos[list(graph.nodes())[0]] == (0.0, 0.0):
        pos = nx.spring_layout(graph, seed=seed)

    return state_history, graph, pos


def plot_simulation_state(history, graph, node_positions, tick_idx):
    if not history or tick_idx >= len(history):
        return None

    frame = history[tick_idx]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.axis("off")

    robots = frame["robots"]
    tasks = frame["tasks"]
    blocked_edges = set(tuple(sorted(e)) for e in frame["blocked_edges"])

    regular_edges = []
    for u, v in graph.edges():
        c_e = tuple(sorted((u, v)))
        if c_e not in blocked_edges:
            regular_edges.append((u, v))

    # Draw open edges
    nx.draw_networkx_edges(
        graph, node_positions, edgelist=regular_edges,
        ax=ax, edge_color="#bdc3c7", width=1.5, alpha=0.7
    )

    # Draw blocked edges
    if blocked_edges:
        nx.draw_networkx_edges(
            graph, node_positions, edgelist=list(blocked_edges),
            ax=ax, edge_color="#e74c3c", width=3.5, style="solid"
        )

    # Draw nodes
    nx.draw_networkx_nodes(
        graph, node_positions, ax=ax,
        node_color="#ecf0f1", node_size=320, edgecolors="#95a5a6"
    )
    nx.draw_networkx_labels(
        graph, node_positions, ax=ax,
        font_size=8, font_color="#2c3e50", font_weight="bold"
    )

    # Draw active tasks
    active_tasks = [t for t in tasks if not t["is_completed"]]
    completed_tasks = [t for t in tasks if t["is_completed"]]

    if active_tasks:
        active_nodes = [t["location"] for t in active_tasks]
        nx.draw_networkx_nodes(
            graph, node_positions, nodelist=active_nodes, ax=ax,
            node_color="#f1c40f", node_shape="*", node_size=500, edgecolors="#d4ac0d"
        )
        for t in active_tasks:
            p = node_positions[t["location"]]
            ax.text(p[0], p[1] + 2.5, f"T{t['id']}", fontsize=8, ha="center", weight="bold", color="#b7950b")

    if completed_tasks:
        comp_nodes = [t["location"] for t in completed_tasks]
        nx.draw_networkx_nodes(
            graph, node_positions, nodelist=comp_nodes, ax=ax,
            node_color="#2ecc71", node_shape="o", node_size=280, edgecolors="#27ae60", alpha=0.6
        )

    # Draw robots
    colors = ["#2980b9", "#8e44ad", "#d35400", "#16a085", "#c0392b", "#27ae60"]
    for i, r in enumerate(robots):
        p = node_positions[r["location"]]
        c = colors[i % len(colors)]
        ax.scatter(p[0], p[1], color=c, marker="^", s=220, edgecolors="white", linewidths=1.5, zorder=6)
        status_txt = f"R{r['id']}" + (f"\n->T{r['active_task']}" if r['active_task'] is not None else "")
        ax.text(p[0], p[1] - 3.2, status_txt, fontsize=7, ha="center", weight="bold", color=c)

    ax.set_title(
        f"Step {frame['tick']}/60 | Tasks Completed: {frame['completed_tasks']}/{len(tasks)} | Conflicts: {frame['conflicts']} | Messages: {frame['messages']}",
        fontsize=11, fontweight="bold", pad=12
    )

    plt.tight_layout()
    return fig


def get_metrics_table(history, tick_idx):
    if not history or tick_idx >= len(history):
        return pd.DataFrame()

    frame = history[tick_idx]
    data = {
        "Simulation Metric": [
            "Completed Tasks",
            "Cumulative Conflicts",
            "Total Messages Exchanged",
            "Total Travel Distance",
        ],
        "Value": [
            str(frame["completed_tasks"]),
            str(frame["conflicts"]),
            str(frame["messages"]),
            f"{frame['travel']:.1f}",
        ]
    }
    return pd.DataFrame(data)


# Build Gradio Interface
theme = gr.themes.Soft(primary_hue="indigo", neutral_hue="slate")

with gr.Blocks(theme=theme, title="ACA Simulation Explorer") as demo:
    history_state = gr.State([])
    graph_state = gr.State(None)
    layout_state = gr.State(None)

    gr.Markdown(
        """
        # Adversarial Contingency Auctions (ACA)
        ### Interactive Multi-Robot Task Allocation under Strategic Blockages
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Configuration")
            num_robots = gr.Slider(minimum=2, maximum=8, step=1, value=4, label="Fleet Size (Robots)")
            num_tasks = gr.Slider(minimum=5, maximum=25, step=1, value=12, label="Task Count")
            graph_family = gr.Dropdown(choices=["RGG", "Warehouse", "ER"], value="RGG", label="Topology Family")
            num_nodes = gr.Slider(minimum=15, maximum=50, step=1, value=30, label="Graph Nodes")
            adversary_str = gr.Dropdown(
                choices=["Stochastic", "Reactive", "Budgeted Interdiction", "Cyclic Patrol"],
                value="Reactive", label="Adversary Type"
            )
            allocator_str = gr.Dropdown(
                choices=[
                    "ACA (Ours)",
                    "ACA (No Margin)",
                    "CBBA",
                    "CBBA-Partial",
                    "CC-CBBA",
                    "Implicit (No Margin)",
                    "Sequential Single-Item (SSI)",
                    "Pessimistic Robust",
                    "Centralized Oracle",
                ],
                value="ACA (Ours)", label="Allocation Mechanism"
            )
            random_seed = gr.Number(value=42, precision=0, label="Random Seed")
            run_btn = gr.Button("Run Simulation", variant="primary")

        with gr.Column(scale=2):
            gr.Markdown("### Trajectory & Allocation Telemetry")
            plot_output = gr.Plot(label="Simulation Map")
            round_slider = gr.Slider(minimum=0, maximum=60, step=1, value=0, label="Playback Step (Scrub to Inspect)")
            gr.Markdown("### Runtime Diagnostics")
            metrics_table = gr.Dataframe(headers=["Simulation Metric", "Value"], interactive=False)

    def handle_run(robots, tasks, fam, nodes, adv, alloc, seed):
        history, graph, pos = run_simulation_wrapper(robots, tasks, fam, nodes, adv, alloc, seed)
        max_idx = len(history) - 1
        fig = plot_simulation_state(history, graph, pos, max_idx)
        df_m = get_metrics_table(history, max_idx)
        return (
            history,
            graph,
            pos,
            fig,
            gr.update(minimum=0, maximum=max_idx, value=max_idx),
            df_m,
        )

    run_btn.click(
        fn=handle_run,
        inputs=[num_robots, num_tasks, graph_family, num_nodes, adversary_str, allocator_str, random_seed],
        outputs=[history_state, graph_state, layout_state, plot_output, round_slider, metrics_table],
    )

    def handle_slider(tick_idx, history, graph, pos):
        if not history or graph is None or pos is None:
            return None, pd.DataFrame()
        fig = plot_simulation_state(history, graph, pos, tick_idx)
        df_m = get_metrics_table(history, tick_idx)
        return fig, df_m

    round_slider.change(
        fn=handle_slider,
        inputs=[round_slider, history_state, graph_state, layout_state],
        outputs=[plot_output, metrics_table],
    )

if __name__ == "__main__":
    demo.launch()
