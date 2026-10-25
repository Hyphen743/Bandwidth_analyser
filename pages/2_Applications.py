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
from ui.common import download_csv_button, render_kpi, setup_page

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

    if filters["data_source"] == "live":
        st.warning(
            "Live mode measures total traffic for this computer. It cannot attribute bytes to individual apps; "
            "the live record is labeled ‘Unattributed interface traffic’. Totals now use the default-route "
            "adapter only; earlier all-adapter live history is preserved separately and is not mixed into this series."
        )

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
    total_gb = summary_df["total_gb"].sum()
    render_kpi(k1, "Total App Volume", f"{total_gb:.1f} GB", delta=f"{len(summary_df)} active applications")
    if highest_app:
        render_kpi(k2, "Top Consumer", highest_app["app_name"], delta=f"{highest_app['total_gb']:.1f} GB ({highest_app['pct_contribution']}%)")
    if lowest_app:
        render_kpi(k3, "Lowest Consumer", lowest_app["app_name"], delta=f"{lowest_app['total_gb']:.2f} GB ({lowest_app['pct_contribution']}%)")
    render_kpi(k4, "Avg per Sample", f"{summary_df['avg_bytes_per_sample'].mean() / 1024:.1f} KB", delta="Payload granularity")

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
        st.plotly_chart(bar_fig, width="stretch")

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
            st.plotly_chart(cat_fig, width="stretch")

    # Application Timeline
    st.subheader("Application Hourly Timeline")
    selected_app_row = summary_df.iloc[0] if app_filter else summary_df.sort_values(by="total_gb", ascending=False).iloc[0]
    app_id = int(selected_app_row["app_id"])

    timeline_df = engine.get_app_timeline(start_ts, end_ts, app_id=app_id)
    if not timeline_df.empty:
        # Show hourly totals in decimal megabytes so Plotly does not abbreviate
        # raw byte counts as values such as "400M" (400 million bytes).
        timeline_chart_df = timeline_df.copy()
        for column in ("bytes_down", "bytes_up"):
            timeline_chart_df[column] = timeline_chart_df[column] / 1_000_000

        time_fig = build_line_chart(
            df=timeline_chart_df,
            x="hour_ts",
            y=["bytes_down", "bytes_up"],
            title=f"Hourly Payload: {selected_app_row['app_name']} (MB)",
            y_label="Data transferred (MB per hour)",
            height=320,
            dark_mode=dark_mode
        )
        st.plotly_chart(time_fig, width="stretch")

    # Detailed Table
    st.subheader("Application Details Table")
    table_display = summary_df[[
        "app_name", "category", "total_gb", "gb_up", "gb_down",
        "up_down_ratio", "pct_contribution", "sample_count"
    ]].copy()
    for column in ("total_gb", "gb_up", "gb_down", "up_down_ratio"):
        table_display[column] = table_display[column].round(2)
    table_display = table_display.rename(columns={
        "app_name": "Application",
        "category": "Category",
        "total_gb": "Total (GB)",
        "gb_up": "Up (GB)",
        "gb_down": "Down (GB)",
        "up_down_ratio": "Up/Down Ratio",
        "pct_contribution": "Share (%)",
        "sample_count": "Collector Samples"
    })

    st.caption(
        "Totals cover the selected date range. Collector Samples are measurement intervals, not app launches or connections."
    )
    st.dataframe(table_display, width="stretch", hide_index=True)
    download_csv_button(table_display, filename="application_analytics.csv", label="Export Applications CSV")


if __name__ == "__main__":
    main()
