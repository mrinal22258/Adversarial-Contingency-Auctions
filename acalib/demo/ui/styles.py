"""
Styling and design system tokens for ACA Mission Control — Clash of Clans (Oct 13, 2026 UI Revamp) Edition.
Features clean orange-yellow 3D beveled buttons, center-stage live base viewport,
4-tab Builder Menu 2.0 drawer, top-right resource/shield counters, and scrollable parchment cards.
"""

# Inline SVG icons (Clean, semantic, accessible)
SVG_ICONS = {
    "overview": """<svg class="nav-svg" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>""",
    "simulate": """<svg class="nav-svg" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>""",
    "experiments": """<svg class="nav-svg" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>""",
    "results": """<svg class="nav-svg" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>""",
    "method": """<svg class="nav-svg" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>""",
    "export": """<svg class="nav-svg" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>""",
    "check": """<svg class="badge-svg" viewBox="0 0 20 20" width="12" height="12" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>""",
    "lock": """<svg class="badge-svg" viewBox="0 0 20 20" width="12" height="12" fill="currentColor"><path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd"/></svg>""",
}

MISSION_CONTROL_CSS = """
:root {
    --font-display: "Trebuchet MS", "Arial Rounded MT Bold", "Segoe UI", system-ui, -apple-system, sans-serif;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;

    /* Clash of Clans Oct 13, 2026 Palette Tokens */
    --coc-bg-deep: #0f172a;
    --coc-bg-hud: #1e293b;
    --coc-parchment: #fdf8ee;
    --coc-parchment-card: #fffdf9;
    --coc-parchment-border: #decbb1;
    --coc-rim-gold: #e09f3e;
    --coc-gold-bright: #ffe169;
    --coc-orange-top: #ffb703;
    --coc-orange-mid: #fb8500;
    --coc-orange-bot: #e85d04;
    --coc-orange-lip: #8a3600;
    --coc-green-top: #9ef01a;
    --coc-green-mid: #38b000;
    --coc-green-bot: #007200;
    --coc-green-lip: #004b23;
    --coc-blue-top: #90e0ef;
    --coc-blue-mid: #0096c7;
    --coc-blue-bot: #023e8a;
    --coc-blue-lip: #011f4b;
    --slate-900: #1e1b18;
    --slate-700: #334155;
    --slate-600: #475569;
}

body, .gradio-container {
    font-family: var(--font-sans) !important;
    background: radial-gradient(circle at 50% 20%, #1e293b 0%, #0b1120 100%) !important;
    color: var(--slate-900) !important;
    max-width: 1560px !important;
    margin: 0 auto !important;
    padding: 10px 16px !important;
}

/* ==================== TOP CHIEF PROFILE & HUD HEADER BAR ==================== */
.header-container {
    background: linear-gradient(180deg, #243046 0%, #151d2c 100%) !important;
    border: 3px solid var(--coc-rim-gold) !important;
    border-radius: 18px !important;
    padding: 12px 18px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.55), inset 0 1.5px 0 rgba(255, 255, 255, 0.22) !important;
    color: #ffffff !important;
}

.header-container h1 {
    font-family: var(--font-display) !important;
    font-size: 22px !important;
    font-weight: 900 !important;
    color: #ffe169 !important;
    text-shadow: 0 2px 0 #000000, -1px -1px 0 #000000, 1px -1px 0 #000000 !important;
    margin: 0 0 4px 0 !important;
    letter-spacing: 0.02em !important;
}

.header-container p, .header-container blockquote {
    color: #e2e8f0 !important;
    margin: 2px 0 !important;
    border-left-color: #ffb703 !important;
}

/* ==================== CLASH OF CLANS BEVELED NAVIGATION TABS ==================== */
#main-tabs > div[role="tablist"],
#main-tabs > .tab-nav,
.header-container + .tabs > div[role="tablist"] {
    display: flex !important;
    flex-wrap: wrap !important;
    overflow: visible !important;
    gap: 8px !important;
    border-bottom: 3px solid var(--coc-rim-gold) !important;
    background: rgba(15, 23, 42, 0.85) !important;
    padding: 8px 12px 6px 12px !important;
    border-radius: 16px 16px 0 0 !important;
    margin-bottom: 0 !important;
}

#main-tabs > div[role="tablist"] > button,
#main-tabs > .tab-nav button {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
    font-family: var(--font-display) !important;
    font-size: 12.5px !important;
    font-weight: 900 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    padding: 8px 16px !important;
    color: #e2e8f0 !important;
    text-shadow: 0 1.5px 0 #000000 !important;
    background: linear-gradient(180deg, #334155 0%, #1e293b 100%) !important;
    border: 2px solid #0f172a !important;
    border-radius: 12px !important;
    box-shadow: inset 0 1.5px 0 rgba(255,255,255,0.25), 0 3px 0 #090d16 !important;
    transition: transform 0.08s ease, filter 0.12s ease, box-shadow 0.08s ease !important;
    margin-bottom: 2px !important;
}

#main-tabs > div[role="tablist"] > button:hover,
#main-tabs > .tab-nav button:hover {
    filter: brightness(1.12) !important;
    color: #ffe169 !important;
}

/* Active Selected Tab = Signature Clash of Clans Orange-Yellow Glossy Bevel Button */
#main-tabs > div[role="tablist"] > button.selected,
#main-tabs > .tab-nav button.selected {
    color: #ffffff !important;
    text-shadow: 0 2px 0 #000000, -1px -1px 0 #000000, 1px -1px 0 #000000 !important;
    background: linear-gradient(180deg, #ffe169 0%, #ffa200 48%, #e85d04 100%) !important;
    border: 2.5px solid #2b1400 !important;
    box-shadow:
        inset 0 2.5px 0 rgba(255, 255, 255, 0.75),
        0 4px 0 var(--coc-orange-lip),
        0 6px 12px rgba(0, 0, 0, 0.45) !important;
    transform: translateY(-1px) !important;
}

/* Main Tab Content Panel (Warm Parchment-Framed Command Board) */
#main-tabs > div[role="tabpanel"],
#main-tabs > .tabitem {
    background: var(--coc-parchment) !important;
    border: 3px solid var(--coc-rim-gold) !important;
    border-top: none !important;
    border-radius: 0 0 20px 20px !important;
    padding: 16px !important;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.65) !important;
}

/* ==================== SUB-TABS (BUILDER MENU 2.0 & BATTLE LOG DRAWERS) ==================== */
.coc-drawer-box div[role="tablist"],
.coc-drawer-box .tab-nav {
    display: flex !important;
    flex-wrap: nowrap !important;
    gap: 4px !important;
    border-bottom: 2px solid var(--coc-rim-gold) !important;
    background: #0f172a !important;
    padding: 5px 6px !important;
    border-radius: 10px 10px 0 0 !important;
    overflow: visible !important;
    margin-bottom: 0 !important;
    width: 100% !important;
}

.coc-drawer-box div[role="tablist"] > button,
.coc-drawer-box .tab-nav button {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-family: var(--font-display) !important;
    font-size: 11.5px !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.02em !important;
    padding: 6px 4px !important;
    color: #94a3b8 !important;
    background: #1e293b !important;
    border: 1.5px solid #334155 !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    text-shadow: none !important;
    white-space: nowrap !important;
    flex: 1 1 0px !important;
    min-width: 0 !important;
    margin: 0 !important;
}

.coc-drawer-box div[role="tablist"] > button:hover {
    filter: brightness(1.15) !important;
    color: #fde68a !important;
}

.coc-drawer-box div[role="tablist"] > button.selected {
    color: #ffffff !important;
    background: linear-gradient(180deg, #ffb703 0%, #e85d04 100%) !important;
    border: 1.5px solid #2b1400 !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 2px 4px rgba(0,0,0,0.3) !important;
    text-shadow: 0 1px 0 #000000 !important;
}

.coc-drawer-box div[role="tabpanel"],
.coc-drawer-box .tabitem {
    background: #ffffff !important;
    border: 2px solid var(--coc-rim-gold) !important;
    border-top: none !important;
    border-radius: 0 0 12px 12px !important;
    padding: 12px !important;
    box-shadow: none !important;
}

/* ==================== SIGNATURE ORANGE-YELLOW BEVELED ACTION BUTTONS ==================== */
.btn-indigo-primary, button.primary {
    font-family: var(--font-display) !important;
    font-weight: 900 !important;
    font-size: 14px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    color: #ffffff !important;
    text-shadow: 0 2px 0 #000000, -1px -1px 0 #000000, 1px -1px 0 #000000 !important;
    background: linear-gradient(180deg, #ffe169 0%, #ffa200 45%, #e85d04 100%) !important;
    border: 2.5px solid #2b1400 !important;
    border-radius: 14px !important;
    padding: 11px 18px !important;
    box-shadow:
        inset 0 2.5px 0 rgba(255, 255, 255, 0.75),
        inset 0 -2px 0 rgba(0, 0, 0, 0.25),
        0 5px 0 var(--coc-orange-lip),
        0 8px 16px rgba(0, 0, 0, 0.4) !important;
    transition: transform 0.08s ease, box-shadow 0.08s ease, filter 0.12s ease !important;
    cursor: pointer !important;
}

.btn-indigo-primary:hover, button.primary:hover {
    filter: brightness(1.08) !important;
}

.btn-indigo-primary:active, button.primary:active {
    transform: translateY(4px) !important;
    box-shadow:
        inset 0 2px 0 rgba(255, 255, 255, 0.6),
        0 1px 0 var(--coc-orange-lip),
        0 3px 6px rgba(0, 0, 0, 0.4) !important;
}

/* Secondary Beveled Button (Royal Blue / Emerald Clash Style) */
.btn-indigo-outline, button.secondary {
    font-family: var(--font-display) !important;
    font-weight: 900 !important;
    font-size: 13px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.03em !important;
    color: #ffffff !important;
    text-shadow: 0 1.5px 0 #000000, -1px -1px 0 #000000, 1px -1px 0 #000000 !important;
    background: linear-gradient(180deg, #9ef01a 0%, #38b000 50%, #007200 100%) !important;
    border: 2.5px solid #002911 !important;
    border-radius: 14px !important;
    padding: 10px 16px !important;
    box-shadow:
        inset 0 2.5px 0 rgba(255, 255, 255, 0.72),
        0 5px 0 var(--coc-green-lip),
        0 7px 14px rgba(0, 0, 0, 0.35) !important;
    transition: transform 0.08s ease, box-shadow 0.08s ease, filter 0.12s ease !important;
}

.btn-indigo-outline:hover, button.secondary:hover {
    filter: brightness(1.08) !important;
}

.btn-indigo-outline:active, button.secondary:active {
    transform: translateY(4px) !important;
    box-shadow: inset 0 2px 0 rgba(255,255,255,0.6), 0 1px 0 var(--coc-green-lip) !important;
}

/* Step & Scrubber Control Buttons (Gold-Trimmed Tactical Controls) */
.btn-control {
    font-family: var(--font-display) !important;
    font-weight: 900 !important;
    font-size: 12.5px !important;
    text-transform: uppercase !important;
    color: #ffffff !important;
    text-shadow: 0 1.5px 0 #000000 !important;
    background: linear-gradient(180deg, #48cae4 0%, #0096c7 52%, #023e8a 100%) !important;
    border: 2px solid #011638 !important;
    border-radius: 12px !important;
    padding: 8px 14px !important;
    box-shadow:
        inset 0 2px 0 rgba(255, 255, 255, 0.68),
        0 4px 0 var(--coc-blue-lip),
        0 5px 10px rgba(0, 0, 0, 0.3) !important;
}

.btn-control:hover {
    filter: brightness(1.1) !important;
}

.btn-control:active {
    transform: translateY(3px) !important;
    box-shadow: inset 0 1.5px 0 rgba(255,255,255,0.5), 0 1px 0 var(--coc-blue-lip) !important;
}

/* ==================== TOP RESOURCE & SHIELD KPI STRIP (COC RESOURCE PILLS) ==================== */
.kpi-row {
    display: grid !important;
    grid-template-columns: repeat(7, 1fr) !important;
    gap: 8px !important;
    width: 100% !important;
    margin-bottom: 12px !important;
}

.kpi-card {
    min-width: 0 !important;
    overflow: hidden !important;
    height: 100% !important;
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
    border: 2px solid var(--coc-rim-gold) !important;
    border-top: 3.5px solid #ffb703 !important;
    border-radius: 12px !important;
    padding: 8px 4px !important;
    text-align: center !important;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.15) !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
}

.kpi-val {
    font-family: var(--font-display) !important;
    font-variant-numeric: tabular-nums !important;
    font-size: 15px !important;
    font-weight: 900 !important;
    color: #ffe169 !important;
    text-shadow: 0 1.5px 0 #000000 !important;
    line-height: 1.2 !important;
    white-space: nowrap !important;
}

.kpi-sub {
    font-size: 10.5px !important;
    color: #94a3b8 !important;
    font-weight: 700 !important;
}

.kpi-lbl {
    font-family: var(--font-display) !important;
    font-size: 10px !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    color: #cbd5e1 !important;
    margin-top: 3px !important;
    white-space: nowrap !important;
    text-overflow: ellipsis !important;
    overflow: hidden !important;
    max-width: 100% !important;
}

/* ==================== SCROLLABLE BUILDER MENU 2.0 & BATTLE LOG DRAWERS ==================== */
.coc-drawer-box {
    background: var(--coc-parchment-card) !important;
    border: 2.5px solid var(--coc-rim-gold) !important;
    border-radius: 16px !important;
    padding: 12px !important;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08) !important;
}

.coc-scroll-pane {
    max-height: 520px !important;
    overflow-y: auto !important;
    padding-right: 6px !important;
}

.coc-scroll-pane::-webkit-scrollbar {
    width: 9px;
}
.coc-scroll-pane::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.06);
    border-radius: 8px;
}
.coc-scroll-pane::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #ffb703, #e85d04);
    border-radius: 8px;
    border: 1.5px solid #2b1400;
}

/* Center Stage Base Frame */
.coc-base-stage {
    background: #131d31 !important;
    border: 3px solid var(--coc-rim-gold) !important;
    border-radius: 18px !important;
    padding: 12px !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35), inset 0 0 40px rgba(0, 0, 0, 0.4) !important;
}

.coc-base-stage h3 {
    color: #ffe169 !important;
    font-family: var(--font-display) !important;
    text-shadow: 0 1.5px 0 #000000 !important;
    margin: 0 0 6px 0 !important;
}

/* Form inputs & labels */
.gradio-container label,
.gradio-container .block label,
.gradio-container .block > span,
.gradio-container .form > label {
    font-family: var(--font-display) !important;
    text-transform: uppercase !important;
    font-size: 11px !important;
    letter-spacing: 0.04em !important;
    font-weight: 800 !important;
    color: #334155 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Result Banner */
.result-banner {
    background: linear-gradient(90deg, #fffbeb 0%, #fef3c7 100%) !important;
    border: 2px solid #f59e0b !important;
    border-left: 6px solid #e85d04 !important;
    border-radius: 12px !important;
    padding: 10px 14px !important;
    margin-bottom: 10px !important;
}

.result-sentence {
    font-size: 13px !important;
    font-weight: 800 !important;
    color: #78350f !important;
}

/* Status Badges */
.badge-tag {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    padding: 3px 9px !important;
    border-radius: 8px !important;
    font-family: var(--font-display) !important;
    font-size: 11px !important;
    font-weight: 900 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    margin-right: 6px !important;
    text-shadow: 0 1px 0 #000 !important;
}

.badge-real {
    background: linear-gradient(180deg, #ffd166, #fb8500) !important;
    color: #ffffff !important;
    border: 1.5px solid #2b1400 !important;
}

.badge-sim {
    background: linear-gradient(180deg, #48cae4, #0077b6) !important;
    color: #ffffff !important;
    border: 1.5px solid #023e8a !important;
}

.badge-verified {
    background: linear-gradient(180deg, #52b788, #2d6a4f) !important;
    color: #ffffff !important;
    border: 1.5px solid #081c15 !important;
}

/* Accessible focus visible outlines */
button:focus-visible, input:focus-visible, select:focus-visible {
    outline: 2.5px solid #ffb703 !important;
    outline-offset: 2px !important;
}

@media (max-width: 1024px) {
    .kpi-row {
        grid-template-columns: repeat(4, 1fr) !important;
    }
}

@media (max-width: 480px) {
    .kpi-row {
        grid-template-columns: repeat(2, 1fr) !important;
    }
}
"""
