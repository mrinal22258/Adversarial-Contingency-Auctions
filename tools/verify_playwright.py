"""
Verification V2: Playwright automated testing across viewports.
Viewports:
- Desktop: 1440 x 900
- Tablet: 1024 x 768
- Mobile: 390 x 844

Assertions:
1. All 6 tabs visible and clickable by role name:
   ["Telemetry", "Summary", "Compare", "Real SITL", "Method", "Export"]
2. No tab hidden behind "..." overflow.
3. No horizontal overflow (document.scrollWidth <= innerWidth).
4. KPI strip labels not wrapped mid-word (height check).
5. Page height < 1600px at 1440x900.
6. Saves high-res screenshots for each tab to docs/screenshots/.
"""

import os
import sys
import time
import subprocess
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(REPO_ROOT, "docs", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

TAB_NAMES = ["Telemetry", "Summary", "Compare", "Real SITL", "Method", "Export"]
VIEWPORTS = [
    {"name": "desktop_1440", "width": 1440, "height": 900},
    {"name": "tablet_1024", "width": 1024, "height": 768},
    {"name": "mobile_390", "width": 390, "height": 844},
]


def run_playwright_verifications():
    print("=================== PLAYWRIGHT VERIFICATION (V2) ===================")
    
    # 1. Start App server
    print("Starting app.py server on port 7860...")
    server_proc = subprocess.Popen(
        [sys.executable, os.path.join(REPO_ROOT, "app.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
    )
    
    # Wait for server to become responsive
    import urllib.request
    print("Waiting for server to become responsive...")
    server_ready = False
    for i in range(25):
        try:
            with urllib.request.urlopen("http://127.0.0.1:7860") as resp:
                if resp.status == 200:
                    server_ready = True
                    print(f"Server ready after {i+1}s!")
                    break
        except Exception:
            time.sleep(1)
    
    if not server_ready:
        out, err = server_proc.communicate(timeout=2)
        print("Server stdout:", out.decode(errors="ignore"))
        print("Server stderr:", err.decode(errors="ignore"))
        raise RuntimeError("Gradio server failed to start on port 7860")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            for vp in VIEWPORTS:
                v_name = vp["name"]
                w, h = vp["width"], vp["height"]
                print(f"\n--- Testing Viewport: {v_name} ({w}x{h}) ---")
                
                context = browser.new_context(viewport={"width": w, "height": h})
                page = context.new_page()
                
                # Navigate to local app
                page.goto("http://127.0.0.1:7860", wait_until="domcontentloaded", timeout=15000)
                page.wait_for_selector(".gradio-container", timeout=15000)
                page.wait_for_timeout(2000)
                
                # Verify no horizontal scrollbar / overflow
                scroll_width = page.evaluate("document.documentElement.scrollWidth")
                inner_width = page.evaluate("window.innerWidth")
                print(f"  Horizontal check: scrollWidth={scroll_width}, innerWidth={inner_width}")
                assert scroll_width <= inner_width + 5, f"Horizontal overflow detected: {scroll_width} > {inner_width}"

                # Run simulation if on desktop
                if v_name == "desktop_1440":
                    print("  Triggering 'Run Simulation'...")
                    run_btn = page.get_by_role("button", name="Run Simulation")
                    assert run_btn.is_visible(), "Run Simulation button must be visible"
                    run_btn.click()
                    
                    # Wait for run to finish (look for Run Result banner)
                    page.wait_for_selector(".result-banner", timeout=20000)
                    print("  Run finished! Banner appeared.")
                    
                    # Check page height < 1600px at 1440x900
                    doc_height = page.evaluate("document.documentElement.scrollHeight")
                    print(f"  Page height at 1440px: {doc_height}px (budget: < 1600px)")
                    assert doc_height < 1600, f"Page height {doc_height}px exceeds 1600px budget!"

                    # Check KPI strip labels
                    kpi_labels = page.query_selector_all(".kpi-lbl")
                    assert len(kpi_labels) >= 7, f"Expected 7 KPI labels, found {len(kpi_labels)}"
                    for kl in kpi_labels:
                        box = kl.bounding_box()
                        if box:
                            assert box["height"] <= 24, f"KPI label wrapped unexpectedly: height={box['height']}"

                # Verify all 6 tabs visible and clickable by role name
                print("  Verifying 6 tabs...")
                for tab_name in TAB_NAMES:
                    tab_elem = page.get_by_role("tab", name=tab_name)
                    tab_elem.scroll_into_view_if_needed()
                    assert tab_elem.is_visible(), f"Tab '{tab_name}' is not visible in {v_name}!"
                    tab_elem.click()
                    page.wait_for_timeout(800)
                    
                    # Capture tab screenshot
                    clean_name = tab_name.lower().replace(" ", "_")
                    ss_path = os.path.join(SCREENSHOTS_DIR, f"{v_name}_{clean_name}.png")
                    page.screenshot(path=ss_path, full_page=False)
                    print(f"    Saved: {os.path.basename(ss_path)}")

                # Check that no overflow "..." tab exists
                dots_tab = page.query_selector("button:has-text('...')")
                if dots_tab:
                    assert not dots_tab.is_visible(), "Tab overflow '...' button should not be visible!"

                context.close()
                print(f"  Viewport {v_name} PASSED all assertions!")

            browser.close()
            print("\nALL PLAYWRIGHT ASSERTIONS (V2) PASSED SUCCESSFULLY!")

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except Exception:
            server_proc.kill()


if __name__ == "__main__":
    run_playwright_verifications()
