"""
Page 7: Multi-Method Anomaly Detection and Ground-Truth Evaluation.
Comparison of Seasonal Z-Score, IQR Fences, and Isolation Forest,
alert acknowledging workflow, and Precision/Recall/F1 evaluation vs ground-truth labels.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ml.anomaly import AnomalyEngine
from ui.charts import build_anomaly_timeline
from ui.common import download_csv_button, render_kpi, setup_page

st.set_page_config(page_title="Anomaly Detection", page_icon="🚨", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Anomaly Detection & Alerting",
        subtitle="Statistical z-scores, non-parametric IQR fences, and machine learning Isolation Forest models."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    engine = AnomalyEngine(repo)
    hourly_df = engine.prepare_hourly_dataset(start_ts, end_ts)

    if hourly_df.empty:
        st.warning("No traffic data available for the chosen time window.")
        return

    # Method Selector & Parameter Tuning
    c_method, c_thresh = st.columns([1.5, 1.0])
    with c_method:
        selected_method = st.selectbox(
            "Detection Algorithm",
            ["Seasonal Rolling Z-Score", "Interquartile Range (IQR)", "Isolation Forest"],
            index=0
        )
    with c_thresh:
        if selected_method == "Seasonal Rolling Z-Score":
            threshold = st.slider("Z-Score Sensitivity (σ)", min_value=1.5, max_value=4.0, value=2.5, step=0.1)
            det_df = engine.detect_zscore(hourly_df, threshold=threshold)
        elif selected_method == "Interquartile Range (IQR)":
            iqr_factor = st.slider("IQR Multiplier (Fence)", min_value=1.0, max_value=3.0, value=1.5, step=0.1)
            det_df = engine.detect_iqr(hourly_df, factor=iqr_factor)
        else:
            contam = st.slider("Contamination Rate (%)", min_value=1.0, max_value=10.0, value=3.0, step=0.5) / 100.0
            det_df = engine.detect_isolation_forest(hourly_df, contamination=contam)

    anomalies_found = det_df[det_df["is_anomaly"] == 1]
    crit_count = len(anomalies_found[anomalies_found["severity"] == "critical"])
    warn_count = len(anomalies_found[anomalies_found["severity"] == "warn"])
    info_count = len(anomalies_found[anomalies_found["severity"] == "info"])

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    render_kpi(k1, "Anomalies Flagged", str(len(anomalies_found)), delta=f"{len(anomalies_found)/len(det_df)*100:.1f}% of timeline", delta_type="neg" if len(anomalies_found) > 0 else "pos")
    render_kpi(k2, "Critical Incidents", str(crit_count), delta="Immediate action needed", delta_type="neg" if crit_count > 0 else "pos")
    render_kpi(k3, "Warnings", str(warn_count), delta="Elevated traffic patterns", delta_type="neutral")
    render_kpi(k4, "Info Notices", str(info_count), delta="Mild deviations", delta_type="neutral")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Anomaly Scatter Timeline Chart
    st.subheader(f"Timeline Anomaly Markers ({selected_method})")
    timeline_fig = build_anomaly_timeline(
        df=det_df,
        x="hour_ts",
        y="mbps",
        title=f"Bandwidth Telemetry with {selected_method} Anomaly Flags",
        height=380,
        dark_mode=dark_mode
    )
    st.plotly_chart(timeline_fig, use_container_width=True)

    # Ground-Truth Benchmark Evaluation Table
    st.subheader("Model Evaluation vs Ground-Truth Labels")
    eval_results = engine.evaluate_against_ground_truth(start_ts, end_ts)

    eval_rows = []
    for m_name, m_stats in eval_results.items():
        eval_rows.append({
            "Method": m_name,
            "Precision": f"{m_stats['precision']:.3f}",
            "Recall": f"{m_stats['recall']:.3f}",
            "F1-Score": f"{m_stats['f1']:.3f}",
            "True Positives (TP)": m_stats["tp"],
            "False Positives (FP)": m_stats["fp"],
            "False Negatives (FN)": m_stats["fn"]
        })

    eval_df = pd.DataFrame(eval_rows)
    st.dataframe(eval_df, use_container_width=True, hide_index=True)
    st.caption("Evaluation benchmarked against injected synthetic ground truth (exfiltration, runaway updates, backup bursts, congestion).")

    # Interactive Alert Inbox & Acknowledgement
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    st.subheader("Active Alerts & Acknowledgement Workflow")

    alerts_df = repo.get_alerts(unacknowledged_only=False, limit=30)
    if not alerts_df.empty:
        for _, alert in alerts_df.iterrows():
            aid = int(alert["alert_id"])
            is_ack = bool(alert["acknowledged"])
            sev = alert["severity"]
            badge_color = "#A63D40" if sev == "critical" else ("#E0A458" if sev == "warn" else "#B8B2A7")

            col_a1, col_a2 = st.columns([4, 1])
            with col_a1:
                border_c = '#383532' if dark_mode else '#EAE5DC'
                muted_c = '#A8A29A' if dark_mode else '#78726A'
                entity_name = alert['entity_name'] or 'Network Link'
                alert_html = (
                    f'<div style="padding:0.5rem 0;border-bottom:1px solid {border_c};">'
                    f'<span style="background-color:{badge_color};color:#FFFFFF;font-size:0.72rem;'
                    f'padding:0.15rem 0.5rem;border-radius:4px;font-weight:700;text-transform:uppercase;">{sev}</span>'
                    f'<strong style="margin-left:0.5rem;">{alert["reason"]}</strong>'
                    f'<div style="font-size:0.8rem;color:{muted_c};margin-top:0.2rem;">'
                    f'Timestamp: {alert["ts"]} | Entity: {entity_name} | Value: {alert["value"]:.1f} (Baseline: {alert["baseline"]:.1f})'
                    f'</div></div>'
                )
                st.markdown(alert_html, unsafe_allow_html=True)

            with col_a2:
                if is_ack:
                    st.markdown("<span style='color: #7A9E7E; font-size: 0.85rem; font-weight: 600;'>✓ Acknowledged</span>", unsafe_allow_html=True)
                else:
                    if st.button("Acknowledge", key=f"ack_{aid}"):
                        repo.acknowledge_alert(aid)
                        st.rerun()

        download_csv_button(alerts_df, filename="system_alerts.csv", label="Export Alerts CSV")
    else:
        st.info("No system alerts logged.")


if __name__ == "__main__":
    main()
