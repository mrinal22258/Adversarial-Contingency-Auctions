"""
Playwright End-to-End Responsive Test Suite for ACA Mission Control UI.
Tests Gradio UI across Desktop (1920x1080), Laptop (1366x768), Tablet (768x1024), and Mobile (390x844).
"""

import os
import sys
import time
import socket
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app import build_app


def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_ui_responsive_tests():
    port = find_free_port()
    print(f"[*] Launching Gradio Mission Control on port {port}...")
    demo = build_app()
    app_proc = demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        prevent_thread_lock=True,
        show_error=True,
    )
    time.sleep(2.0)

    url = f"http://127.0.0.1:{port}"
    print(f"[*] Connecting Playwright to {url}...")

    viewports = [
        ("Desktop", 1920, 1080),
        ("Laptop", 1366, 768),
        ("Tablet", 768, 1024),
        ("Mobile", 390, 844),
    ]

    results = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for vp_name, width, height in viewports:
                print(f"[*] Testing Viewport: {vp_name} ({width}x{height})...")
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_selector("h1", timeout=15000)

                # Verify Title / Header
                header_text = page.locator("h1").first.text_content()
                assert "Adversarial Contingency Auctions" in header_text, f"Header mismatch: {header_text}"

                # Verify KPI Cards exist
                kpi_cards = page.locator(".kpi-card")
                kpi_count = kpi_cards.count()
                assert kpi_count >= 7, f"Expected at least 7 KPI cards, found {kpi_count}"

                # Verify Status Badges
                badges = page.locator(".badge-tag")
                badge_count = badges.count()
                assert badge_count >= 2, f"Expected status badges, found {badge_count}"

                # Verify Tab list is present
                tabs = page.locator("button[role='tab']")
                tab_count = tabs.count()
                if width >= 1024:
                    assert tab_count >= 6, f"Expected 6 tabs on {vp_name}, found {tab_count}"
                else:
                    assert tab_count >= 1, f"Expected tab navigation on {vp_name}, found {tab_count}"

                # Verify Buttons
                run_btn = page.locator("button:has-text('Run Simulation')")
                assert run_btn.is_visible(), "Run Simulation button not visible"

                results[vp_name] = {
                    "width": width,
                    "height": height,
                    "kpi_cards": kpi_count,
                    "badges": badge_count,
                    "tabs": tab_count,
                    "status": "PASS",
                }
                context.close()
            browser.close()
    finally:
        print("[*] Shutting down Gradio test server...")
        demo.close()

    print("\n================ Responsive Test Results ================")
    for vp, data in results.items():
        print(f"  [{data['status']}] {vp:10s} ({data['width']}x{data['height']}): {data['kpi_cards']} KPI cards, {data['tabs']} tabs, {data['badges']} badges")
    print("=========================================================")
    return results


if __name__ == "__main__":
    run_ui_responsive_tests()
