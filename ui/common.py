"""
Shared UI Utilities, Filters Sidebar, and Widget Helpers.
Provides unified date filtering, entity selection, CSV export,
and layout styling for all 12 Streamlit pages.
"""

from __future__ import annotations

import io
import textwrap
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from db.repository import DatabaseRepository
from ui.theme import inject_custom_css
from accounts import ensure_account_schema
from ui.auth_ui import render_logout, require_account


def setup_page(title: str, subtitle: Optional[str] = None) -> Tuple[DatabaseRepository, Dict[str, Any]]:
    """
    Standard page initialization:
    - Sets page config and injected CSS
    - Checks dark mode session state
    - Loads repository and sidebar filters
    - Returns (repo, filter_dict)
    """
    preferences_repo = DatabaseRepository()
    ensure_account_schema(preferences_repo)

    # Session state initialization
    if "dark_mode" not in st.session_state:
        saved_theme = preferences_repo.get_setting("theme_mode", "light")
        st.session_state["dark_mode"] = saved_theme == "dark"

    if "data_source" not in st.session_state:
        st.session_state["data_source"] = preferences_repo.get_setting("data_source", "simulated")

    repo = _repository_for_source(st.session_state["data_source"], preferences_repo)

    dark_mode = st.session_state["dark_mode"]
    inject_custom_css(dark_mode=dark_mode)
    if not require_account(preferences_repo):
        # Keep the existing theme, data-source, and filter controls available
        # while signed out; only the protected dashboard content is gated.
        render_sidebar(preferences_repo)
        st.stop()

    # Page Header
    st.markdown(f"""
    <div style="margin-bottom: 1.5rem; padding-bottom: 0.75rem; border-bottom: 1px solid {'#383532' if dark_mode else '#EAE5DC'};">
        <h1 style="margin: 0; font-size: 2.1rem; line-height: 1.2;">{title}</h1>
        {f'<p style="margin: 0.35rem 0 0 0; color: {"#A8A29A" if dark_mode else "#78726A"}; font-size: 0.95rem;">{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    filters = render_sidebar(repo)
    if filters["data_source"] == "live":
        from collector.live_collector import LiveCollector
        collector = LiveCollector.get_instance(repo)
        if not collector.is_running() and not st.session_state.get("live_collector_manually_stopped", False):
            collector.start()
        st.info(
            "LIVE LOCAL DEVICE DATA: this view uses measurements collected on this computer. "
            "Application byte totals and other devices/users cannot be reliably inferred from interface counters."
        )
    return repo, filters


def _repository_for_source(source: str, preferences_repo: DatabaseRepository) -> DatabaseRepository:
    """Return an isolated repository for live measurements or simulated history."""
    if source != "live":
        return preferences_repo

    import socket
    import uuid
    from db.init_db import init_database

    # Start a clean series because the old shared DB may contain duplicate
    # samples from multiple Streamlit processes. Keep that file intact for audit.
    live_path = preferences_repo.db_path.parent / "bandwidth_live_v2.db"
    live_repo = DatabaseRepository(live_path)
    initialized = False
    if live_path.exists() and live_path.stat().st_size > 0:
        try:
            initialized = live_repo.get_setting("live_database_initialized", "0") == "1"
        except Exception:
            initialized = False
    if not initialized:
        init_database(live_path)
        with live_repo.get_connection() as conn:
            conn.execute("DELETE FROM devices")
            conn.execute("DELETE FROM users")
            conn.execute("DELETE FROM applications")
            conn.commit()

        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except OSError:
            local_ip = "127.0.0.1"
        mac = ":".join(f"{(uuid.getnode() >> shift) & 0xff:02x}" for shift in range(40, -1, -8))
        live_repo.insert_device(None, f"This computer ({hostname})", mac, local_ip, "laptop")
        for key in (
            "capacity_mbps", "congestion_util_threshold", "latency_alert_threshold",
            "packet_loss_threshold", "anomaly_z_threshold", "ping_host",
            "collector_interval_sec", "theme_mode", "quiet_hours_enabled",
            "quiet_hours_start", "quiet_hours_end", "desktop_notifications",
            "monthly_device_budget_gb",
        ):
            value = preferences_repo.get_setting(key)
            if value is not None:
                live_repo.set_setting(key, value)
        live_repo.set_setting("live_database_initialized", "1")
    return live_repo


def render_sidebar(repo: DatabaseRepository) -> Dict[str, Any]:
    """Render unified navigation and filter controls in Streamlit sidebar."""
    preferences_repo = DatabaseRepository()
    with st.sidebar:
        if st.session_state.get("account_id"):
            render_logout()
        st.markdown("""
        <div style="margin-bottom: 1.25rem;">
            <div style="font-size: 1.2rem; font-weight: 700; font-family: 'Newsreader', Georgia, serif; color: #C8553D;">
                BANDWIDTH ANALYZER
            </div>
            <div style="font-size: 0.75rem; color: #8C867E; letter-spacing: 0.05em; text-transform: uppercase;">
                Network Telemetry & ML Suite
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Dark mode toggle
        dark_toggle = st.toggle("Dark Theme (Charcoal)", value=st.session_state.get("dark_mode", False))
        if dark_toggle != st.session_state.get("dark_mode", False):
            st.session_state["dark_mode"] = dark_toggle
            preferences_repo.set_setting("theme_mode", "dark" if dark_toggle else "light")
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
            if selected_source == "simulated":
                from collector.live_collector import LiveCollector
                LiveCollector.get_instance(repo).stop()
            else:
                st.session_state["live_collector_manually_stopped"] = False
            st.session_state["data_source"] = selected_source
            preferences_repo.set_setting("data_source", selected_source)
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
        if st.button(
            "Reload 90-Day Demo Data",
            width="stretch",
            disabled=st.session_state.get("data_source") == "live",
        ):
            with st.spinner("Regenerating 90-day seasonal dataset..."):
                from collector.simulator import NetworkSimulator
                sim = NetworkSimulator(preferences_repo, days=90)
                sim.generate()
                st.success("Demo dataset refreshed!")
                st.rerun()
        if st.session_state.get("data_source") == "live":
            st.caption("Live history starts fresh in this version; prior live history is preserved in bandwidth_live.db.")

    return {
        "start_ts": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_ts": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "app_filter": None if selected_app == "All Applications" else selected_app,
        "device_filter": None if selected_device == "All Devices" else selected_device,
        "dark_mode": st.session_state.get("dark_mode", False),
        "data_source": st.session_state.get("data_source", "simulated"),
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
        pill_html = f'<div style="float: right;"><span class="status-pill {pill_class}">{pill}</span></div>'

    delta_html = ""
    if delta:
        delta_class = delta_type if delta_type in ("pos", "neg") else "neutral"
        delta_html = f'<div class="kpi-delta {delta_class}">{delta}</div>'

    html = textwrap.dedent(f"""
    <div style="background-color: {surface}; border: 1px solid {border}; border-radius: 8px; padding: 1.1rem 1.25rem; margin-bottom: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
        {pill_html}
        <div style="font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; color: {subtext}; margin-bottom: 0.35rem; font-weight: 600;">
            {title}
        </div>
        <div style="font-size: 1.95rem; font-weight: 700; color: {text}; font-family: 'Newsreader', Georgia, serif; line-height: 1.1;">
            {value}
        </div>
        {delta_html}
    </div>
    """).strip()
    col.html(html)


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
        width="content"
    )
