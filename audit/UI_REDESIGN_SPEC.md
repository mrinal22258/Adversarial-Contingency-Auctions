# UI Redesign Specification: Adversarial Contingency Auctions Mission Control

**Document Version:** 1.0.0  
**Target Application:** `app.py` (Gradio Mission Control Web Application)  
**Theme:** Mission Control / Dark Calm Command Center  
**Design Standard:** WCAG 2.1 Level AA Compliance  

---

## 1. Executive Vision & Architectural Aesthetic

The Adversarial Contingency Auctions (ACA) interactive web application is designed as a mission-critical multi-robot operations center ("Mission Control"). The redesign replaces generic prototype styling with a production-grade, dark-calm control room interface engineered for roboticists, autonomy researchers, and systems operators.

### Core Aesthetic Pillars
1. **Calm, Low-Fatigue Color Palette:** Deep space canvas (`#0b0f19`), slate card backdrops (`#111827`), subtle cool-gray borders (`#1f2937`), and electric indigo/cyan accents (`#6366f1`, `#06b6d4`).
2. **Center-Stage Spatial Telemetry:** The real map topology (OSMnx Boston road network or MovingAI warehouse) anchors the center workspace, flanked by mission controls and live telemetry.
3. **High-Density, Tabular KPI Strip:** Instant mission situational awareness via single-line tabular numeric cards displaying completion, conflicts, net welfare, messages, and contingency commitments.
4. **Accessible, Dual-Encoded State Indicators:** No color-only signals. Every system state combines a distinct geometric shape/icon with high-contrast text and semantic color.
5. **Zero Raw Browser Defaults:** All buttons, dropdowns, sliders, and accordions are custom-styled with consistent rounded micro-radii, crisp hover states, and explicit focus rings.

---

## 2. Component Hierarchy & Workspace Layout

```
+---------------------------------------------------------------------------------------------------+
| HEADER BAR: Title | Mission Status [ACTIVE/IDLE] | Map Provenance Badge [VERIFIED] | Clock / Tick |
+---------------------------------------------------------------------------------------------------+
| PRIMARY KPI STRIP (7 Tabular Cards):                                                              |
| [Tasks: 15/15] [Conflicts: 0] [Net Welfare: +142.8] [Messages: 48] [Safe Claims: 12] [Detours: 3] |
+---------------------------------------------------------------------------------------------------+
| WORKSPACE TABS: [1. Live Telemetry] [2. Summary] [3. Paired Benchmark] [4. SITL] [5. Traces] [6. Matrix]
+------------------------------------+------------------------------------+-------------------------+
| LEFT: Control Drawer               | CENTER: Spatial Mission View       | RIGHT: Event Telemetry  |
| - Topology Selector (Boston/Wh)   | - Interactive Graph / Map Canvas   | - Live Event Stream     |
| - Fleet & Task Allocation Specs   | - Nominal Paths (Cyan Solid)       | - Robot State Table     |
| - Adversary & Comm Regime Sliders | - Adversarial Blockage (Red Hash)  | - Safe-Claim Monotonicity|
| - Mission Playback Actions (Play) | - Contingency Branch (Amber Dash)  | - Communication Log     |
+------------------------------------+------------------------------------+-------------------------+
| FOOTER: Data Lineage | SHA-256 Hashes | Model Commit Tag | Proof Reference Links                  |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Design Tokens & Visual Hierarchy

### 3.1 Color Palette
| Token | Hex Code | Semantic Role |
|---|---|---|
| `--color-canvas-bg` | `#0b0f19` | Main application background |
| `--color-panel-bg` | `#111827` | Cards, drawers, and modal containers |
| `--color-subpanel-bg` | `#1e293b` | Form inputs, dropdown fields, data tables |
| `--color-border-subtle` | `#334155` | Default component borders |
| `--color-border-focus` | `#6366f1` | Active focus rings and highlighted cards |
| `--color-accent-primary` | `#6366f1` | Primary CTA, tabs, and key accents |
| `--color-accent-cyan` | `#06b6d4` | Nominal paths and telemetry markers |
| `--color-status-success` | `#10b981` | Safe claims, completed tasks, verified provenance |
| `--color-status-warning` | `#f59e0b` | Contingency branch detours, consensus fallbacks |
| `--color-status-danger` | `#ef4444` | Adversarial blockages, detected conflicts |
| `--color-text-primary` | `#f8fafc` | Main headings, KPI values, high-contrast labels |
| `--color-text-secondary` | `#94a3b8` | Metadata, unit labels, secondary descriptions |
| `--color-text-muted` | `#64748b` | Disabled states, timestamps, borders |

### 3.2 Typography
- **Primary Body Font:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, Helvetica, Arial, sans-serif`
- **Monospace & KPI Values:** `ui-monospace, SFMono-Regular, "JetBrains Mono", Menlo, Consolas, monospace`
- **Tabular Numerics:** `font-variant-numeric: tabular-nums;` enabled on all metric cards and tables.

### 3.3 Spatial Path Visual Differentiation
- **Nominal Planned Path:** Solid line (`#06b6d4`, width 3.0px, solid).
- **Adversarial Blockage:** Bold cross-hatch with alert marker (`#ef4444`, width 4.5px, marker `X`).
- **Contingency Branch Taken:** Dashed amber line (`#f59e0b`, width 3.0px, dasharray `6,4`).
- **Safe Claim Territory:** Light cyan glow envelope (`rgba(6, 182, 212, 0.15)`).

---

## 4. Dual-Coded System State Indicators

To guarantee accessibility and zero reliance on color alone, all operational states utilize dual encoding (icon + distinct geometric shape + text + semantic color):

| State | Indicator Symbol | Shape / Border | Background & Color | Accessibility Text |
|---|---|---|---|---|
| **ACTIVE** | `[●] RUNNING` | Solid Pill (`border-radius: 9999px`) | Green tint (`#064e3b` / `#34d399`) | "System active and allocating tasks" |
| **IDLE** | `[◼] STANDBY` | Square Pill (`border-radius: 4px`) | Slate tint (`#1e293b` / `#94a3b8`) | "System standing by" |
| **BLOCKED** | `[▲] BLOCKED` | Triangle Badge (`border: 2px solid #ef4444`) | Red tint (`#7f1d1d` / `#f87171`) | "Adversarial interdiction detected" |
| **CONTINGENCY** | `[◆] RE-PLAN` | Diamond Badge (`border: 2px solid #f59e0b`) | Amber tint (`#78350f` / `#fbbf24`) | "Executing Phase-2 contingency detour" |
| **VERIFIED MAP** | `[✓] PROVENANCE` | Shield / Check Badge | Emerald tint (`#064e3b` / `#6ee7b7`) | "Cryptographically verified OSMnx/MovingAI map" |

---

## 5. Responsive Breakpoint Matrix

The mission control interface dynamically adjusts across screen geometries:

| Viewport Category | Resolution | Layout Behavior |
|---|---|---|
| **Ultra-Wide / Desktop** | `>= 1440px` | Full 3-column control room: Left Drawer (300px), Center Stage Map (Flex 1), Right Telemetry (360px). KPI strip renders 7 cards in 1 row. |
| **Laptop Standard** | `1024px - 1439px` | 2-column layout: Left Drawer collapses into sticky sidebar (280px); Map & Telemetry stack vertically or tabulate. KPI strip wraps to 4 + 3 cards. |
| **Tablet Viewport** | `768px - 1023px` | Stacked single-column hierarchy: Control accordions collapse by default; Center Stage Map spans 100% width; Telemetry placed beneath map. |
| **Mobile / Compact** | `< 768px` | Mobile command layout: KPI strip displays 2x4 grid; Map scales to full mobile width; Touch-friendly playback buttons (min 44px tap target). |

---

## 6. Accessibility & Usability Checklist (WCAG AA Compliance)

- [x] **Contrast Ratio:** Normal text contrast >= 5.8:1 against `#0b0f19` / `#111827` (exceeds WCAG 4.5:1 requirement).
- [x] **Large Text & Headings:** Contrast ratio >= 8.2:1 against background.
- [x] **Non-Color State Communication:** All status badges incorporate unique glyphs (`[●]`, `[◼]`, `[▲]`, `[◆]`, `[✓]`) and text descriptions.
- [x] **Keyboard Navigation:** Explicit `:focus-visible` styling with `2px solid #6366f1` and `2px` offset on all buttons, inputs, and sliders.
- [x] **No Flashing / Calming Transitions:** Transitions standardized to `150ms ease-in-out`; zero strobing animations.
- [x] **Touch Targets:** All interactive buttons possess minimum dimensions of `36px` on desktop and `44px` on mobile.

---

## 7. Gradio Implementation Architecture (`app.py`)

1. **Custom Root Injection:** Deliver the full control-room CSS design tokens via `MISSION_CONTROL_CSS` injected into `gr.Blocks(css=MISSION_CONTROL_CSS, theme=gr.themes.Base())`.
2. **Stable DOM Selectors:** Provide explicit `elem_id` and `elem_classes` attributes for all mission-critical components:
   - `#mission-header`, `#kpi-strip`, `#control-drawer`, `#map-center-stage`, `#event-stream`, `#provenance-badge`.
3. **Reactive State Sync:**
   - Real-time updates push simulation tick progress to the KPI row, narrative event log, and map visualization in a synchronized atomic step.
4. **Offline Resilience:** All OSMnx Boston GraphML and MovingAI warehouse topologies load locally with SHA-256 provenance verification; zero external CDN dependencies.
