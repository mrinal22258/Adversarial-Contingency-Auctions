"""
Adversarial Contingency Auctions (ACA) — Mission Control Explorer.
Thin launcher for the modularized Gradio web interface.
"""

import os
import sys

# Ensure repository root is in sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.demo.ui.layout import build_app, create_app
from acalib.demo.ui.callbacks import (
    run_simulation_wrapper,
    get_metrics_table,
    plot_simulation_state,
)

# Canonical application instance
demo = build_app()

if __name__ == "__main__":
    server_port = int(os.environ.get("PORT", 7860))
    # Default to 127.0.0.1 for seamless local browser access on Windows/macOS;
    # containerized deployments can override via HOST=0.0.0.0.
    server_name = os.environ.get("HOST", "127.0.0.1")
    print(f"[*] Starting ACA Mission Control on {server_name}:{server_port}...")
    print(f"[*] Browser URL: http://localhost:{server_port} or http://127.0.0.1:{server_port}")
    show_error = os.environ.get("ACA_DEBUG") == "1"
    demo.launch(
        server_name=server_name,
        server_port=server_port,
        show_error=show_error,
    )

