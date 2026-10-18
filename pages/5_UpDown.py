"""
Page 5: Upload vs Download Traffic Analysis.
Upstream/downstream totals, overall ratio, category asymmetry,
and bidirectional time-series area charts.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from analytics.updown import UpDownAnalytics
from ui.charts import build_area_updown_chart, build_bar_chart
from ui.common import download_csv_button, render_kpi, setup_page

st.set_page_config(page_title="Upload vs Download", page_icon="⚖️", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Upload vs Download Dynamics",
        subtitle="Bidirectional payload symmetry, uplink/downlink ratios, and traffic characterization."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    engine = UpDownAnalytics(repo)
    summary = engine.get_summary(start_ts, end_ts)
    cat_df = engine.get_category_asymmetry(start_ts, end_ts)
    timeline_df = engine.get_timeline_bidirectional(start_ts, end_ts)

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    render_kpi(k1, "Total Uploaded", f"{summary['gb_up']:.1f} GB", delta=f"{summary['pct_up']}% of all bytes")
    render_kpi(k2, "Total Downloaded", f"{summary['gb_down']:.1f} GB", delta=f"{summary['pct_down']}% of all bytes")
    render_kpi(k3, "Overall Up/Down Ratio", f"{summary['ratio']:.2f}", delta="Typical broadband: 0.15 - 0.35")
    render_kpi(k4, "Combined Volume", f"{summary['total_gb']:.1f} GB", delta="Bidirectional aggregate")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Bidirectional Area Chart
    st.subheader("Hourly Bidirectional Throughput (Upload vs Download)")
    if not timeline_df.empty:
        area_fig = build_area_updown_chart(
            df=timeline_df,
            x="hour_ts",
            y_up="mbps_up",
            y_down="mbps_down",
            title="Throughput Over Time (Mbps)",
            height=360,
            dark_mode=dark_mode
        )
        st.plotly_chart(area_fig, width="stretch")

    # Category Asymmetry & Characterization Table
    st.subheader("Category Payload Asymmetry & Characterization")
    if not cat_df.empty:
        c1, c2 = st.columns([1.3, 1.0])

        with c1:
            bar_fig = build_bar_chart(
                df=cat_df,
                x="category",
                y="ratio",
                title="Up/Down Ratio by Application Category",
                height=320,
                dark_mode=dark_mode
            )
            st.plotly_chart(bar_fig, width="stretch")

        with c2:
            display_cat = cat_df[[
                "category", "gb_up", "gb_down", "ratio", "traffic_character"
            ]].rename(columns={
                "category": "Category",
                "gb_up": "Up (GB)",
                "gb_down": "Down (GB)",
                "ratio": "Ratio",
                "traffic_character": "Profile"
            })
            st.dataframe(display_cat, width="stretch", hide_index=True)
            download_csv_button(display_cat, filename="updown_category_asymmetry.csv", label="Export Table CSV")


if __name__ == "__main__":
    main()
