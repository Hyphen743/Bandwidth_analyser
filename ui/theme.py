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
    muted_text = "#C5BFB7" if dark_mode else "#625D56"
    terracotta = WARM_PALETTE["terracotta"]
    amber = WARM_PALETTE["amber"]
    toolbar_css = ""
    if dark_mode:
        toolbar_css = f"""
        /* Keep Streamlit's native top toolbar visible in charcoal mode. */
        [data-testid="stHeader"], [data-testid="stToolbar"] {{
            background-color: {bg} !important;
            color: {text} !important;
        }}
        [data-testid="stHeader"] button,
        [data-testid="stToolbar"] button,
        [data-testid="stMainMenu"] button {{
            color: {text} !important;
            background-color: transparent !important;
            border-color: {border} !important;
        }}
        [data-testid="stHeader"] svg,
        [data-testid="stToolbar"] svg,
        [data-testid="stMainMenu"] svg {{
            color: {text} !important;
            fill: {text} !important;
        }}
        [data-testid="stAppDeployButton"] {{
            color: {text} !important;
            background-color: {surface} !important;
            border: 1px solid {border} !important;
        }}
        [data-testid="stAppDeployButton"] * {{
            color: {text} !important;
            fill: {text} !important;
        }}
        """

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
            color: {text};
        }}

        {toolbar_css}

        /* Keep Streamlit's native widgets readable in both themes. */
        [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],
        [data-testid="stCaptionContainer"], [data-testid="stAlert"] {{ color: {text}; }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{ color: {text}; }}
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{ color: {text} !important; }}
        [data-testid="stDataFrame"], [data-testid="stTable"] {{
            border: 1px solid {border}; border-radius: 8px; overflow: hidden;
        }}
        input, textarea {{
            color: {text} !important;
            background-color: {surface} !important;
            border-color: {border} !important;
            caret-color: {terracotta};
        }}
        input::placeholder, textarea::placeholder {{
            color: {muted_text} !important;
            opacity: 1 !important;
        }}
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {{
            color: {text} !important;
            background-color: {surface} !important;
            border-color: {border} !important;
        }}
        div[data-baseweb="select"] *,
        div[data-baseweb="input"] *,
        div[data-baseweb="textarea"] * {{ color: {text} !important; }}
        /* Keep Streamlit's password visibility control clearly visible in both themes. */
        div[data-baseweb="input"] button[aria-label*="password" i] {{
            min-width: 2.5rem !important;
            min-height: 2.5rem !important;
            color: {text} !important;
            background-color: {surface} !important;
            opacity: 1 !important;
            border-left: 1px solid {border} !important;
            border-radius: 0 6px 6px 0 !important;
        }}
        div[data-baseweb="input"] button[aria-label*="password" i] svg,
        div[data-baseweb="input"] button[aria-label*="password" i] svg * {{
            color: #000000 !important;
            fill: #000000 !important;
            stroke: #000000 !important;
            opacity: 1 !important;
        }}
        div[data-baseweb="input"] button[aria-label*="password" i]:hover {{
            background-color: {border} !important;
        }}
        div[data-baseweb="input"] button[aria-label*="password" i]:focus-visible {{
            outline: 2px solid {terracotta} !important;
            outline-offset: 1px !important;
        }}
        /* The eye button's accessible label varies between Streamlit/BaseWeb versions.
           Target the suffix button by its location inside the text-input widget too. */
        div[data-baseweb="input"] button,
        div[data-baseweb="input"] button:hover,
        div[data-baseweb="input"] button:active,
        [data-testid="stTextInputRootElement"] button,
        [data-testid="stTextInputRootElement"] button:hover,
        [data-testid="stTextInputRootElement"] button:active {{
            color: {text} !important;
            background: {surface} !important;
            background-color: {surface} !important;
            border: 1px solid {border} !important;
            border-radius: 0 6px 6px 0 !important;
            min-width: 2.5rem !important;
            min-height: 2.5rem !important;
            opacity: 1 !important;
        }}
        div[data-baseweb="input"] button svg,
        div[data-baseweb="input"] button svg *,
        div[data-baseweb="input"] button path,
        [data-testid="stTextInputRootElement"] button svg,
        [data-testid="stTextInputRootElement"] button svg *,
        [data-testid="stTextInputRootElement"] button path {{
            color: #000000 !important;
            fill: #000000 !important;
            stroke: #000000 !important;
            opacity: 1 !important;
        }}
        div[data-baseweb="input"] button:focus-visible,
        [data-testid="stTextInputRootElement"] button:focus-visible {{
            outline: 2px solid {terracotta} !important;
            outline-offset: 1px !important;
        }}
        div[data-baseweb="select"] > div * {{ background-color: {surface} !important; }}
        div[data-baseweb="select"] svg {{ fill: {text} !important; }}
        [data-testid="stSelectbox"] [role="combobox"],
        [data-testid="stDateInput"] [role="textbox"] {{
            background-color: {surface} !important;
            color: {text} !important;
            border-color: {border} !important;
        }}
        div[data-baseweb="select"] > div > div:last-child,
        div[data-baseweb="select"] > div > div:last-child * {{
            background-color: {surface} !important;
            color: {text} !important;
            fill: {text} !important;
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
        [data-testid="stDownloadButton"] button {{
            background-color: {surface} !important;
            color: {text} !important;
            border: 1px solid {border} !important;
        }}
        [data-testid="stDownloadButton"] button * {{ color: {text} !important; }}

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
        div[data-baseweb="popover"], [role="listbox"], [role="option"] {{
            background-color: {surface} !important;
            color: {text} !important;
        }}
        [role="option"] *, [role="listbox"] * {{ color: {text} !important; }}

        /* Expander headers and form submit buttons need explicit theme colors;
           Streamlit otherwise keeps a white header with low-contrast text. */
        [data-testid="stExpander"] details,
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary:hover,
        [data-testid="stExpander"] details > div,
        [data-testid="stForm"] {{
            background-color: {surface} !important;
            color: {text} !important;
            border-color: {border} !important;
        }}
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] details > div *,
        [data-testid="stForm"] * {{ color: {text}; }}
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] * {{ color: {muted_text} !important; }}
        [data-testid="stFormSubmitButton"] button {{
            background-color: {terracotta} !important;
            color: #FFFFFF !important;
            border: 1px solid {terracotta} !important;
        }}
        [data-testid="stFormSubmitButton"] button * {{ color: #FFFFFF !important; }}
        [data-testid="stFormSubmitButton"] button:hover {{
            background-color: #B24630 !important;
            color: #FFFFFF !important;
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
            color: {'#C5BFB7' if dark_mode else '#625D56'};
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
        .kpi-delta.neutral {{ color: {'#C5BFB7' if dark_mode else '#625D56'}; }}

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
        .pill-efficient {{ background-color: {'#284231' if dark_mode else '#E8F0EA'}; color: {'#C8E5CF' if dark_mode else '#3E6346'}; }}
        .pill-moderate {{ background-color: {'#49391E' if dark_mode else '#FAF2E3'}; color: {'#F0D59F' if dark_mode else '#8F6218'}; }}
        .pill-inefficient {{ background-color: {'#4A292A' if dark_mode else '#F8E7E7'}; color: {'#F0B6B6' if dark_mode else '#8C292C'}; }}

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
        section[data-testid="stSidebar"] [data-testid="stRadio"] label,
        section[data-testid="stSidebar"] [data-testid="stCheckbox"] label,
        section[data-testid="stSidebar"] [role="radio"],
        section[data-testid="stSidebar"] [role="checkbox"] {{ color: {text} !important; }}

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
