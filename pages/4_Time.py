"""
Page 4: Time-Based Bandwidth Analysis.
Hourly, daily, weekly aggregations, peak vs off-peak schedules,
weekday vs weekend profiles, and hour-by-weekday utilization heatmap.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from analytics.time_analysis import TimeAnalytics
from ui.charts import build_bar_chart, build_heatmap_chart, build_line_chart
from ui.common import download_csv_button, render_kpi, setup_page

st.set_page_config(page_title="Time Analysis", page_icon="⏰", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Temporal Bandwidth Analysis",
        subtitle="Diurnal cycles, peak vs off-peak load windows, and hour-by-weekday intensity heatmap."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    engine = TimeAnalytics(repo)

    # Fetch data
    hourly_df = engine.get_hourly_series(start_ts, end_ts)
    peak_offpeak_df = engine.get_peak_offpeak(start_ts, end_ts)
    extremes = engine.get_peak_periods(start_ts, end_ts)
    heatmap_matrix = engine.get_hour_weekday_matrix(start_ts, end_ts)

    if hourly_df.empty:
        st.warning("No time-series usage found for the specified period.")
        return

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    peak_h = extremes["peak_hour"]
    trough_h = extremes["trough_hour"]

    render_kpi(k1, "Monitored Hours", f"{len(hourly_df)} Hrs", delta=f"Hourly resolution")
    if peak_h:
        render_kpi(k2, "Historical Peak", f"{peak_h['mbps']:.1f} Mbps", delta=f"{peak_h['hour_bucket']}")
    if trough_h:
        render_kpi(k3, "Minimum Trough", f"{trough_h['mbps']:.1f} Mbps", delta=f"{trough_h['hour_bucket']}")
    render_kpi(k4, "Average Rate", f"{hourly_df['mbps'].mean():.1f} Mbps", delta="Mean aggregate throughput")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Hour by Weekday Heatmap
    st.subheader("Hour-by-Weekday Intensity Matrix (Average Mbps)")
    if not heatmap_matrix.empty:
        heat_fig = build_heatmap_chart(
            matrix_df=heatmap_matrix,
            title="Weekly Traffic Heatmap (00:00 - 23:00)",
            height=300,
            dark_mode=dark_mode
        )
        st.plotly_chart(heat_fig, use_container_width=True)

    # Peak vs Off-Peak & Weekday vs Weekend Row
    c1, c2 = st.columns([1.2, 1.0])

    with c1:
        st.subheader("Peak vs Off-Peak Consumption Share")
        if not peak_offpeak_df.empty:
            bar_fig = build_bar_chart(
                df=peak_offpeak_df,
                x="period_type",
                y="total_gb",
                title="Transferred Volume by Schedule (GB)",
                height=320,
                dark_mode=dark_mode
            )
            st.plotly_chart(bar_fig, use_container_width=True)

    with c2:
        st.subheader("Weekday vs Weekend Hourly Profiles")
        w_df = engine.get_weekday_vs_weekend(start_ts, end_ts)
        if not w_df.empty:
            pivot_w = w_df.pivot(index="hour_of_day", columns="day_type", values="avg_mbps").reset_index()
            w_fig = build_line_chart(
                df=pivot_w,
                x="hour_of_day",
                y=["Weekday", "Weekend"],
                title="Average Diurnal Wave (Mbps)",
                y_label="Avg Mbps",
                height=320,
                dark_mode=dark_mode
            )
            st.plotly_chart(w_fig, use_container_width=True)

    # Daily Series
    st.subheader("Daily Transferred Data Volume (GB)")
    daily_df = engine.get_daily_series(start_ts, end_ts)
    if not daily_df.empty:
        daily_fig = build_line_chart(
            df=daily_df,
            x="date_bucket",
            y="total_gb",
            title="Daily Total Transferred (GB)",
            y_label="GB",
            height=300,
            dark_mode=dark_mode
        )
        st.plotly_chart(daily_fig, use_container_width=True)
        download_csv_button(daily_df, filename="daily_bandwidth_trends.csv", label="Export Daily Data")


if __name__ == "__main__":
    main()
