"""
Page 10: Network Efficiency Scoring and Optimization Advisor.
Multi-factor efficiency gauge (0-100), subscore decomposition,
cross-entity ratings, and ranked optimization recommendations with estimated GB savings.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ml.efficiency import EfficiencyEngine
from ui.charts import build_bar_chart
from ui.common import download_csv_button, format_bytes, render_kpi, setup_page

st.set_page_config(page_title="Efficiency Scoring", page_icon="✨", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Network Efficiency Scoring & Advisor",
        subtitle="Holistic performance rating based on throughput utility, burstiness, off-peak shifting, and link health."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    engine = EfficiencyEngine(repo)
    eff = engine.calculate_efficiency(start_ts, end_ts)
    sub = eff["subscores"]

    # Efficiency Overview KPIs
    k1, k2, k3, k4 = st.columns(4)
    render_kpi(
        k1,
        "Composite Efficiency",
        f"{eff['overall_score']:.0f} / 100",
        delta="Multi-factor weighted rating",
        delta_type="pos" if eff["overall_score"] >= 70 else ("neg" if eff["overall_score"] < 40 else "neutral"),
        pill=eff["rating"]
    )
    render_kpi(k2, "Peak-to-Average (PAR)", f"{eff['par']:.2f}", delta="Burstiness multiplier", delta_type="pos" if eff["par"] < 2.5 else "neg")
    render_kpi(k3, "Useful Data Share", f"{sub['useful_throughput']:.0f}%", delta="Productive traffic volume", delta_type="pos")
    render_kpi(k4, "Off-Peak Deferral", f"{sub['offpeak_shifting']:.0f}%", delta="Night schedule utilization", delta_type="neutral")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Subscore Pillar Breakdown
    st.subheader("Efficiency Subscore Pillars")
    pillars_df = pd.DataFrame([
        {"Pillar": "Useful Throughput (Weight 25%)", "Score": sub["useful_throughput"], "Benchmark Target": 85},
        {"Pillar": "PAR Smoothness (Weight 25%)", "Score": sub["smoothness_par"], "Benchmark Target": 75},
        {"Pillar": "Off-Peak Shifting (Weight 20%)", "Score": sub["offpeak_shifting"], "Benchmark Target": 70},
        {"Pillar": "Bidirectional Balance (Weight 15%)", "Score": sub["traffic_balance"], "Benchmark Target": 80},
        {"Pillar": "Link Quality & Loss (Weight 15%)", "Score": sub["network_quality"], "Benchmark Target": 90}
    ])

    fig_bar = build_bar_chart(
        df=pillars_df,
        x="Score",
        y="Pillar",
        horizontal=True,
        title="Subscore Health Breakdown (0 - 100)",
        height=280,
        dark_mode=dark_mode
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Cross-Entity Ratings
    st.subheader("Application Efficiency Scorecard")
    entity_eff_df = engine.compare_entities_efficiency(start_ts, end_ts)
    if not entity_eff_df.empty:
        if "total_bytes" in entity_eff_df.columns:
            entity_eff_df["volume_formatted"] = entity_eff_df["total_bytes"].apply(format_bytes)
        else:
            entity_eff_df["volume_formatted"] = (entity_eff_df["total_gb"] * (1024**3)).apply(format_bytes)
        st.dataframe(
            entity_eff_df.rename(columns={
                "name": "Application",
                "category": "Category",
                "volume_formatted": "Volume",
                "efficiency_score": "Efficiency Score (0-100)",
                "rating": "Status"
            })[["Application", "Category", "Volume", "Efficiency Score (0-100)", "Status"]],
            use_container_width=True,
            hide_index=True
        )

    # -------------------------------------------------------------------------
    # Optimization Advisor (Ranked List of Savings)
    # -------------------------------------------------------------------------
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    st.subheader("Optimization Advisor (Ranked Action Items)")
    st.caption("Prioritized architectural and configuration adjustments with projected bandwidth savings.")

    if eff["recommendations"]:
        rec_df = pd.DataFrame(eff["recommendations"])
        st.dataframe(
            rec_df.rename(columns={
                "priority": "Priority",
                "title": "Actionable Recommendation",
                "impact": "Expected Operational Impact",
                "estimated_savings_gb": "Projected Monthly Savings (GB)",
                "category": "Strategy Type"
            }),
            use_container_width=True,
            hide_index=True
        )

        total_savings = rec_df["estimated_savings_gb"].sum()
        st.success(f"Implementing all recommendations can conserve approximately **{total_savings:.1f} GB** of monthly network overhead.")
        download_csv_button(rec_df, filename="optimization_recommendations.csv", label="Export Recommendations CSV")
    else:
        st.info("Network is performing at peak efficiency. No optimization adjustments needed.")


if __name__ == "__main__":
    main()
