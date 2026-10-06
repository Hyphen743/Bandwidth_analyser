"""
Page 2: Application Bandwidth Analysis.
Highest/lowest apps, average/min/max stats, upload vs download split,
percentage contribution, and historical consumption timelines.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from analytics.app_analysis import ApplicationAnalytics
from ui.charts import build_bar_chart, build_donut_chart, build_line_chart
from ui.common import download_csv_button, format_bytes, render_kpi, setup_page

st.set_page_config(page_title="Applications Analysis", page_icon="📦", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Application Consumption Analysis",
        subtitle="Bandwidth breakdown across applications, categories, and bidirectional payload distribution."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]
    app_filter = filters["app_filter"]

    engine = ApplicationAnalytics(repo)
    summary_df = engine.get_summary(start_ts, end_ts)

    if summary_df.empty:
        st.warning("No application records found for the selected time range.")
        return

    # Filter if entity selected
    if app_filter:
        summary_df = summary_df[summary_df["app_name"] == app_filter]

    # Extremes & Metrics
    extremes = engine.get_extremes(start_ts, end_ts)
    highest_app = extremes["highest"]
    lowest_app = extremes["lowest"]

    k1, k2, k3, k4 = st.columns(4)
    total_bytes = summary_df["total_bytes"].sum() if "total_bytes" in summary_df.columns else summary_df["total_gb"].sum() * (1024**3)
    render_kpi(k1, "Total App Volume", format_bytes(total_bytes), delta=f"{len(summary_df)} active applications")
    if highest_app:
        top_bytes = highest_app["total_bytes"] if "total_bytes" in highest_app else highest_app["total_gb"] * (1024**3)
        render_kpi(k2, "Top Consumer", highest_app["app_name"], delta=f"{format_bytes(top_bytes)} ({highest_app['pct_contribution']}%)")
    if lowest_app:
        low_bytes = lowest_app["total_bytes"] if "total_bytes" in lowest_app else lowest_app["total_gb"] * (1024**3)
        render_kpi(k3, "Lowest Consumer", lowest_app["app_name"], delta=f"{format_bytes(low_bytes)} ({lowest_app['pct_contribution']}%)")
    avg_sample_bytes = summary_df['avg_bytes_per_sample'].mean() if 'avg_bytes_per_sample' in summary_df.columns else 0
    render_kpi(k4, "Avg per Sample", format_bytes(avg_sample_bytes), delta="Payload granularity")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Charts Row
    c1, c2 = st.columns([1.5, 1.0])

    with c1:
        st.subheader("Bandwidth Volume by Application (GB)")
        top_apps = summary_df.sort_values(by="total_gb", ascending=True)
        bar_fig = build_bar_chart(
            df=top_apps,
            x="total_gb",
            y="app_name",
            horizontal=True,
            title="Total Transferred Data",
            height=360,
            dark_mode=dark_mode
        )
        st.plotly_chart(bar_fig, use_container_width=True)

    with c2:
        st.subheader("Traffic Share by Category")
        cat_df = engine.get_category_breakdown(start_ts, end_ts)
        if not cat_df.empty:
            cat_fig = build_donut_chart(
                df=cat_df,
                names="category",
                values="total_gb",
                title="Category Share",
                height=360,
                dark_mode=dark_mode
            )
            st.plotly_chart(cat_fig, use_container_width=True)

    # Application Timeline
    st.subheader("Application Hourly Timeline")
    selected_app_row = summary_df.iloc[0] if app_filter else summary_df.sort_values(by="total_gb", ascending=False).iloc[0]
    app_id = int(selected_app_row["app_id"])

    timeline_df = engine.get_app_timeline(start_ts, end_ts, app_id=app_id)
    if not timeline_df.empty:
        time_fig = build_line_chart(
            df=timeline_df,
            x="hour_ts",
            y=["bytes_down", "bytes_up"],
            title=f"Hourly Payload: {selected_app_row['app_name']} (Bytes)",
            y_label="Bytes",
            height=320,
            dark_mode=dark_mode
        )
        st.plotly_chart(time_fig, use_container_width=True)

    # Detailed Table
    st.subheader("Application Details Table")
    table_display = summary_df[[
        "app_name", "category", "total_gb", "gb_up", "gb_down",
        "up_down_ratio", "pct_contribution", "sample_count"
    ]].rename(columns={
        "app_name": "Application",
        "category": "Category",
        "total_gb": "Total (GB)",
        "gb_up": "Up (GB)",
        "gb_down": "Down (GB)",
        "up_down_ratio": "Up/Down Ratio",
        "pct_contribution": "Share (%)",
        "sample_count": "Samples"
    })

    st.dataframe(table_display, use_container_width=True, hide_index=True)
    download_csv_button(table_display, filename="application_analytics.csv", label="Export Applications CSV")


if __name__ == "__main__":
    main()
