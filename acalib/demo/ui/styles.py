"""
Styling and design system tokens for ACA Mission Control.
Calm indigo aesthetic, system fonts, tabular figures, and zero emojis.
Strict responsive layout for 1440px, 1024px, and 390px viewports.
"""

# Inline SVG icons (Clean, semantic, accessible, zero emoji)
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
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    --indigo-50: #eef2ff;
    --indigo-100: #e0e7ff;
    --indigo-200: #c7d2fe;
    --indigo-600: #4f46e5;
    --indigo-700: #4338ca;
    --slate-50: #f8fafc;
    --slate-100: #f1f5f9;
    --slate-200: #e2e8f0;
    --slate-300: #cbd5e1;
    --slate-600: #475569;
    --slate-700: #334155;
    --slate-800: #1e293b;
    --slate-900: #0f172a;
    --emerald-600: #059669;
    --rose-600: #e11d48;
    --amber-600: #d97706;
}

body, .gradio-container {
    font-family: var(--font-sans) !important;
    background-color: #f8fafc !important;
    color: var(--slate-900) !important;
}

/* Header & Shell Title */
.header-container {
    margin-bottom: 12px !important;
    padding-bottom: 8px !important;
    border-bottom: 1px solid var(--slate-200) !important;
}

.header-container h1 {
    font-size: 22px !important;
    font-weight: 700 !important;
    color: var(--slate-900) !important;
    margin: 0 0 6px 0 !important;
    line-height: 1.2 !important;
}

/* Shell Navigation Tabs: High visual hierarchy */
.tab-nav, div[role="tablist"], .tab-wrapper, .tab-container:not(.visually-hidden) {
    display: flex !important;
    flex-wrap: wrap !important;
    overflow: visible !important;
    max-width: 100% !important;
    gap: 6px !important;
    border-bottom: 2px solid var(--slate-200) !important;
    background: transparent !important;
    margin-bottom: 12px !important;
}

div[role="tablist"] > button, .tab-nav button, .tab-wrapper button, .tab-container button, .tabs button {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    font-family: var(--font-sans) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    padding: 7px 12px !important;
    white-space: nowrap !important;
    color: var(--slate-600) !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -2px !important;
    border-radius: 4px 4px 0 0 !important;
    transition: all 0.15s ease !important;
    background: transparent !important;
}

div[role="tablist"] > button:hover, .tab-nav button:hover {
    color: var(--indigo-600) !important;
    background: var(--indigo-50) !important;
}

div[role="tablist"] > button.selected, .tab-nav button.selected, .tab-container button.selected, .tabs button.selected {
    color: var(--indigo-600) !important;
    border-bottom: 2.5px solid var(--indigo-600) !important;
    background: #ffffff !important;
}

.nav-svg {
    display: inline-block !important;
    vertical-align: middle !important;
}

/* Form inputs & labels */
.gradio-container label,
.gradio-container .block label,
.gradio-container .block > span,
.gradio-container .form > label {
    font-family: var(--font-sans) !important;
    text-transform: uppercase !important;
    font-size: 11px !important;
    letter-spacing: 0.05em !important;
    font-weight: 600 !important;
    color: var(--slate-600) !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Buttons */
.btn-indigo-primary {
    background: var(--indigo-600) !important;
    color: #ffffff !important;
    border: 1px solid var(--indigo-700) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
    transition: background-color 0.15s ease !important;
}

.btn-indigo-primary:hover {
    background: var(--indigo-700) !important;
}

.btn-indigo-outline {
    background: #ffffff !important;
    color: var(--indigo-600) !important;
    border: 1.5px solid var(--indigo-600) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border-radius: 6px !important;
    padding: 7px 14px !important;
    transition: all 0.15s ease !important;
}

.btn-indigo-outline:hover {
    background: var(--indigo-50) !important;
}

.btn-control {
    background: #ffffff !important;
    color: var(--slate-700) !important;
    border: 1px solid var(--slate-200) !important;
    font-weight: 600 !important;
    font-size: 12px !important;
    border-radius: 6px !important;
}

.btn-control:hover {
    background: var(--slate-100) !important;
}

/* KPI Ribbon (7 Cards, Tabular Mono Figures) */
.kpi-row {
    display: flex !important;
    gap: 8px !important;
    width: 100% !important;
    margin-bottom: 12px !important;
}

.kpi-row > div {
    flex: 1 1 0px !important;
    min-width: 0 !important;
}

.kpi-card {
    height: 100% !important;
    min-width: 0 !important;
    background: #ffffff !important;
    border: 1px solid var(--slate-200) !important;
    border-top: 2.5px solid var(--indigo-600) !important;
    border-radius: 8px !important;
    padding: 8px 6px !important;
    text-align: center !important;
    overflow: hidden !important;
    box-sizing: border-box !important;
}

.kpi-val {
    font-family: var(--font-mono) !important;
    font-variant-numeric: tabular-nums !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    color: var(--slate-900) !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

.kpi-lbl {
    font-family: var(--font-sans) !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: var(--slate-600) !important;
    margin-top: 2px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

/* Result Banner */
.result-banner {
    background: #ffffff !important;
    border: 1px solid #cbd5e1 !important;
    border-left: 4px solid var(--indigo-600) !important;
    border-radius: 6px !important;
    padding: 10px 14px !important;
    margin-bottom: 10px !important;
}

.result-sentence {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--slate-800) !important;
}

/* Status Badges */
.badge-tag {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    padding: 3px 8px !important;
    border-radius: 4px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    margin-right: 6px !important;
    vertical-align: middle !important;
}

.badge-real {
    background: #e0f2fe !important;
    color: #0369a1 !important;
    border: 1px solid #bae6fd !important;
}

.badge-sim {
    background: #f1f5f9 !important;
    color: #475569 !important;
    border: 1px solid #cbd5e1 !important;
}

.badge-verified {
    background: #ecfdf5 !important;
    color: #047857 !important;
    border: 1px solid #a7f3d0 !important;
}

/* Accessible focus visible outlines */
button:focus-visible, input:focus-visible, select:focus-visible {
    outline: 2px solid var(--indigo-600) !important;
    outline-offset: 2px !important;
}

/* Code block formatting */
pre, code {
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
}

/* Responsive Breakpoints: 1440, 1024, and 390 px */
@media (max-width: 1024px) {
    .kpi-row {
        flex-wrap: wrap !important;
    }
    .kpi-row > div {
        flex: 1 1 30% !important;
    }
    div[role="tablist"] > button {
        font-size: 11px !important;
        padding: 5px 8px !important;
    }
}

@media (max-width: 480px) {
    .header-container h1 {
        font-size: 17px !important;
    }
    .kpi-row > div {
        flex: 1 1 45% !important;
    }
    div[role="tablist"] > button {
        font-size: 9px !important;
        padding: 4px 6px !important;
        letter-spacing: 0 !important;
    }
    .kpi-val {
        font-size: 15px !important;
    }
}
"""
