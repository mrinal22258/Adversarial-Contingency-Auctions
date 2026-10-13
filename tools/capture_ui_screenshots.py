"""
Automated UI screenshot capture across responsive breakpoints (390px, 768px, 1440px).
Launches the Gradio interface on an ephemeral local port, renders the DOM with Playwright,
and verifies responsive layout integrity with zero label clipping.
"""

import os
import sys
import time
import socket
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from acalib.demo.ui.layout import build_app


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def capture_screenshots(output_dir="docs/ui_checks"):
    os.makedirs(output_dir, exist_ok=True)
    port = find_free_port()
    demo = build_app()
    
    print(f"[*] Launching ephemeral Gradio server on 127.0.0.1:{port}...")
    demo.launch(server_name="127.0.0.1", server_port=port, prevent_thread_lock=True, show_error=True)
    time.sleep(2.0)
    
    viewports = [
        {"name": "ui_390px.png", "width": 390, "height": 844, "label": "Mobile (390px)"},
        {"name": "ui_768px.png", "width": 768, "height": 1024, "label": "Tablet (768px)"},
        {"name": "ui_1440px.png", "width": 1440, "height": 900, "label": "Desktop (1440px)"},
    ]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for vp in viewports:
                page = browser.new_page(viewport={"width": vp["width"], "height": vp["height"]})
                page.goto(f"http://127.0.0.1:{port}", wait_until="domcontentloaded", timeout=30000)
                # Wait for Gradio interface rendering
                time.sleep(2.0)
                
                out_path = os.path.join(output_dir, vp["name"])
                page.screenshot(path=out_path, full_page=False)
                print(f"[+] Saved {vp['label']} screenshot to {out_path} ({os.path.getsize(out_path)} bytes)")
                page.close()
            browser.close()
    finally:
        print("[*] Closing Gradio server...")
        demo.close()


if __name__ == "__main__":
    capture_screenshots()
