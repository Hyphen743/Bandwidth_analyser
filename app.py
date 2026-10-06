"""
Bandwidth Usage Monitor and Analyzer - Streamlit Application Entry.
Executive Network Health Overview, Live Telemetry KPI Cards,
and High-Level Analytical Summaries.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from analytics.app_analysis import ApplicationAnalytics
from collector.live_collector import LiveCollector
from db.repository import DatabaseRepository
from ml.efficiency import EfficiencyEngine
from ui.charts import build_bar_chart, build_donut_chart, build_line_chart
from ui.common import download_csv_button, render_kpi, setup_page

# Page Config must be the first Streamlit command
st.set_page_config(
    page_title="Bandwidth Analyzer",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)


def main() -> None:
    repo, filters = setup_page(
        title="Network Telemetry & Operations",
        subtitle="Real-time monitoring, machine learning traffic forecasting, and automated efficiency scoring."
    )

    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    # Initialize sub-engines
    app_engine = ApplicationAnalytics(repo)
    eff_engine = EfficiencyEngine(repo)

    # Telemetry snapshot
    collector = LiveCollector.get_instance(repo)
    latest_live = collector.get_latest_stats()

    # Calculate Today's usage from DB
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_df = repo.query_df(
        "SELECT COALESCE(SUM(bytes_up + bytes_down), 0) AS total_bytes FROM bandwidth_usage WHERE ts >= :today_start",
        {"today_start": f"{today_str} 00:00:00"}
    )
    today_gb = round(float(today_df.iloc[0]["total_bytes"] or 0) / (1024.0 ** 3), 2) if not today_df.empty else 0.0

    # Alerts count
    alerts_df = repo.get_alerts(unacknowledged_only=True)
    unack_alerts_count = len(alerts_df)

    # Efficiency score
    eff_result = eff_engine.calculate_efficiency(start_ts, end_ts)
    eff_score = eff_result["overall_score"]
    eff_rating = eff_result["rating"]

    # -------------------------------------------------------------------------
    # KPI Cards Row
    # -------------------------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)

    # Current Throughput
    current_mbps = latest_live["total_mbps"]
    render_kpi(
        col=c1,
        title="Current Throughput",
        value=f"{current_mbps:.1f} Mbps",
        delta=f"↑ {latest_live['mbps_up']:.1f} | ↓ {latest_live['mbps_down']:.1f}",
        delta_type="neutral"
    )

    # Today's Volume
    render_kpi(
        col=c2,
        title="Today's Data Transferred",
        value=f"{today_gb:.2f} GB",
        delta=f"Active period volume",
        delta_type="neutral"
    )

    # Active Alerts
    render_kpi(
        col=c3,
        title="Active Alerts",
        value=str(unack_alerts_count),
        delta="Action required" if unack_alerts_count > 0 else "All systems normal",
        delta_type="neg" if unack_alerts_count > 0 else "pos"
    )

    # Efficiency Score
    render_kpi(
        col=c4,
        title="Network Efficiency",
        value=f"{eff_score:.0f} / 100",
        delta=f"P.A.R. {eff_result['par']:.2f}",
        delta_type="pos" if eff_score >= 70 else ("neg" if eff_score < 40 else "neutral"),
        pill=eff_rating
    )

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # Live Traffic Monitor + Auto-Refresh
    # -------------------------------------------------------------------------
    col_chart, col_side = st.columns([2.2, 1.0])

    with col_chart:
        st.subheader("Live Traffic Stream")

        # Auto refresh toggle
        auto_refresh = st.checkbox("Enable Live Polling (3s)", value=False)

        # Fetch recent usage
        recent_history = repo.query_df(
            """
            SELECT 
                strftime('%Y-%m-%d %H:%M:%S', ts) AS ts_sec,
                ROUND(SUM(bytes_up) * 8.0 / (3600.0 * 1000.0 * 1000.0), 3) AS mbps_up,
                ROUND(SUM(bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 3) AS mbps_down,
                ROUND(SUM(bytes_up + bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 3) AS mbps_total
            FROM bandwidth_usage
            WHERE ts BETWEEN :start_ts AND :end_ts
            GROUP BY ts
            ORDER BY ts DESC
            LIMIT 48;
            """,
            {"start_ts": start_ts, "end_ts": end_ts}
        )

        if not recent_history.empty:
            recent_sorted = recent_history.sort_values(by="ts_sec")
            live_fig = build_line_chart(
                df=recent_sorted,
                x="ts_sec",
                y=["mbps_down", "mbps_up"],
                title="Recent Bandwidth (Mbps)",
                height=340,
                dark_mode=dark_mode
            )
            st.plotly_chart(live_fig, use_container_width=True)
            download_csv_button(recent_sorted, filename="recent_bandwidth.csv", label="Export Live Data")
        else:
            st.info("No network activity found for the selected time range.")

    with col_side:
        st.subheader("Top 5 Applications")
        top_apps_df = repo.get_top_apps(start_ts, end_ts, limit=5)

        if not top_apps_df.empty:
            donut_fig = build_donut_chart(
                df=top_apps_df,
                names="app_name",
                values="total_gb",
                height=300,
                dark_mode=dark_mode
            )
            st.plotly_chart(donut_fig, use_container_width=True)

            # Display mini table
            display_tbl = top_apps_df[["app_name", "category", "total_gb"]].rename(
                columns={"app_name": "Application", "category": "Category", "total_gb": "Volume (GB)"}
            )
            st.dataframe(display_tbl, use_container_width=True, hide_index=True)
        else:
            st.info("No application data available.")

    # -------------------------------------------------------------------------
    # Optimization Quick Summary
    # -------------------------------------------------------------------------
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    st.subheader("Optimization Opportunities")

    if eff_result["recommendations"]:
        rec_cols = st.columns(min(3, len(eff_result["recommendations"])))
        for i, rec in enumerate(eff_result["recommendations"][:3]):
            with rec_cols[i]:
                border = "#383532" if dark_mode else "#EAE5DC"
                surface = "#272523" if dark_mode else "#FFFFFF"
                text = "#EDE8E3" if dark_mode else "#2B2B2B"
                st.markdown(f"""
                <div style="background-color: {surface}; border: 1px solid {border}; border-radius: 8px; padding: 1rem 1.1rem; height: 100%;">
                    <div style="font-size: 0.72rem; text-transform: uppercase; font-weight: 700; color: #C8553D;">
                        {rec['priority']} Priority • {rec['category']}
                    </div>
                    <div style="font-size: 0.95rem; font-weight: 600; color: {text}; margin: 0.4rem 0;">
                        {rec['title']}
                    </div>
                    <div style="font-size: 0.82rem; color: {'#A8A29A' if dark_mode else '#78726A'};">
                        {rec['impact']}
                    </div>
                    <div style="font-size: 0.85rem; font-weight: 600; color: #5C8065; margin-top: 0.5rem;">
                        Est. Savings: ~{rec['estimated_savings_gb']} GB
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.success("No critical network optimizations required at this time.")

    # Auto refresh trigger if enabled
    if auto_refresh:
        time.sleep(3)
        st.rerun()


if __name__ == "__main__":
    main()
