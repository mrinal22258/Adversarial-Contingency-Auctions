import os
import sys
import yaml
import tempfile
import random
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import gradio as gr

# Ensure the ACA directory is in the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ACA"))

from main import SimulationEngine

class VisualSimulationEngine(SimulationEngine):
    """Subclass of SimulationEngine to capture detailed tick-by-tick state history

    without modifying the core auction, belief, or environment logic.
    """
    def __init__(self, config_path: str) -> None:
        self.state_history = []
        super().__init__(config_path)

    def _collect_tick_metrics(self) -> None:
        # Run standard metrics gathering
        super()._collect_tick_metrics()
        
        # Save a visual state snapshot for the current tick
        robot_snapshots = []
        for r in self._robots:
            robot_snapshots.append({
                "id": r.robot_id,
                "type": r.robot_type,
                "location": r.current_location,
                "battery": r.current_battery,
                "planned_path": list(r.planned_path),
                "belief_theta_2": r.belief.get("theta_2", 0.5)
            })
            
        task_snapshots = []
        for t in self._active_tasks:
            task_snapshots.append({
                "id": t.task_id,
                "location": t.location,
                "reward": t.reward,
                "deadline": t.deadline,
                "is_completed": t.is_completed,
                "completed_by": t._completed_by,
                "completion_time": t._completion_time
            })
            
        blocked_edges = []
        for u, v, d in self._world.graph.edges(data=True):
            if d.get("blocked", False):
                blocked_edges.append((min(u, v), max(u, v)))
                
        self.state_history.append({
            "tick": self._time_step,
            "robots": robot_snapshots,
            "tasks": task_snapshots,
            "blocked_edges": blocked_edges,
            "assignments": dict(self._auction_house._assignments),
            "total_fleet_battery": sum(r.current_battery for r in self._robots),
            "completed_tasks_count": sum(1 for t in self._active_tasks if t.is_completed),
            "social_welfare": self._metrics_log[-1]["social_welfare"] if self._metrics_log else 0.0,
            "belief_divergence": self._metrics_log[-1]["belief_divergence"] if self._metrics_log else 0.0,
            "message_volume_spent": self._auction_house._current_epoch_messages,
            "out_of_sync": len(self._auction_house.get_market_state().get("out_of_sync_allocations", {}))
        })


def run_simulation_wrapper(num_scouts, num_heavy_lifters, num_nodes, mutation_probability, random_seed):
    # Load defaults
    default_config_path = os.path.join(os.path.dirname(__file__), "ACA", "config", "settings.yaml")
    with open(default_config_path, "r") as f:
        config = yaml.safe_load(f)
        
    # Apply UI parameters
    config["graph"]["num_nodes"] = int(num_nodes)
    config["graph"]["seed"] = int(random_seed)
    config["simulation"]["random_seed"] = int(random_seed)
    config["adversary"]["seed"] = int(random_seed) + 50
    config["adversary"]["mutation_probability"] = float(mutation_probability)
    
    # Update robot counts
    for robot_conf in config.get("robots", []):
        if robot_conf.get("type") == "scout":
            robot_conf["count"] = int(num_scouts)
        elif robot_conf.get("type") == "heavy_lifter":
            robot_conf["count"] = int(num_heavy_lifters)
            
    # Write to a temporary file
    temp_dir = tempfile.gettempdir()
    temp_config_path = os.path.join(temp_dir, f"aca_config_{random.randint(0, 1000000)}.yaml")
    
    with open(temp_config_path, "w") as f:
        yaml.safe_dump(config, f)
        
    try:
        # Instantiate and run
        engine = VisualSimulationEngine(temp_config_path)
        engine.run()
        history = engine.state_history
        graph = engine._world.graph
    finally:
        # Clean up config file
        if os.path.exists(temp_config_path):
            os.remove(temp_config_path)
            
    # Generate node positions for visual continuity
    node_positions = nx.spring_layout(graph, seed=int(random_seed))
    
    return history, graph, node_positions


def plot_simulation_state(history, graph, node_positions, tick_idx):
    if not history or tick_idx >= len(history):
        return None
        
    history_frame = history[tick_idx]
    
    # Create matplotlib figure
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.axis("off")
    
    # 1. Gather frame states
    robots = history_frame["robots"]
    tasks = history_frame["tasks"]
    blocked_edges = set(history_frame["blocked_edges"])
    
    # 2. Draw regular edges
    regular_edges = []
    risky_edges = []
    
    for u, v, d in graph.edges(data=True):
        edge = (min(u, v), max(u, v))
        if edge in blocked_edges:
            continue
        if d.get("is_risk", False):
            risky_edges.append(edge)
        else:
            regular_edges.append(edge)
            
    # Draw normal edges
    nx.draw_networkx_edges(
        graph, node_positions, edgelist=regular_edges,
        ax=ax, edge_color="#d5dbdb", width=1.5
    )
    
    # Draw risky non-blocked edges (dashed orange)
    nx.draw_networkx_edges(
        graph, node_positions, edgelist=risky_edges,
        ax=ax, edge_color="#f39c12", width=1.5, style="dashed"
    )
    
    # Draw blocked edges (thick red)
    if blocked_edges:
        nx.draw_networkx_edges(
            graph, node_positions, edgelist=list(blocked_edges),
            ax=ax, edge_color="#e74c3c", width=3.5
        )
        
    # Draw base nodes
    nx.draw_networkx_nodes(
        graph, node_positions, ax=ax,
        node_color="#f8f9f9", node_size=350, edgecolors="#bdc3c7"
    )
    
    # Label nodes
    nx.draw_networkx_labels(
        graph, node_positions, ax=ax,
        font_size=9, font_color="#34495e", font_weight="bold"
    )
    
    # 3. Draw active/completed tasks
    active_tasks = [t for t in tasks if not t["is_completed"]]
    completed_tasks = [t for t in tasks if t["is_completed"]]
    
    if active_tasks:
        active_task_nodes = [t["location"] for t in active_tasks]
        nx.draw_networkx_nodes(
            graph, node_positions, nodelist=active_task_nodes, ax=ax,
            node_color="#f1c40f", node_shape="*", node_size=550, edgecolors="#d4ac0d"
        )
        # Add labels for active tasks reward
        for t in active_tasks:
            pos = node_positions[t["location"]]
            ax.text(
                pos[0], pos[1] + 0.08, f"{t['id']}\n(R:{int(t['reward'])})",
                color="#7d6608", fontsize=8, ha="center", weight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#f1c40f", alpha=0.9)
            )
            
    if completed_tasks:
        completed_task_nodes = [t["location"] for t in completed_tasks]
        nx.draw_networkx_nodes(
            graph, node_positions, nodelist=completed_task_nodes, ax=ax,
            node_color="#2ecc71", node_shape="o", node_size=350, edgecolors="#27ae60", alpha=0.5
        )
        
    # 4. Draw robots
    # Group robots by location to offset them slightly if multiple are on the same node
    loc_to_robots = {}
    for r in robots:
        loc = r["location"]
        if loc not in loc_to_robots:
            loc_to_robots[loc] = []
        loc_to_robots[loc].append(r)
        
    for loc, r_list in loc_to_robots.items():
        base_pos = node_positions[loc]
        for i, r in enumerate(r_list):
            if len(r_list) > 1:
                angle = 2.0 * np.pi * i / len(r_list)
                offset = np.array([0.06 * np.cos(angle), 0.06 * np.sin(angle)])
                pos = base_pos + offset
            else:
                pos = base_pos
                
            color = "#3498db" if r["type"] == "scout" else "#9b59b6"
            marker = "^" if r["type"] == "scout" else "s"
            
            ax.scatter(
                pos[0], pos[1], color=color, marker=marker, s=180, edgecolors="white",
                linewidths=1.5, zorder=5
            )
            
            # Add text label for battery and ID
            ax.text(
                pos[0], pos[1] - 0.09, f"{r['id']}\n(⚡:{int(r['battery'])})",
                color="#2c3e50", fontsize=8, ha="center", weight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, alpha=0.9)
            )
            
    # Add title and metrics info
    ax.set_title(
        f"Tick: {history_frame['tick']} | Fleet Battery: {history_frame['total_fleet_battery']:.1f} | Welfare: {history_frame['social_welfare']:.1f}",
        fontsize=12, fontweight="bold", pad=15
    )
    
    plt.tight_layout()
    return fig


def get_metrics_table(history, tick_idx):
    if not history or tick_idx >= len(history):
        return pd.DataFrame()
        
    frame = history[tick_idx]
    data = {
        "Simulation Metric": [
            "Completed Tasks (Count)",
            "Social Welfare (Rewards - Battery Cost)",
            "Total Fleet Battery Remaining",
            "Belief Divergence across Fleet (StdDev)",
            "Consensus Communication Spent (kappa)",
            "Out-of-Sync Allocation Discrepancies"
        ],
        "Value": [
            int(frame["completed_tasks_count"]),
            f"{frame['social_welfare']:.2f}",
            f"{frame['total_fleet_battery']:.2f}",
            f"{frame['belief_divergence']:.4f}",
            f"{frame['message_volume_spent']:.1f}",
            int(frame["out_of_sync"])
        ]
    }
    return pd.DataFrame(data)


# Build Gradio Interface
theme = gr.themes.Soft(primary_hue="indigo", neutral_hue="slate")

with gr.Blocks(theme=theme, title="Adversarial Contingency Auctions") as demo:
    # State values to hold simulation output
    history_state = gr.State([])
    graph_state = gr.State(None)
    layout_state = gr.State(None)
    
    # Title & Header
    gr.Markdown(
        """
        # Adversarial Contingency Auctions — Multi-Robot Task Allocation
        ### Decentralized auction-based allocation under adversarial blockages and inconsistent-belief dynamics
        """
    )
    
    with gr.Row():
        # LEFT Column: Controls
        with gr.Column(scale=1):
            gr.Markdown("### Simulation Parameters")
            
            num_scouts = gr.Slider(
                minimum=0, maximum=4, step=1, value=2,
                label="Number of Scouts (Triangles)"
            )
            num_heavy_lifters = gr.Slider(
                minimum=0, maximum=4, step=1, value=2,
                label="Number of Heavy Lifters (Squares)"
            )
            num_nodes = gr.Slider(
                minimum=5, maximum=30, step=1, value=15,
                label="Environment Size (Number of Graph Nodes)"
            )
            mutation_probability = gr.Slider(
                minimum=0.0, maximum=1.0, step=0.05, value=0.5,
                label="Adversarial Blockage Probability"
            )
            random_seed = gr.Number(
                value=42, precision=0,
                label="Random Seed (Reproducibility)"
            )
            
            run_btn = gr.Button("Run Simulation", variant="primary")
            
        # RIGHT Column: Output Viz & Stats
        with gr.Column(scale=2):
            gr.Markdown("### Environment Map & Allocation State")
            plot_output = gr.Plot(label="Graph State Visualization")
            
            # Interactive round slider
            round_slider = gr.Slider(
                minimum=0, maximum=0, step=1, value=0,
                label="Step / Tick (Scrub to animate)"
            )
            
            gr.Markdown("### Tick Diagnostics & Metrics")
            metrics_table = gr.Dataframe(
                headers=["Simulation Metric", "Value"],
                interactive=False
            )

    # Simulation click trigger
    def handle_run_simulation(scouts, lifters, nodes, mutation_prob, seed):
        # Run simulation
        history, graph, node_positions = run_simulation_wrapper(
            scouts, lifters, nodes, mutation_prob, seed
        )
        
        # Max steps
        max_idx = len(history) - 1
        
        # Plot final state frame
        fig = plot_simulation_state(history, graph, node_positions, max_idx)
        df_metrics = get_metrics_table(history, max_idx)
        
        # Update slider bounds and state variables
        return (
            history,
            graph,
            node_positions,
            fig,
            gr.update(minimum=0, maximum=max_idx, value=max_idx),
            df_metrics
        )

    run_btn.click(
        fn=handle_run_simulation,
        inputs=[num_scouts, num_heavy_lifters, num_nodes, mutation_probability, random_seed],
        outputs=[history_state, graph_state, layout_state, plot_output, round_slider, metrics_table]
    )

    # Slider scrub trigger
    def handle_slider_change(tick_idx, history, graph, node_positions):
        if not history or graph is None or node_positions is None:
            return None, pd.DataFrame()
            
        fig = plot_simulation_state(history, graph, node_positions, tick_idx)
        df_metrics = get_metrics_table(history, tick_idx)
        return fig, df_metrics

    round_slider.change(
        fn=handle_slider_change,
        inputs=[round_slider, history_state, graph_state, layout_state],
        outputs=[plot_output, metrics_table]
    )

if __name__ == "__main__":
    demo.launch()
