"""
UI Theme and Styling for Bandwidth Usage Monitor.
Enforces minimal, calm visual design with zero blue anywhere and full WCAG AA/AAA contrast.
Light palette:
- Background: #FAF7F2, Surface: #FFFFFF, Surface-2: #F5EFE6, Text: #2B2B2B, Muted: #7E7870, Border: #E8E2D8
Dark palette:
- Background: #1C1B1A, Surface: #262422, Surface-2: #2F2C29, Text: #EDE8E0, Muted: #A39E94, Border: #3A3632
Accents:
- Primary Terracotta: #C8553D, Accent Amber: #E0A458, Sage: #7A9E7E, Alert: #D4605F / #A63D40
"""

from __future__ import annotations

import streamlit as st

WARM_PALETTE = {
    # Light theme variables
    "bg_light": "#FAF7F2",
    "surface_light": "#FFFFFF",
    "surface_2_light": "#F5EFE6",
    "text_light": "#2B2B2B",
    "muted_light": "#7E7870",
    "card_border_light": "#E8E2D8",
    "alert_light": "#A63D40",

    # Dark theme variables
    "bg_dark": "#1C1B1A",
    "surface_dark": "#262422",
    "surface_2_dark": "#2F2C29",
    "text_dark": "#EDE8E0",
    "muted_dark": "#A39E94",
    "card_border_dark": "#3A3632",
    "alert_dark": "#D4605F",

    # Shared accent colors (Strictly zero blue)
    "terracotta": "#C8553D",
    "amber": "#E0A458",
    "sage": "#7A9E7E",
    "stone": "#B8B2A7",
    "alert_red": "#A63D40",
    "stone_light": "#EAE5DC"
}

COLORWAY = [
    "#C8553D",  # Terracotta
    "#E0A458",  # Amber
    "#7A9E7E",  # Sage
    "#B8B2A7",  # Stone
    "#D4605F",  # Warm Alert
    "#D48C46",  # Warm Ochre
    "#5C8065",  # Forest Sage
    "#9E8279"   # Muted Clay
]


def inject_custom_css(dark_mode: bool = False) -> None:
    """Inject global CSS stylesheet with complete light/dark theme variables."""
    if dark_mode:
        bg = WARM_PALETTE["bg_dark"]
        surface = WARM_PALETTE["surface_dark"]
        surface2 = WARM_PALETTE["surface_2_dark"]
        text = WARM_PALETTE["text_dark"]
        muted = WARM_PALETTE["muted_dark"]
        border = WARM_PALETTE["card_border_dark"]
        alert = WARM_PALETTE["alert_dark"]
    else:
        bg = WARM_PALETTE["bg_light"]
        surface = WARM_PALETTE["surface_light"]
        surface2 = WARM_PALETTE["surface_2_light"]
        text = WARM_PALETTE["text_light"]
        muted = WARM_PALETTE["muted_light"]
        border = WARM_PALETTE["card_border_light"]
        alert = WARM_PALETTE["alert_light"]

    terracotta = WARM_PALETTE["terracotta"]
    amber = WARM_PALETTE["amber"]

    css = f"""
    <style>
        /* CSS Variables */
        :root {{
            --bg: {bg};
            --surface: {surface};
            --surface-2: {surface2};
            --text: {text};
            --text-muted: {muted};
            --border: {border};
            --primary: {terracotta};
            --accent: {amber};
            --alert: {alert};
        }}

        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&display=swap');

        /* Base app container */
        html, body, [class*="css"], .stApp {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: var(--text) !important;
            background-color: var(--bg) !important;
        }}

        /* Selection highlighting - Terracotta instead of blue */
        ::selection {{
            background: rgba(200, 85, 61, 0.35) !important;
            color: var(--text) !important;
        }}

        /* Headings */
        h1, h2, h3 {{
            font-family: 'Newsreader', Georgia, serif;
            font-weight: 600;
            color: var(--text) !important;
            letter-spacing: -0.01em;
        }}
        h4, h5, h6 {{
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            color: var(--text) !important;
        }}

        /* Paragraphs and general text */
        p, span, div, label, li {{
            color: var(--text);
        }}

        /* Links: terracotta/amber - zero blue */
        a, a:visited {{
            color: var(--primary) !important;
            text-decoration: none;
            transition: color 0.15s ease;
        }}
        a:hover {{
            color: var(--accent) !important;
            text-decoration: underline;
        }}

        /* Sidebar container */
        section[data-testid="stSidebar"] {{
            background-color: var(--surface) !important;
            border-right: 1px solid var(--border) !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
            color: var(--text) !important;
        }}

        /* Sidebar Navigation Links */
        [data-testid="stSidebarNav"] {{
            background-color: transparent !important;
        }}
        [data-testid="stSidebarNav"] a {{
            color: var(--text-muted) !important;
            border-radius: 6px;
            padding: 0.35rem 0.6rem;
            margin: 0.15rem 0;
            transition: all 0.15s ease;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            background-color: var(--surface-2) !important;
            color: var(--text) !important;
        }}
        [data-testid="stSidebarNav"] a[aria-current="page"],
        [data-testid="stSidebarNav"] li:has(a[aria-current="page"]) a {{
            background-color: var(--surface-2) !important;
            color: var(--primary) !important;
            font-weight: 600 !important;
            border-left: 3px solid var(--primary) !important;
        }}

        /* Form Labels with high contrast */
        label, [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] span {{
            color: var(--text) !important;
            font-size: 0.88rem !important;
            font-weight: 500 !important;
        }}

        /* Inputs: text, number, date, time */
        input, textarea,
        div[data-baseweb="input"] input,
        div[data-baseweb="base-input"] input {{
            background-color: var(--surface-2) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
        }}
        div[data-baseweb="input"],
        div[data-baseweb="base-input"] {{
            background-color: var(--surface-2) !important;
            border-color: var(--border) !important;
            border-radius: 6px !important;
        }}
        input::placeholder, textarea::placeholder {{
            color: var(--text-muted) !important;
        }}
        input:focus, textarea:focus,
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="base-input"]:focus-within {{
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 2px rgba(200, 85, 61, 0.25) !important;
            outline: none !important;
        }}

        /* Number input up/down buttons */
        div[data-baseweb="input"] button {{
            background-color: var(--surface-2) !important;
            color: var(--text) !important;
            border-color: var(--border) !important;
        }}
        div[data-baseweb="input"] button:hover {{
            color: var(--primary) !important;
        }}

        /* Select boxes and Dropdowns */
        div[data-baseweb="select"] > div {{
            background-color: var(--surface-2) !important;
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
            color: var(--text) !important;
        }}
        div[data-baseweb="select"] * {{
            color: var(--text) !important;
        }}
        div[data-baseweb="select"]:focus-within > div {{
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 2px rgba(200, 85, 61, 0.25) !important;
        }}

        /* Dropdown popover list */
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] ul,
        div[data-baseweb="menu"],
        ul[role="listbox"] {{
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
            color: var(--text) !important;
        }}
        li[role="option"] {{
            color: var(--text) !important;
            background-color: transparent !important;
        }}
        li[role="option"]:hover,
        li[role="option"][aria-selected="true"] {{
            background-color: var(--surface-2) !important;
            color: var(--primary) !important;
        }}

        /* Date picker calendar */
        div[data-baseweb="calendar"] {{
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            color: var(--text) !important;
        }}
        div[data-baseweb="calendar"] * {{
            color: var(--text) !important;
        }}
        div[data-baseweb="calendar"] [aria-selected="true"] {{
            background-color: var(--primary) !important;
            color: #FFFFFF !important;
        }}

        /* Sliders */
        div[data-baseweb="slider"] [role="slider"] {{
            background-color: var(--primary) !important;
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 3px rgba(200, 85, 61, 0.25) !important;
        }}
        div[data-baseweb="slider"] div[data-testid="stSliderTickBar"] {{
            background-color: var(--border) !important;
        }}
        div[data-baseweb="slider"] div[style*="background"] {{
            background-color: var(--primary) !important;
        }}

        /* Radios and Checkboxes */
        div[data-baseweb="radio"] div[aria-checked="true"],
        div[data-baseweb="checkbox"] div[aria-checked="true"] {{
            border-color: var(--primary) !important;
            background-color: var(--primary) !important;
        }}
        div[data-baseweb="radio"] label,
        div[data-baseweb="checkbox"] label,
        [data-testid="stCheckbox"] label {{
            color: var(--text) !important;
        }}

        /* Tabs */
        button[data-baseweb="tab"] {{
            color: var(--text-muted) !important;
            background: transparent !important;
            border: none !important;
            font-weight: 500 !important;
            padding: 0.6rem 1rem !important;
            border-bottom: 2px solid transparent !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: var(--primary) !important;
            font-weight: 600 !important;
            border-bottom: 2px solid var(--primary) !important;
        }}
        div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {{
            background-color: var(--primary) !important;
        }}

        /* Expanders */
        [data-testid="stExpander"], details {{
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
        }}
        summary, [data-testid="stExpander"] summary {{
            color: var(--text) !important;
            font-weight: 600 !important;
        }}

        /* Dataframes & Tables */
        [data-testid="stDataFrame"], div[data-testid="stTable"] {{
            background-color: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
        }}
        [data-testid="stDataFrame"] * {{
            color: var(--text) !important;
        }}

        /* Standard Buttons */
        [data-testid="stButton"] > button,
        [data-testid="stDownloadButton"] > button {{
            background-color: var(--surface-2) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
            padding: 0.45rem 1rem !important;
            font-weight: 500 !important;
            font-size: 0.88rem !important;
            transition: all 0.15s ease !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
        }}
        [data-testid="stButton"] > button:hover,
        [data-testid="stDownloadButton"] > button:hover {{
            border-color: var(--primary) !important;
            color: var(--primary) !important;
            background-color: var(--surface) !important;
        }}
        [data-testid="stButton"] > button:focus,
        [data-testid="stDownloadButton"] > button:focus {{
            border-color: var(--primary) !important;
            box-shadow: 0 0 0 2px rgba(200, 85, 61, 0.25) !important;
        }}

        /* Primary Buttons */
        [data-testid="stButton"] > button[kind="primary"] {{
            background-color: var(--primary) !important;
            color: #FFFFFF !important;
            border: 1px solid var(--primary) !important;
        }}
        [data-testid="stButton"] > button[kind="primary"]:hover {{
            background-color: #B24630 !important;
            border-color: #B24630 !important;
        }}

        /* Status Pills */
        .status-pill {{
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .pill-efficient {{ background-color: rgba(122, 158, 126, 0.2); color: #7A9E7E; }}
        .pill-moderate {{ background-color: rgba(224, 164, 88, 0.2); color: #E0A458; }}
        .pill-inefficient {{ background-color: rgba(212, 96, 95, 0.2); color: #D4605F; }}

        /* Custom Scrollbar */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: transparent;
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 3px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--text-muted);
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
