"""
Page 3: Devices and Users Bandwidth Analysis.
Cross-device comparative consumption, user attribution, and
per-device historical z-score anomaly detection.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from analytics.device_analysis import DeviceAnalytics
from ui.charts import build_bar_chart, build_donut_chart
from ui.common import download_csv_button, format_bytes, render_kpi, setup_page

st.set_page_config(page_title="Devices & Users", page_icon="💻", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Devices & Users Analysis",
        subtitle="Bandwidth distribution across hardware endpoints, owner assignments, and unusual usage spikes."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]
    dev_filter = filters["device_filter"]

    engine = DeviceAnalytics(repo)
    device_df = engine.get_device_summary(start_ts, end_ts)
    user_df = engine.get_user_summary(start_ts, end_ts)

    if device_df.empty:
        st.warning("No device activity recorded for the specified time range.")
        return

    if dev_filter:
        device_df = device_df[device_df["hostname"] == dev_filter]

    extremes = engine.get_extremes(start_ts, end_ts)
    highest_dev = extremes["highest"]
    lowest_dev = extremes["lowest"]

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    total_bytes = device_df["total_bytes"].sum() if "total_bytes" in device_df.columns else device_df["total_gb"].sum() * (1024**3)
    render_kpi(k1, "Monitored Endpoints", f"{len(device_df)} Devices", delta=f"{len(user_df)} mapped users")
    if highest_dev:
        top_bytes = highest_dev["total_bytes"] if "total_bytes" in highest_dev else highest_dev["total_gb"] * (1024**3)
        render_kpi(k2, "Top Endpoint", highest_dev["hostname"], delta=f"{format_bytes(top_bytes)} ({highest_dev['pct_contribution']}%)")
    if lowest_dev:
        low_bytes = lowest_app_bytes = lowest_dev["total_bytes"] if "total_bytes" in lowest_dev else lowest_dev["total_gb"] * (1024**3)
        render_kpi(k3, "Lowest Endpoint", lowest_dev["hostname"], delta=f"{format_bytes(lowest_app_bytes)} ({lowest_dev['pct_contribution']}%)")
    avg_dev_bytes = device_df["total_bytes"].mean() if "total_bytes" in device_df.columns else device_df["total_gb"].mean() * (1024**3)
    render_kpi(k4, "Avg Device Load", format_bytes(avg_dev_bytes), delta="Per-endpoint average")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Visualizations Row
    c1, c2 = st.columns([1.5, 1.0])

    with c1:
        st.subheader("Data Volume by Device (GB)")
        sorted_dev = device_df.sort_values(by="total_gb", ascending=True)
        bar_fig = build_bar_chart(
            df=sorted_dev,
            x="total_gb",
            y="hostname",
            horizontal=True,
            title="Endpoint Bandwidth Consumption",
            height=340,
            dark_mode=dark_mode
        )
        st.plotly_chart(bar_fig, use_container_width=True)

    with c2:
        st.subheader("Usage by User")
        if not user_df.empty:
            user_fig = build_donut_chart(
                df=user_df,
                names="user_name",
                values="total_gb",
                title="User Traffic Distribution",
                height=340,
                dark_mode=dark_mode
            )
            st.plotly_chart(user_fig, use_container_width=True)

    # Unusual Device Consumption (Z-score spikes)
    st.subheader("Unusual Device Spikes (Historical Z-Score vs Own History)")
    unusual_df = engine.detect_unusual_device_consumption(start_ts, end_ts, z_threshold=2.0)

    if not unusual_df.empty:
        st.dataframe(
            unusual_df.rename(columns={
                "hostname": "Device",
                "date": "Date",
                "daily_gb": "Volume (GB)",
                "historical_avg_gb": "Historical Avg (GB)",
                "z_score": "Z-Score",
                "severity": "Severity"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("No anomalous single-device volume deviations detected in this timeframe.")

    # Detailed Table
    st.subheader("Device Inventory & Metrics")
    dev_display = device_df[[
        "hostname", "user_name", "user_role", "device_type",
        "ip", "total_gb", "gb_up", "gb_down", "pct_contribution"
    ]].rename(columns={
        "hostname": "Hostname",
        "user_name": "Assigned User",
        "user_role": "Role",
        "device_type": "Type",
        "ip": "IP Address",
        "total_gb": "Total (GB)",
        "gb_up": "Up (GB)",
        "gb_down": "Down (GB)",
        "pct_contribution": "Share (%)"
    })
    st.dataframe(dev_display, use_container_width=True, hide_index=True)
    download_csv_button(dev_display, filename="devices_and_users.csv", label="Export Device Metrics")


if __name__ == "__main__":
    main()
