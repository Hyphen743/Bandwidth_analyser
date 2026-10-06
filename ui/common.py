"""
Shared UI Utilities, Filters Sidebar, and Widget Helpers.
Provides unified date filtering, entity selection, CSV export,
and layout styling for all 12 Streamlit pages.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from db.repository import DatabaseRepository
from ui.theme import inject_custom_css


def setup_page(title: str, subtitle: Optional[str] = None) -> Tuple[DatabaseRepository, Dict[str, Any]]:
    """
    Standard page initialization:
    - Sets page config and injected CSS
    - Checks dark mode session state
    - Loads repository and sidebar filters
    - Returns (repo, filter_dict)
    """
    repo = DatabaseRepository()

    # Session state initialization
    if "dark_mode" not in st.session_state:
        saved_theme = repo.get_setting("theme_mode", "light")
        st.session_state["dark_mode"] = saved_theme == "dark"

    if "data_source" not in st.session_state:
        st.session_state["data_source"] = repo.get_setting("data_source", "simulated")

    dark_mode = st.session_state["dark_mode"]
    inject_custom_css(dark_mode=dark_mode)

    # Page Header
    header_border = '#383532' if dark_mode else '#EAE5DC'
    sub_color = '#A8A29A' if dark_mode else '#78726A'
    sub_p = f'<p style="margin:0.35rem 0 0 0;color:{sub_color};font-size:0.95rem;">{subtitle}</p>' if subtitle else ''
    header_html = (
        f'<div style="margin-bottom:1.5rem;padding-bottom:0.75rem;border-bottom:1px solid {header_border};">'
        f'<h1 style="margin:0;font-size:2.1rem;line-height:1.2;">{title}</h1>'
        f'{sub_p}</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # Sidebar
    filters = render_sidebar(repo)
    return repo, filters


def render_sidebar(repo: DatabaseRepository) -> Dict[str, Any]:
    """Render unified navigation and filter controls in Streamlit sidebar."""
    with st.sidebar:
        sidebar_logo_html = (
            '<div style="margin-bottom:1.25rem;">'
            '<div style="font-size:1.2rem;font-weight:700;font-family:\'Newsreader\',Georgia,serif;color:#C8553D;">'
            'BANDWIDTH ANALYZER</div>'
            '<div style="font-size:0.75rem;color:#8C867E;letter-spacing:0.05em;text-transform:uppercase;">'
            'Network Telemetry & ML Suite</div></div>'
        )
        st.markdown(sidebar_logo_html, unsafe_allow_html=True)

        # Dark mode toggle
        dark_toggle = st.toggle("Dark Theme (Charcoal)", value=st.session_state.get("dark_mode", False))
        if dark_toggle != st.session_state.get("dark_mode", False):
            st.session_state["dark_mode"] = dark_toggle
            repo.set_setting("theme_mode", "dark" if dark_toggle else "light")
            st.rerun()

        # Data Source Mode (Simulated vs Live)
        st.markdown("---")
        st.markdown("**Data Source Mode**")
        source_mode = st.radio(
            "Source",
            ["Simulated (90 Days)", "Live Network (psutil)"],
            index=0 if st.session_state.get("data_source", "simulated") == "simulated" else 1,
            label_visibility="collapsed"
        )
        selected_source = "simulated" if "Simulated" in source_mode else "live"
        if selected_source != st.session_state.get("data_source"):
            st.session_state["data_source"] = selected_source
            repo.set_setting("data_source", selected_source)
            st.rerun()

        st.markdown("---")
        st.markdown("**Timeline Filters**")

        # Determine date bounds from DB
        min_ts, max_ts = repo.get_date_range()
        now = datetime.now()
        if not min_ts or not max_ts:
            default_start = now - timedelta(days=7)
            default_end = now
        else:
            default_start = datetime.strptime(min_ts, "%Y-%m-%d %H:%M:%S")
            default_end = datetime.strptime(max_ts, "%Y-%m-%d %H:%M:%S")

        quick_range = st.selectbox(
            "Quick Range",
            ["Full 90 Days", "Last 30 Days", "Last 7 Days", "Last 24 Hours", "Custom Range"],
            index=0
        )

        if quick_range == "Last 24 Hours":
            start_dt = default_end - timedelta(hours=24)
            end_dt = default_end
        elif quick_range == "Last 7 Days":
            start_dt = default_end - timedelta(days=7)
            end_dt = default_end
        elif quick_range == "Last 30 Days":
            start_dt = default_end - timedelta(days=30)
            end_dt = default_end
        elif quick_range == "Full 90 Days":
            start_dt = default_start
            end_dt = default_end
        else:
            col1, col2 = st.columns(2)
            with col1:
                d1 = st.date_input("Start", value=default_start.date())
            with col2:
                d2 = st.date_input("End", value=default_end.date())
            start_dt = datetime.combine(d1, datetime.min.time())
            end_dt = datetime.combine(d2, datetime.max.time())

        # Entity Filters
        st.markdown("---")
        st.markdown("**Entity Filtering**")

        apps_df = repo.get_applications()
        app_options = ["All Applications"] + apps_df["name"].tolist() if not apps_df.empty else ["All Applications"]
        selected_app = st.selectbox("Application", app_options)

        devices_df = repo.get_devices()
        dev_options = ["All Devices"] + devices_df["hostname"].tolist() if not devices_df.empty else ["All Devices"]
        selected_device = st.selectbox("Device", dev_options)

        # Demo Reset Button
        st.markdown("---")
        if st.button("Reload 90-Day Demo Data", use_container_width=True):
            with st.spinner("Regenerating 90-day seasonal dataset..."):
                from collector.simulator import NetworkSimulator
                sim = NetworkSimulator(repo, days=90)
                sim.generate()
                st.success("Demo dataset refreshed!")
                st.rerun()

    return {
        "start_ts": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_ts": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "app_filter": None if selected_app == "All Applications" else selected_app,
        "device_filter": None if selected_device == "All Devices" else selected_device,
        "dark_mode": st.session_state.get("dark_mode", False),
        "data_source": st.session_state.get("data_source", "simulated")
    }


def render_kpi(
    col: Any,
    title: str,
    value: str,
    delta: Optional[str] = None,
    delta_type: str = "neutral",
    pill: Optional[str] = None
) -> None:
    """Render a KPI metric card component."""
    dark_mode = st.session_state.get("dark_mode", False)
    surface = "#272523" if dark_mode else "#FFFFFF"
    text = "#EDE8E3" if dark_mode else "#2B2B2B"
    border = "#383532" if dark_mode else "#EAE5DC"
    subtext = "#A8A29A" if dark_mode else "#7E7870"

    pill_html = ""
    if pill:
        pill_class = f"pill-{pill.lower()}"
        pill_html = f'<div style="float:right;"><span class="status-pill {pill_class}">{pill}</span></div>'

    delta_html = ""
    if delta:
        delta_class = delta_type if delta_type in ("pos", "neg") else "neutral"
        delta_html = f'<div class="kpi-delta {delta_class}">{delta}</div>'

    html = (
        f'<div style="background-color:{surface};border:1px solid {border};border-radius:8px;'
        f'padding:1.1rem 1.25rem;margin-bottom:0.75rem;box-shadow:0 1px 3px rgba(0,0,0,0.03);">'
        f'{pill_html}'
        f'<div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;color:{subtext};'
        f'margin-bottom:0.35rem;font-weight:600;">{title}</div>'
        f'<div style="font-size:1.95rem;font-weight:700;color:{text};font-family:\'Newsreader\',Georgia,serif;'
        f'line-height:1.1;">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )
    col.markdown(html, unsafe_allow_html=True)


def download_csv_button(
    df: pd.DataFrame,
    filename: str = "export.csv",
    label: str = "Download CSV"
) -> None:
    """Renders a standard Download CSV button for any tabular result."""
    if df.empty:
        return
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=f"📥 {label}",
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
        use_container_width=False
    )
