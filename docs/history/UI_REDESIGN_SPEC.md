# UI Redesign Specification: Adversarial Contingency Auctions Mission Control (Clash of Clans Oct 13, 2026 HUD Edition)

**Document Version:** 2.0.0  
**Target Application:** `app.py` (Gradio Mission Control Web Application)  
**Theme:** Clash of Clans (Oct 13, 2026 UI Revamp — Builder Menu 2.0 & Mirrored Battle/Build HUD)  
**Design Standard:** WCAG 2.1 Level AA Compliance  

---

## 1. Executive Vision & Architectural Aesthetic

Inspired by the October 13, 2026 Clash of Clans UI rework ("Builder Menu 2.0"), the Adversarial Contingency Auctions (ACA) Gradio interface eliminates vertical accordion clutter by dedicating the center stage to the live **Robot Graph Simulation Base** while organizing all controls, telemetry, and benchmarks into clean, scrollable, tabbed HUD drawers and beveled orange-yellow action buttons.

### Core Aesthetic Pillars
1. **Tactile Orange-Yellow 3D Beveled Buttons:** High-contrast amber-gold gradients (`#ffe169` → `#ffa200` → `#e85d04`), dark bronze borders (`#2b1400`), specular top inner highlights, and 3D bottom lip shadows (`#8a3600`).
2. **Center-Stage Live Base Viewport:** The real map topology (OSMnx Boston road network or MovingAI warehouse) anchors the center workspace (`#131d31` tactical base plate framed in `#e09f3e` gold).
3. **Builder Menu 2.0 (4-Tab Configuration Hub):** Replaces the old 5 stacked left accordions with 4 compact tabs (`1. Base Map`, `2. Fleet & Army`, `3. ACA Gear`, `4. Adversary & Comms`).
4. **4-Tab Battle Log & Telemetry Inspector:** Replaces the endless vertical stack of tables below the map with 4 dedicated tabs (`1. Event Stream`, `2. Step Metrics`, `3. Mission Narrative & Failures`, `4. CLI Repro`).
5. **Top Resource & Pinsker Shield Strip:** 7 tabular counter cards styled as dark-slate resource pills with gold top rims and glowing gold numerals.
