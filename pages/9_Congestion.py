"""
Page 9: Link Congestion Bottlenecks and What-If Capacity Planning.
Congestion incident discovery, multivariate correlation matrix (utilization vs latency vs loss),
offender attribution during bottleneck episodes, predictive congestion classifier,
and interactive What-If Capacity upgrade simulator.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import streamlit as st

from ml.congestion import CongestionAnalyzer
from ml.predictor import BandwidthPredictor
from ui.charts import build_congestion_chart
from ui.common import download_csv_button, render_kpi, setup_page

st.set_page_config(page_title="Congestion Analysis", page_icon="🛑", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Network Congestion & Bottlenecks",
        subtitle="Saturation thresholds, bufferbloat telemetry correlations, and What-If capacity modeling."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    analyzer = CongestionAnalyzer(repo)
    predictor = BandwidthPredictor(repo)

    # Configurable threshold
    threshold_util = st.slider("Congestion Utilization Threshold (%)", min_value=50.0, max_value=95.0, value=80.0, step=5.0)

    # Fetch congestion metrics
    metrics_df = analyzer.get_congestion_events(start_ts, end_ts, threshold_util=threshold_util)

    if metrics_df.empty:
        st.warning("No network telemetry records available.")
        return

    congested_count = len(metrics_df[metrics_df["is_congested"] == 1])
    total_samples = len(metrics_df)
    cong_rate = (congested_count / total_samples * 100.0) if total_samples > 0 else 0.0

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    render_kpi(k1, "Congested Intervals", str(congested_count), delta=f"{cong_rate:.1f}% of timeline", delta_type="neg" if congested_count > 0 else "pos")
    render_kpi(k2, "Peak Utilization", f"{metrics_df['utilization_pct'].max():.1f}%", delta="Maximum load observed")
    render_kpi(k3, "Mean Bufferbloat Latency", f"{metrics_df['latency_ms'].mean():.1f} ms", delta=f"Jitter {metrics_df['jitter_ms'].mean():.1f} ms")
    render_kpi(k4, "Packet Drop Events", f"{len(metrics_df[metrics_df['packet_loss_pct'] > 0])}", delta="Loss > 0%")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Timeline Chart
    st.subheader("Network Utilization & Congestion Episodes")
    cong_fig = build_congestion_chart(
        metrics_df=metrics_df,
        threshold_util=threshold_util,
        title="Link Saturation Over Time",
        height=360,
        dark_mode=dark_mode
    )
    st.plotly_chart(cong_fig, use_container_width=True)

    # Correlation Matrix & Offender Attribution Row
    c_corr, c_offend = st.columns([1.1, 1.3])

    with c_corr:
        st.subheader("Telemetry Correlation Matrix")
        corr_matrix = analyzer.get_correlation_matrix(start_ts, end_ts)
        st.dataframe(
            corr_matrix.style.format("{:.2f}").background_gradient(cmap="Reds", vmin=0, vmax=1),
            use_container_width=True
        )
        st.caption("Strong positive correlation between utilization and latency/loss highlights severe bufferbloat.")

    with c_offend:
        st.subheader("Top Contributing Offenders During Congestion")
        offenders_df = analyzer.attribute_congestion_offenders(start_ts, end_ts, limit=5)
        if not offenders_df.empty:
            st.dataframe(
                offenders_df.rename(columns={
                    "app_name": "Application",
                    "category": "Category",
                    "hostname": "Device",
                    "total_bytes": "Total Bytes",
                    "avg_mbps": "Throughput (Mbps)"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No offender traffic attributed during these intervals.")

    # -------------------------------------------------------------------------
    # NEW FEATURE: What-If Capacity Planner
    # -------------------------------------------------------------------------
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    st.subheader("What-If Capacity Planner")
    st.caption("Simulate the impact of provisioning additional users or upgrading total link bandwidth.")

    w1, w2 = st.columns(2)
    with w1:
        add_users = st.slider("Simulate Additional Active Users", min_value=0, max_value=20, value=2, step=1)
    with w2:
        sim_capacity = st.slider("Simulate Link Bandwidth (Mbps)", min_value=50.0, max_value=500.0, value=150.0, step=25.0)

    # Calculate simulated congestion reduction
    # Each user adds an average of ~8 Mbps at peak
    sim_series = metrics_df["utilization_pct"].values.copy()
    user_load_factor = (add_users * 7.5) / sim_capacity * 100.0
    capacity_ratio = 100.0 / sim_capacity

    simulated_utilization = (sim_series * capacity_ratio) + user_load_factor
    sim_congested_count = int(np.sum(simulated_utilization >= threshold_util))
    reduction_pct = ((congested_count - sim_congested_count) / max(1, congested_count)) * 100.0

    r1, r2, r3 = st.columns(3)
    render_kpi(r1, "Original Congested Hours", f"{congested_count} Hrs", delta="Current 100 Mbps link")
    render_kpi(r2, "Projected Congested Hours", f"{sim_congested_count} Hrs", delta=f"At {sim_capacity:.0f} Mbps + {add_users} users")
    render_kpi(
        r3,
        "Net Congestion Relief",
        f"{reduction_pct:.1f}%",
        delta="Improvement" if reduction_pct >= 0 else "Worse degradation",
        delta_type="pos" if reduction_pct > 0 else "neg"
    )

    download_csv_button(metrics_df, filename="congestion_metrics.csv", label="Export Telemetry CSV")


if __name__ == "__main__":
    main()
