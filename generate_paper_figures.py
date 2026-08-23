"""Generates publication-quality PDF and high-res PNG figures for ACA paper.

Uses matplotlib and standard libraries to produce vector PDF and 300 DPI PNG figures
matching IEEE Transactions / RA-L formatting requirements.
"""

import os
import sys
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.gridspec import GridSpec
except ImportError:
    print("[Error] matplotlib is required to generate paper figures. Run: pip install matplotlib numpy")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Common styling
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 13,
    "text.usetex": False
})


def save_fig(fig, base_name):
    pdf_path = os.path.join(OUTPUT_DIR, f"{base_name}.pdf")
    png_path = os.path.join(OUTPUT_DIR, f"{base_name}.png")
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight", dpi=300)
    fig.savefig(png_path, format="png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"Saved: {pdf_path} and {png_path}")


def create_fig1_motivation():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    
    # (a) Classical Baseline
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 10)
    ax1.axis("off")
    ax1.set_title("(a) Classical Auctions (CBBA / SSI): Cascading Reset", fontsize=12, fontweight="bold", color="#b91c1c", pad=12)
    
    # Border
    rect1 = patches.FancyBboxPatch((0.2, 0.2), 9.6, 9.4, boxstyle="round,pad=0.3", ec="#f87171", fc="#fef2f2", lw=1.5)
    ax1.add_patch(rect1)
    
    # Nodes
    c1 = plt.Circle((2, 7.5), 0.7, color="#3b82f6", ec="#1d4ed8", lw=2, zorder=4)
    c2 = plt.Circle((5, 7.5), 0.6, color="#64748b", ec="#334155", lw=2, zorder=4)
    c3 = plt.Circle((8, 7.5), 0.7, color="#10b981", ec="#047857", lw=2, zorder=4)
    ax1.add_patch(c1); ax1.add_patch(c2); ax1.add_patch(c3)
    ax1.text(2, 7.5, "R1", color="white", weight="bold", ha="center", va="center", zorder=5)
    ax1.text(5, 7.5, "v2", color="white", weight="bold", ha="center", va="center", zorder=5)
    ax1.text(8, 7.5, "T1", color="white", weight="bold", ha="center", va="center", zorder=5)
    ax1.text(2, 8.5, "Start (v1)", ha="center", fontsize=9, color="#1e293b")
    ax1.text(8, 8.5, "Goal (v3)", ha="center", fontsize=9, color="#1e293b")
    
    # Edges
    ax1.plot([2.7, 4.4], [7.5, 7.5], color="#2563eb", lw=3.5, zorder=3)
    ax1.plot([5.6, 7.3], [7.5, 7.5], color="#dc2626", lw=3, ls="--", zorder=3)
    ax1.text(6.5, 8.0, "BLOCKED", color="#b91c1c", weight="bold", fontsize=9, ha="center")
    
    # Sequence box
    s_rect1 = patches.FancyBboxPatch((0.6, 0.6), 8.8, 5.8, boxstyle="round,pad=0.2", ec="#fca5a5", fc="white", lw=1.2)
    ax1.add_patch(s_rect1)
    ax1.text(0.9, 5.8, "Failure Sequence:", fontweight="bold", color="#991b1b", fontsize=11)
    ax1.text(0.9, 4.8, "1. R1 reaches blocked edge (v2 -> v3). Single path fails.", fontsize=9.5, color="#334155")
    ax1.text(0.9, 4.0, "2. R1 drops Task T1 and broadcasts global nullification.", fontsize=9.5, color="#334155")
    ax1.text(0.9, 3.2, "3. Entire fleet forced into expensive multi-round re-auction.", fontsize=9.5, color="#b91c1c", weight="bold")
    ax1.text(0.9, 2.4, "4. Under jammed/partitioned comms: Allocation collapse.", fontsize=9.5, color="#b91c1c", weight="bold")
    
    res_box1 = patches.FancyBboxPatch((0.9, 0.9), 8.2, 1.0, boxstyle="round,pad=0.1", ec="#ef4444", fc="#fee2e2", lw=1)
    ax1.add_patch(res_box1)
    ax1.text(5.0, 1.4, "Result: 68% Completion, High Comm Surge (>75 msgs)", color="#991b1b", weight="bold", ha="center", va="center", fontsize=9.5)

    # (b) Proposed ACA
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 10)
    ax2.axis("off")
    ax2.set_title("(b) Proposed ACA: Autonomous Contingency Tree Activation", fontsize=12, fontweight="bold", color="#047857", pad=12)
    
    rect2 = patches.FancyBboxPatch((0.2, 0.2), 9.6, 9.4, boxstyle="round,pad=0.3", ec="#86efac", fc="#f0fdf4", lw=1.5)
    ax2.add_patch(rect2)
    
    # Nodes
    c2_1 = plt.Circle((2, 7.8), 0.7, color="#3b82f6", ec="#1d4ed8", lw=2, zorder=4)
    c2_2 = plt.Circle((4.5, 7.8), 0.6, color="#64748b", ec="#334155", lw=2, zorder=4)
    c2_3 = plt.Circle((8, 7.8), 0.7, color="#10b981", ec="#047857", lw=2, zorder=4)
    c2_4 = plt.Circle((6.2, 6.2), 0.6, color="#06b6d4", ec="#0891b2", lw=2, zorder=4)
    ax2.add_patch(c2_1); ax2.add_patch(c2_2); ax2.add_patch(c2_3); ax2.add_patch(c2_4)
    ax2.text(2, 7.8, "R1", color="white", weight="bold", ha="center", va="center", zorder=5)
    ax2.text(4.5, 7.8, "v2", color="white", weight="bold", ha="center", va="center", zorder=5)
    ax2.text(8, 7.8, "T1", color="white", weight="bold", ha="center", va="center", zorder=5)
    ax2.text(6.2, 6.2, "v4", color="white", weight="bold", ha="center", va="center", zorder=5)
    ax2.text(6.2, 5.5, "Contingency", ha="center", fontsize=8.5, color="#0e7490")
    
    # Edges
    ax2.plot([2.7, 3.9], [7.8, 7.8], color="#2563eb", lw=3.5, zorder=3)
    ax2.plot([5.1, 7.3], [7.8, 7.8], color="#dc2626", lw=2.5, ls=":", zorder=3)
    ax2.annotate("", xy=(5.8, 6.5), xytext=(4.9, 7.4), arrowprops=dict(arrowstyle="->", color="#059669", lw=3))
    ax2.annotate("", xy=(7.4, 7.4), xytext=(6.6, 6.5), arrowprops=dict(arrowstyle="->", color="#059669", lw=3))
    
    # Sequence box
    s_rect2 = patches.FancyBboxPatch((0.6, 0.6), 8.8, 4.4, boxstyle="round,pad=0.2", ec="#86efac", fc="white", lw=1.2)
    ax2.add_patch(s_rect2)
    ax2.text(0.9, 4.5, "ACA Resilience Sequence:", fontweight="bold", color="#065f46", fontsize=11)
    ax2.text(0.9, 3.7, "1. Precomputed Contingency Tree pre-calculates detour v4.", fontsize=9.5, color="#334155")
    ax2.text(0.9, 3.0, "2. R1 detects blockage, updates P(theta), pivots locally to v4.", fontsize=9.5, color="#334155")
    ax2.text(0.9, 2.3, "3. Zero global re-auction messages sent; market stays intact.", fontsize=9.5, color="#047857", weight="bold")
    
    res_box2 = patches.FancyBboxPatch((0.9, 0.9), 8.2, 1.0, boxstyle="round,pad=0.1", ec="#22c55e", fc="#dcfce7", lw=1)
    ax2.add_patch(res_box2)
    ax2.text(5.0, 1.4, "Result: 91% Completion, 0 Re-Auctions, Bounded Comms", color="#065f46", weight="bold", ha="center", va="center", fontsize=9.5)
    
    save_fig(fig, "fig1_motivation")


def create_fig6_boxplots():
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 4.5))
    
    methods = ["SSI", "CBBA", "Greedy DRA", "ACA w/o KL", "Full ACA"]
    colors = ["#94a3b8", "#60a5fa", "#f87171", "#a78bfa", "#10b981"]
    
    # Subplot 1: Completion Rate
    rates = [68.4, 82.1, 74.0, 84.5, 91.2]
    bars1 = ax1.bar(methods, rates, color=colors, width=0.6, edgecolor="#334155", lw=1)
    ax1.set_ylabel("Completion Rate (%)", fontweight="bold")
    ax1.set_ylim(0, 105)
    ax1.set_title("(a) Task Completion Rate (%)", fontweight="bold", pad=10)
    ax1.grid(axis="y", linestyle="--", alpha=0.5)
    for bar, val in zip(bars1, rates):
        ax1.text(bar.get_x() + bar.get_width()/2, val + 2, f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax1.tick_params(axis="x", rotation=25)
    
    # Subplot 2: Conflicts
    conflicts = [44.2, 28.0, 38.5, 21.4, 5.1]
    bars2 = ax2.bar(methods, conflicts, color=colors, width=0.6, edgecolor="#334155", lw=1)
    ax2.set_ylabel("Allocation Conflict Rate (%)", fontweight="bold")
    ax2.set_ylim(0, 55)
    ax2.set_title("(b) Allocation Conflicts (%) [Lower Better]", fontweight="bold", pad=10)
    ax2.grid(axis="y", linestyle="--", alpha=0.5)
    for bar, val in zip(bars2, conflicts):
        ax2.text(bar.get_x() + bar.get_width()/2, val + 1, f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax2.tick_params(axis="x", rotation=25)

    # Subplot 3: Consensus Comm Msgs
    comms = [32.4, 98.6, 114.2, 45.2, 24.1]
    bars3 = ax3.bar(methods, comms, color=colors, width=0.6, edgecolor="#334155", lw=1)
    ax3.set_ylabel("Consensus Overhead (Messages)", fontweight="bold")
    ax3.set_ylim(0, 135)
    ax3.set_title("(c) Consensus Message Volume", fontweight="bold", pad=10)
    ax3.grid(axis="y", linestyle="--", alpha=0.5)
    for bar, val in zip(bars3, comms):
        ax3.text(bar.get_x() + bar.get_width()/2, val + 2, f"{val:.1f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax3.tick_params(axis="x", rotation=25)

    plt.tight_layout()
    save_fig(fig, "fig6_benchmark_boxplots")


def create_fig2_adversary_model():
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(14, 5))
    
    for ax in (ax1, ax2, ax3):
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
        
    # (a) Fleet
    ax1.set_title("(a) Heterogeneous Fleet", fontweight="bold", color="#1d4ed8", pad=10)
    rect1 = patches.FancyBboxPatch((0.2, 0.2), 9.6, 9.6, boxstyle="round,pad=0.2", ec="#bfdbfe", fc="#eff6ff")
    ax1.add_patch(rect1)
    ax1.text(0.6, 8.8, "▲ Scout Robots (Mobility)", fontweight="bold", color="#1e40af", fontsize=10.5)
    ax1.text(0.6, 7.8, "• Speed: 2.0x nodes/tick\n• Sensing Radius: 2 hops\n• Comm Budget: 100 bits/tick\n• Role: Recon & prior P(θ) update", fontsize=9, color="#334155")
    ax1.text(0.6, 4.4, "■ Heavy Lifters (Payload)", fontweight="bold", color="#6d28d9", fontsize=10.5)
    ax1.text(0.6, 3.4, "• Speed: 1.0x nodes/tick\n• Battery: 300 units (Move: 6.0)\n• Sensing: 1 hop | Comm: 40 bits\n• Role: High-value task fulfillment", fontsize=9, color="#334155")
    
    # (b) Adversary
    ax2.set_title("(b) Adversary Policy Space (θ*)", fontweight="bold", color="#b91c1c", pad=10)
    rect2 = patches.FancyBboxPatch((0.2, 0.2), 9.6, 9.6, boxstyle="round,pad=0.2", ec="#fecaca", fc="#fef2f2")
    ax2.add_patch(rect2)
    ax2.text(0.6, 8.8, "θ1: Stochastic Jammer", fontweight="bold", color="#991b1b", fontsize=10.5)
    ax2.text(0.6, 7.8, "• P(Xe = 1 | θ1) = P_base\n• Random non-targeted blockage", fontsize=9, color="#334155")
    ax2.text(0.6, 5.8, "θ2: Reactive Path Blocker", fontweight="bold", color="#991b1b", fontsize=10.5)
    ax2.text(0.6, 4.8, "• P(Xe = 1 | θ2) = min(1.0, Pbase + αNe)\n• Triggered within 1 hop of robot", fontsize=9, color="#334155")
    ax2.text(0.6, 2.8, "θ3: Optimal Minimax", fontweight="bold", color="#991b1b", fontsize=10.5)
    ax2.text(0.6, 1.8, "• argmax_e Σ ΔCost_r(e)\n• Maximum bottleneck congestion", fontsize=9, color="#334155")

    # (c) Regularization
    ax3.set_title("(c) Beliefs & KL Regularization", fontweight="bold", color="#047857", pad=10)
    rect3 = patches.FancyBboxPatch((0.2, 0.2), 9.6, 9.6, boxstyle="round,pad=0.2", ec="#bbf7d0", fc="#f0fdf4")
    ax3.add_patch(rect3)
    ax3.text(0.6, 8.8, "Bayesian Posterior Filter", fontweight="bold", color="#065f46", fontsize=10.5)
    ax3.text(0.6, 7.6, "P_r(θj | Xe) ∝ P(Xe | θj) P_r(θj)\n• Private Prior: B_r = [P(θ1), P(θ2)]\n• Inferred Teammate Mean: Q^(r)", fontsize=9, color="#334155")
    ax3.text(0.6, 4.4, "KL-Regularized Bidding", fontweight="bold", color="#065f46", fontsize=10.5)
    ax3.text(0.6, 3.2, "Bid_r(t) = E_r[Cost] + λ D_KL(B_r || Q_r)\n• Penalizes out-of-sync bids\n• Stabilizes consensus under comm drop", fontsize=9, color="#334155")

    plt.tight_layout()
    save_fig(fig, "fig2_adversary_model")


def create_fig3_contingency_tree():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    ax1.set_xlim(0, 10); ax1.set_ylim(0, 10); ax1.axis("off")
    ax2.set_xlim(0, 10); ax2.set_ylim(0, 10); ax2.axis("off")
    
    ax1.set_title("(a) Spatial Contingency Trajectory Formulation", fontweight="bold", color="#0891b2", pad=10)
    rect1 = patches.FancyBboxPatch((0.2, 0.2), 9.6, 9.6, boxstyle="round,pad=0.2", ec="#cbd5e1", fc="white")
    ax1.add_patch(rect1)
    
    # Nodes
    c1 = plt.Circle((1.8, 5.0), 0.6, color="#3b82f6", zorder=4); ax1.add_patch(c1); ax1.text(1.8, 5.0, "v_init", color="white", ha="center", va="center", weight="bold", fontsize=9)
    c2 = plt.Circle((4.8, 5.0), 0.5, color="#64748b", zorder=4); ax1.add_patch(c2); ax1.text(4.8, 5.0, "u", color="white", ha="center", va="center", weight="bold", fontsize=9)
    c3 = plt.Circle((8.2, 5.0), 0.6, color="#10b981", zorder=4); ax1.add_patch(c3); ax1.text(8.2, 5.0, "v_goal", color="white", ha="center", va="center", weight="bold", fontsize=9)
    c4 = plt.Circle((6.5, 7.2), 0.5, color="#64748b", zorder=4); ax1.add_patch(c4); ax1.text(6.5, 7.2, "v", color="white", ha="center", va="center", weight="bold", fontsize=9)
    c5 = plt.Circle((6.5, 2.8), 0.5, color="#f59e0b", zorder=4); ax1.add_patch(c5); ax1.text(6.5, 2.8, "w_det", color="white", ha="center", va="center", weight="bold", fontsize=9)
    
    # Lines
    ax1.plot([2.4, 4.3], [5.0, 5.0], color="#3b82f6", lw=3.5)
    ax1.plot([5.2, 6.1], [5.3, 6.8], color="#10b981", lw=3)
    ax1.plot([6.9, 7.8], [6.8, 5.3], color="#10b981", lw=3)
    ax1.text(6.5, 8.1, "Branch A: Open (Cost_A)", ha="center", color="#059669", weight="bold", fontsize=9.5)
    
    ax1.plot([5.2, 6.1], [4.7, 3.2], color="#d97706", lw=3, ls="--")
    ax1.plot([6.9, 7.8], [3.2, 4.7], color="#d97706", lw=3, ls="--")
    ax1.text(6.5, 1.9, "Branch B: Detour (Cost_B)", ha="center", color="#d97706", weight="bold", fontsize=9.5)
    
    # (b) Decision Tree
    ax2.set_title("(b) Bayesian Expected Valuation Tree", fontweight="bold", color="#4338ca", pad=10)
    rect2 = patches.FancyBboxPatch((0.2, 0.2), 9.6, 9.6, boxstyle="round,pad=0.2", ec="#cbd5e1", fc="white")
    ax2.add_patch(rect2)
    
    r_root = patches.FancyBboxPatch((3.5, 7.8), 3.0, 1.2, boxstyle="round,pad=0.1", ec="#6366f1", fc="#e0e7ff")
    ax2.add_patch(r_root); ax2.text(5.0, 8.4, "Trajectory T(r, t)", ha="center", va="center", weight="bold", color="#312e81")
    
    ax2.plot([4.2, 2.5], [7.8, 6.2], color="#059669", lw=2.5)
    ax2.plot([5.8, 7.5], [7.8, 6.2], color="#d97706", lw=2.5)
    ax2.text(2.6, 7.1, "P_r(θ1) [Open]", color="#059669", weight="bold", fontsize=9)
    ax2.text(7.4, 7.1, "P_r(θ2) [Blocked]", color="#d97706", weight="bold", fontsize=9)
    
    r_leaf1 = patches.FancyBboxPatch((1.0, 4.8), 3.0, 1.4, boxstyle="round,pad=0.1", ec="#22c55e", fc="#dcfce7")
    ax2.add_patch(r_leaf1); ax2.text(2.5, 5.5, "Branch A\nCost_A", ha="center", va="center", weight="bold", color="#14532d", fontsize=9.5)
    
    r_leaf2 = patches.FancyBboxPatch((6.0, 4.8), 3.0, 1.4, boxstyle="round,pad=0.1", ec="#f59e0b", fc="#fef3c7")
    ax2.add_patch(r_leaf2); ax2.text(7.5, 5.5, "Branch B (Detour)\nCost_B", ha="center", va="center", weight="bold", color="#78350f", fontsize=9.5)
    
    r_eq = patches.FancyBboxPatch((0.8, 1.0), 8.4, 2.8, boxstyle="round,pad=0.2", ec="#cbd5e1", fc="#f8fafc")
    ax2.add_patch(r_eq)
    ax2.text(5.0, 3.0, "Expected Contingency Valuation:", ha="center", weight="bold", color="#1e293b", fontsize=10.5)
    ax2.text(5.0, 2.1, "E_r[Cost] = P_r(θ1) · Cost_A + P_r(θ2) · Cost_B", ha="center", weight="bold", color="#4338ca", fontsize=11)
    ax2.text(5.0, 1.4, "Instant localized pivot upon sensing Xe = 1", ha="center", color="#059669", fontsize=9.5)
    
    plt.tight_layout()
    save_fig(fig, "fig3_contingency_tree")


def create_fig7_traces():
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.2))
    ticks = ["t = 15: SSI Allocation", "t = 45: Jammer Triggered", "t = 65: Contingency Pivot", "t = 110: 100% Completed"]
    colors_header = ["#1e293b", "#b91c1c", "#047857", "#4338ca"]
    
    for idx, (ax, tick_title, h_color) in enumerate(zip(axes, ticks, colors_header)):
        ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
        ax.set_title(tick_title, fontweight="bold", color=h_color, fontsize=10.5, pad=8)
        rect = patches.FancyBboxPatch((0.2, 0.2), 9.6, 9.6, boxstyle="round,pad=0.1", ec="#cbd5e1", fc="white")
        ax.add_patch(rect)
        
        # Nodes
        c_r1 = plt.Circle((2.5, 7.5 if idx<2 else (5.5 if idx==2 else 7.5)), 0.6, color="#3b82f6", zorder=4); ax.add_patch(c_r1)
        ax.text(c_r1.center[0], c_r1.center[1], "R1", color="white", weight="bold", ha="center", va="center", fontsize=8)
        
        c_t1 = plt.Circle((7.5, 7.5), 0.6, color="#10b981", zorder=4); ax.add_patch(c_t1)
        ax.text(7.5, 7.5, "T1", color="white", weight="bold", ha="center", va="center", fontsize=8)
        
        c_v2 = plt.Circle((5.0, 7.5), 0.5, color="#64748b", zorder=4); ax.add_patch(c_v2)
        ax.text(5.0, 7.5, "v2", color="white", ha="center", va="center", fontsize=8)
        
        c_v3 = plt.Circle((5.0, 4.0), 0.5, color="#06b6d4", zorder=4); ax.add_patch(c_v3)
        ax.text(5.0, 4.0, "v3", color="white", ha="center", va="center", fontsize=8)

        if idx == 0:
            ax.plot([3.1, 6.9], [7.5, 7.5], color="#2563eb", lw=2.5)
            ax.text(5.0, 1.5, "• Initial Bids Allocated\n• Uniform Prior [0.5, 0.5]", ha="center", fontsize=8.5, color="#334155")
        elif idx == 1:
            ax.plot([3.1, 4.5], [7.5, 7.5], color="#2563eb", lw=2.5)
            ax.plot([5.5, 6.9], [7.5, 7.5], color="#dc2626", lw=2.5, ls=":")
            ax.text(6.2, 8.4, "BLOCKED", color="#dc2626", weight="bold", fontsize=8, ha="center")
            ax.text(5.0, 1.5, "• Edge Blocked!\n• Posterior P(θ2) = 0.82", ha="center", fontsize=8.5, color="#b91c1c")
        elif idx == 2:
            ax.plot([3.0, 4.6], [7.1, 4.4], color="#059669", lw=2.5)
            ax.plot([5.4, 7.0], [4.4, 7.1], color="#059669", lw=2.5)
            ax.text(5.0, 1.5, "• Local Detour Activated\n• 0 Global Re-Auctions", ha="center", fontsize=8.5, color="#047857", weight="bold")
        elif idx == 3:
            ax.plot([3.0, 5.0, 7.5], [7.5, 4.0, 7.5], color="#059669", lw=2, alpha=0.5)
            ax.text(5.0, 1.5, "• Mission Accomplished\n• Welfare: +184.2", ha="center", fontsize=8.5, color="#1e1b4b", weight="bold")
            
    plt.tight_layout()
    save_fig(fig, "fig7_qualitative_traces")


def create_fig4_pipeline():
    fig, ax = plt.subplots(figsize=(15, 7.8))
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 62)
    ax.axis("off")

    # Main outer border
    outer = patches.FancyBboxPatch((1, 1), 118, 60, boxstyle="round,pad=0.5", ec="#cbd5e1", fc="#ffffff", lw=1.5)
    ax.add_patch(outer)

    # Title
    ax.text(60, 58.5, "Adversarial Contingency Auctions (ACA) Architecture Pipeline", fontsize=15, fontweight="bold", color="#0f172a", ha="center")
    ax.text(60, 56.2, "Decentralized Multi-Robot Task Allocation with Inconsistent-Belief Modeling & Adversarial Path Blockages", fontsize=10.5, color="#64748b", ha="center")

    # 1. FLEET BLOCK
    b1 = patches.FancyBboxPatch((4, 28), 24, 25, boxstyle="round,pad=0.2", ec="#3b82f6", fc="#eff6ff", lw=1.5)
    ax.add_patch(b1)
    b1_h = patches.FancyBboxPatch((4, 49), 24, 4, boxstyle="round,pad=0.1", ec="#3b82f6", fc="#3b82f6", lw=1)
    ax.add_patch(b1_h)
    ax.text(16, 51, "1. Heterogeneous Fleet", color="white", fontweight="bold", fontsize=11, ha="center", va="center")
    ax.text(5.5, 45, "▲ Scout Robots (Fast)", color="#1e40af", fontweight="bold", fontsize=9.5)
    ax.text(5.5, 41.5, "• Speed: 2.0x | Range = 2\n• Comm Budget: 100 bits/tick\n• Recon & prior P(θ) update", color="#334155", fontsize=8.5)
    ax.text(5.5, 34.5, "■ Heavy Lifters (Payload)", color="#1e40af", fontweight="bold", fontsize=9.5)
    ax.text(5.5, 31, "• Battery: 300 units (Move: 6.0)\n• High payload transport\n• Task fulfillment & execution", color="#334155", fontsize=8.5)

    # 2. AUCTION ENGINE BLOCK
    b2 = patches.FancyBboxPatch((33, 28), 25, 25, boxstyle="round,pad=0.2", ec="#8b5cf6", fc="#f5f3ff", lw=1.5)
    ax.add_patch(b2)
    b2_h = patches.FancyBboxPatch((33, 49), 25, 4, boxstyle="round,pad=0.1", ec="#8b5cf6", fc="#8b5cf6", lw=1)
    ax.add_patch(b2_h)
    ax.text(45.5, 51, "2. Decentralized Market", color="white", fontweight="bold", fontsize=11, ha="center", va="center")
    ax.text(34.5, 45, "Sequential Single-Item (SSI)", color="#5b21b6", fontweight="bold", fontsize=9.5)
    ax.text(34.5, 41.5, "• Marginal Bid Calculation: c_ij\n• Consensus Iterations (CBBA)", color="#334155", fontsize=8.5)
    ax.text(34.5, 35.5, "Disagreement Penalty (κ)", color="#5b21b6", fontweight="bold", fontsize=9.5)
    ax.text(34.5, 31, "• Inconsistent-Belief Regularizer\n• Bundle Size Bound (k ≤ 5)\n• Winning Bids Allocated", color="#334155", fontsize=8.5)

    # 3. STRATEGIC ADVERSARY BLOCK
    b3 = patches.FancyBboxPatch((63, 28), 24, 25, boxstyle="round,pad=0.2", ec="#ef4444", fc="#fef2f2", lw=1.5)
    ax.add_patch(b3)
    b3_h = patches.FancyBboxPatch((63, 49), 24, 4, boxstyle="round,pad=0.1", ec="#ef4444", fc="#ef4444", lw=1)
    ax.add_patch(b3_h)
    ax.text(75, 51, "3. Strategic Adversary (θ*)", color="white", fontweight="bold", fontsize=11, ha="center", va="center")
    ax.text(64.5, 45, "Adversary Behavioral Policies", color="#991b1b", fontweight="bold", fontsize=9.5)
    ax.text(64.5, 39, "• θ1: Stochastic Jammer\n• θ2: Reactive Path Blocker\n• θ3: Optimal Minimax Cut", color="#334155", fontsize=8.5)
    ax.text(64.5, 32.5, "Dynamic Topology Mutations\n• Edge Traversal Cost → ∞", color="#991b1b", fontweight="bold", fontsize=8.5)

    # 4. MISSION EXECUTION BLOCK
    b4 = patches.FancyBboxPatch((92, 28), 24, 25, boxstyle="round,pad=0.2", ec="#10b981", fc="#f0fdf4", lw=1.5)
    ax.add_patch(b4)
    b4_h = patches.FancyBboxPatch((92, 49), 24, 4, boxstyle="round,pad=0.1", ec="#10b981", fc="#10b981", lw=1)
    ax.add_patch(b4_h)
    ax.text(104, 51, "4. Mission Execution", color="white", fontweight="bold", fontsize=11, ha="center", va="center")
    ax.text(93.5, 45, "Dynamic Re-routing", color="#065f46", fontweight="bold", fontsize=9.5)
    ax.text(93.5, 40.5, "• Real-Time Path Recalculation\n• Obstacle Avoidance Detour", color="#334155", fontsize=8.5)
    ax.text(93.5, 35, "Mission Performance", color="#065f46", fontweight="bold", fontsize=9.5)
    ax.text(93.5, 30.5, "• Reward Collection (R_j)\n• Verified Task Completion", color="#334155", fontsize=8.5)

    # 5. BOTTOM FEEDBACK BLOCK
    b5 = patches.FancyBboxPatch((18, 3.5), 84, 20, boxstyle="round,pad=0.2", ec="#06b6d4", fc="#ecfeff", lw=1.5)
    ax.add_patch(b5)
    b5_h = patches.FancyBboxPatch((18, 20), 84, 3.5, boxstyle="round,pad=0.1", ec="#0891b2", fc="#0891b2", lw=1)
    ax.add_patch(b5_h)
    ax.text(60, 21.7, "5. Subjective Belief Filtering & Contingency Branching Layer", color="white", fontweight="bold", fontsize=11, ha="center", va="center")

    # Sub-boxes in Layer 5
    sub1 = patches.FancyBboxPatch((20, 5), 25, 13.5, boxstyle="round,pad=0.1", ec="#a5f3fc", fc="white", lw=1)
    ax.add_patch(sub1)
    ax.text(21, 16.5, "Bayesian Adversary Filter", color="#0e7490", fontweight="bold", fontsize=9)
    ax.text(21, 11, "• Prior: P(θ1)=0.5, P(θ2)=0.5\n• Likelihood L(o|θ) update\n• Recursive Posterior Filter", color="#334155", fontsize=8)

    sub2 = patches.FancyBboxPatch((47.5, 5), 25, 13.5, boxstyle="round,pad=0.1", ec="#a5f3fc", fc="white", lw=1)
    ax.add_patch(sub2)
    ax.text(48.5, 16.5, "Contingency Planning Trees", color="#0e7490", fontweight="bold", fontsize=9)
    ax.text(48.5, 11, "• Primary Path: Optimal under P(θ)\n• Fallback Detour Branches\n• Expected Cost Valuation E[Cost]", color="#334155", fontsize=8)

    sub3 = patches.FancyBboxPatch((75, 5), 25, 13.5, boxstyle="round,pad=0.1", ec="#a5f3fc", fc="white", lw=1)
    ax.add_patch(sub3)
    ax.text(76, 16.5, "Teammate Belief Modeling", color="#0e7490", fontweight="bold", fontsize=9)
    ax.text(76, 11, "• Theory-of-Mind Beliefs B_p^(r)\n• Belief Divergence StdDev\n• KL Disagreement Regularization", color="#334155", fontsize=8)

    # Arrows
    # 1 -> 2
    ax.annotate("", xy=(32.5, 40), xytext=(28.5, 40), arrowprops=dict(arrowstyle="->", color="#2563eb", lw=2.5))
    ax.text(30.5, 41.5, "Bids", color="#2563eb", fontweight="bold", fontsize=8.5, ha="center")

    # 2 -> 3
    ax.annotate("", xy=(62.5, 40), xytext=(58.5, 40), arrowprops=dict(arrowstyle="->", color="#7c3aed", lw=2.5))
    ax.text(60.5, 41.5, "Routes", color="#7c3aed", fontweight="bold", fontsize=8.5, ha="center")

    # 3 -> 4
    ax.annotate("", xy=(91.5, 40), xytext=(87.5, 40), arrowprops=dict(arrowstyle="->", color="#dc2626", lw=2.5))
    ax.text(89.5, 41.5, "Mutation", color="#dc2626", fontweight="bold", fontsize=8.5, ha="center")

    # 4 -> 5 (Observations)
    ax.annotate("", xy=(102, 13.5), xytext=(104, 28), arrowprops=dict(arrowstyle="->", color="#059669", lw=2, connectionstyle="angle,angleA=-90,angleB=180,rad=5"))
    ax.text(105, 20, "Observations", color="#059669", fontweight="bold", fontsize=8.5)

    # 5 -> 1 (State Update)
    ax.annotate("", xy=(16, 28), xytext=(18, 13.5), arrowprops=dict(arrowstyle="->", color="#0891b2", lw=2, connectionstyle="angle,angleA=180,angleB=90,rad=5"))
    ax.text(10, 20, "State Update", color="#0891b2", fontweight="bold", fontsize=8.5, ha="center")

    # 5 -> 2 (Contingency Valuations)
    ax.annotate("", xy=(45.5, 28), xytext=(45.5, 23.5), arrowprops=dict(arrowstyle="->", color="#0891b2", lw=2))
    ax.text(49, 25.5, "Contingency Valuations", color="#0891b2", fontweight="bold", fontsize=8)

    plt.tight_layout()
    save_fig(fig, "pipeline")


def copy_pipeline_and_results():
    # Also generate pipeline and results as PDF/PNG
    # (aca_performance_dashboard.png already exists from main.py)
    dash_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Adversarial-Contingency-Auctions-main", "Adversarial-Contingency-Auctions-main", "ACA", "logs", "plots", "aca_performance_dashboard.png")
    if os.path.exists(dash_src):
        import shutil
        shutil.copyfile(dash_src, os.path.join(OUTPUT_DIR, "results.png"))
        shutil.copyfile(dash_src, os.path.join(OUTPUT_DIR, "fig5_telemetry_dashboard.png"))
        # Also save as PDF
        from PIL import Image
        img = Image.open(dash_src)
        img.convert("RGB").save(os.path.join(OUTPUT_DIR, "results.pdf"))
        img.convert("RGB").save(os.path.join(OUTPUT_DIR, "fig5_telemetry_dashboard.pdf"))
        print("Generated results.pdf and results.png from simulation dashboard.")


if __name__ == "__main__":
    print("Generating figures...")
    create_fig1_motivation()
    create_fig2_adversary_model()
    create_fig3_contingency_tree()
    create_fig4_pipeline()
    create_fig6_boxplots()
    create_fig7_traces()
    copy_pipeline_and_results()
    print("All figures successfully created in:", OUTPUT_DIR)
