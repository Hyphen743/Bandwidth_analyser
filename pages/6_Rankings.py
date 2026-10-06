"""
Page 6: Leaderboards and Rank Shifts.
Top 5/10 applications and devices, comparing current period positions
against preceding periods with directional rank shift indicators (↑, ↓, ↔).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from analytics.ranking import RankingAnalytics
from ui.common import download_csv_button, format_bytes, render_kpi, setup_page

st.set_page_config(page_title="Rankings & Shifts", page_icon="🏆", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Leaderboards & Period Rank Shifts",
        subtitle="Tracking consumer movements and relative rank volatility over successive operational windows."
    )
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    engine = RankingAnalytics(repo)

    top_n = st.radio("Leaderboard Depth", [5, 10], index=1, horizontal=True)

    app_ranks = engine.get_app_rankings(start_ts, end_ts, limit=top_n)
    dev_ranks = engine.get_device_rankings(start_ts, end_ts, limit=top_n)

    tab_apps, tab_devices = st.tabs(["Applications Leaderboard", "Devices Leaderboard"])

    with tab_apps:
        st.subheader(f"Top {top_n} Applications")
        if not app_ranks.empty:
            app_ranks["volume_formatted"] = app_ranks["total_bytes"].apply(format_bytes)
            display_apps = app_ranks[[
                "current_rank", "rank_change", "app_name", "category", "volume_formatted"
            ]].rename(columns={
                "current_rank": "Rank",
                "rank_change": "Shift",
                "app_name": "Application",
                "category": "Category",
                "volume_formatted": "Volume"
            })
            st.dataframe(display_apps, use_container_width=True, hide_index=True)
            download_csv_button(display_apps, filename="top_apps_rankings.csv", label="Export Apps Leaderboard")
        else:
            st.info("No application rankings available.")

    with tab_devices:
        st.subheader(f"Top {top_n} Endpoints")
        if not dev_ranks.empty:
            dev_ranks["volume_formatted"] = dev_ranks["total_bytes"].apply(format_bytes)
            display_devs = dev_ranks[[
                "current_rank", "rank_change", "hostname", "device_type", "volume_formatted"
            ]].rename(columns={
                "current_rank": "Rank",
                "rank_change": "Shift",
                "hostname": "Device Hostname",
                "device_type": "Hardware Type",
                "volume_formatted": "Volume"
            })
            st.dataframe(display_devs, use_container_width=True, hide_index=True)
            download_csv_button(display_devs, filename="top_devices_rankings.csv", label="Export Devices Leaderboard")
        else:
            st.info("No device rankings available.")


if __name__ == "__main__":
    main()
