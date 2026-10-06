"""
UI Theme and Styling for Bandwidth Usage Monitor.
Enforces minimal, calm visual design with zero blue anywhere.
Palette:
- Background: #FAF7F2 (light) / #1C1B1A (warm charcoal dark)
- Surface: #FFFFFF (light) / #272523 (dark)
- Text: #2B2B2B (light) / #EDE8E3 (dark)
- Primary Terracotta: #C8553D
- Accent Amber: #E0A458
- Sage: #7A9E7E
- Muted Stone: #B8B2A7
- Alert Red: #A63D40
"""

from __future__ import annotations

import streamlit as st

WARM_PALETTE = {
    "bg_light": "#FAF7F2",
    "surface_light": "#FFFFFF",
    "text_light": "#2B2B2B",
    "bg_dark": "#1C1B1A",
    "surface_dark": "#272523",
    "text_dark": "#EDE8E3",
    "terracotta": "#C8553D",
    "amber": "#E0A458",
    "sage": "#7A9E7E",
    "stone": "#B8B2A7",
    "stone_light": "#EAE5DC",
    "alert_red": "#A63D40",
    "card_border_light": "#E8E2D8",
    "card_border_dark": "#383532"
}

COLORWAY = [
    "#C8553D",  # Terracotta
    "#E0A458",  # Amber
    "#7A9E7E",  # Sage
    "#B8B2A7",  # Stone
    "#A63D40",  # Alert Red
    "#D48C46",  # Warm Ochre
    "#5C8065",  # Forest Sage
    "#9E8279"   # Muted Clay
]


def inject_custom_css(dark_mode: bool = False) -> None:
    """Inject global CSS stylesheet overriding Streamlit styling."""
    bg = WARM_PALETTE["bg_dark"] if dark_mode else WARM_PALETTE["bg_light"]
    surface = WARM_PALETTE["surface_dark"] if dark_mode else WARM_PALETTE["surface_light"]
    text = WARM_PALETTE["text_dark"] if dark_mode else WARM_PALETTE["text_light"]
    border = WARM_PALETTE["card_border_dark"] if dark_mode else WARM_PALETTE["card_border_light"]
    terracotta = WARM_PALETTE["terracotta"]
    amber = WARM_PALETTE["amber"]

    css = f"""
    <style>
        /* Base typography & colors */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: {text};
            background-color: {bg};
        }}

        .stApp {{
            background-color: {bg};
        }}

        /* Headings with warm serif editorial tone */
        h1, h2, h3 {{
            font-family: 'Newsreader', Georgia, serif;
            font-weight: 600;
            color: {text};
            letter-spacing: -0.01em;
        }}

        h4, h5, h6 {{
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            color: {text};
        }}

        /* Eliminate all default blue hyperlinks and focus states */
        a {{
            color: {terracotta} !important;
            text-decoration: none;
            transition: color 0.2s ease;
        }}
        a:hover {{
            color: {amber} !important;
            text-decoration: underline;
        }}

        /* Streamlit primary button overrides */
        .stButton>button {{
            background-color: {surface};
            color: {text};
            border: 1px solid {border};
            border-radius: 6px;
            padding: 0.45rem 1rem;
            font-weight: 500;
            font-size: 0.88rem;
            transition: all 0.2s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }}
        .stButton>button:hover {{
            border-color: {terracotta};
            color: {terracotta};
            background-color: {surface};
        }}
        .stButton>button:focus, .stButton>button:active {{
            border-color: {terracotta} !important;
            box-shadow: 0 0 0 2px rgba(200, 85, 61, 0.2) !important;
            color: {terracotta} !important;
        }}

        /* Primary action button */
        .stButton>button[kind="primary"] {{
            background-color: {terracotta} !important;
            color: #FFFFFF !important;
            border: 1px solid {terracotta} !important;
        }}
        .stButton>button[kind="primary"]:hover {{
            background-color: #B24630 !important;
            border-color: #B24630 !important;
        }}

        /* Sliders - replace blue thumb and track with terracotta */
        div[data-baseweb="slider"] div {{
            background-color: {terracotta} !important;
        }}
        div[data-baseweb="slider"] [role="slider"] {{
            background-color: {terracotta} !important;
            border-color: {terracotta} !important;
            box-shadow: 0 0 0 3px rgba(200, 85, 61, 0.2) !important;
        }}

        /* Radio & Checkbox */
        div[data-baseweb="radio"] div[aria-checked="true"] {{
            border-color: {terracotta} !important;
            background-color: {terracotta} !important;
        }}
        div[data-baseweb="checkbox"] div[aria-checked="true"] {{
            border-color: {terracotta} !important;
            background-color: {terracotta} !important;
        }}

        /* Select box / Dropdown focus */
        div[data-baseweb="select"] > div {{
            border-color: {border} !important;
            background-color: {surface} !important;
        }}
        div[data-baseweb="select"] > div:focus-within {{
            border-color: {terracotta} !important;
            box-shadow: 0 0 0 1px {terracotta} !important;
        }}

        /* Metric cards */
        .kpi-card {{
            background-color: {surface};
            border: 1px solid {border};
            border-radius: 8px;
            padding: 1.1rem 1.25rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 1px 3px rgba(43, 43, 43, 0.03);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        .kpi-card:hover {{
            border-color: {border};
            box-shadow: 0 3px 6px rgba(43, 43, 43, 0.06);
        }}
        .kpi-title {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #7E7870;
            margin-bottom: 0.35rem;
            font-weight: 600;
        }}
        .kpi-value {{
            font-size: 1.9rem;
            font-weight: 700;
            color: {text};
            font-family: 'Newsreader', Georgia, serif;
            line-height: 1.1;
        }}
        .kpi-delta {{
            font-size: 0.82rem;
            margin-top: 0.4rem;
            font-weight: 500;
        }}
        .kpi-delta.pos {{ color: #5C8065; }}
        .kpi-delta.neg {{ color: #A63D40; }}
        .kpi-delta.neutral {{ color: #7E7870; }}

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
        .pill-efficient {{ background-color: #E8F0EA; color: #3E6346; }}
        .pill-moderate {{ background-color: #FAF2E3; color: #8F6218; }}
        .pill-inefficient {{ background-color: #F8E7E7; color: #8C292C; }}

        /* Sidebar styling */
        section[data-testid="stSidebar"] {{
            background-color: {surface};
            border-right: 1px solid {border};
        }}
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3 {{
            font-size: 1.1rem;
        }}

        /* Subtle scrollbars */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: transparent;
        }}
        ::-webkit-scrollbar-thumb {{
            background: {border};
            border-radius: 3px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #9E978D;
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
