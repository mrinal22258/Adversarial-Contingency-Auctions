"""
Compatibility entrypoint to generate paper figures directly from logged empirical data.
Calls experiments/make_figures.py and updates static/images/ for the manuscript and web visualizer.
"""

import os
import sys
import shutil
import pandas as pd

from experiments.make_figures import main as generate_figures_main
from experiments.make_tables import main as generate_tables_main

if __name__ == "__main__":
    csv_path = "results/raw_results.csv"
    if not os.path.exists(csv_path):
        print(f"Results CSV not found at {csv_path}. Running quick benchmark sweep first...")
        import subprocess
        subprocess.run([sys.executable, "experiments/run_sweep.py", "--fast", "--output", csv_path], check=True)

    print("Generating LaTeX tables from logged CSV data...")
    generate_tables_main()

    print("Generating publication figures from logged CSV data...")
    generate_figures_main()

    # Also copy figures to static/images for web visualizer compatibility
    os.makedirs("static/images", exist_ok=True)
    for fname in ["fig_completion_conflicts.png", "fig_welfare_messages.png"]:
        src = os.path.join("results", fname)
        dst = os.path.join("static", "images", fname)
        if os.path.exists(src):
            shutil.copyfile(src, dst)
            print(f"Copied {src} -> {dst}")

    print("\nAll paper tables and figures successfully regenerated from empirical data.")
