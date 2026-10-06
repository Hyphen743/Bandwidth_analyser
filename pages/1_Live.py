"""
Page 1: Live Network Monitoring and Telemetry Probe.
Real-time psutil traffic counters, active socket processes,
ping probe latency/loss, and protocol breakdown.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from collector.live_collector import LiveCollector
from collector.process_mapper import ProcessMapper
from ui.charts import build_donut_chart, build_line_chart
from ui.common import download_csv_button, render_kpi, setup_page

st.set_page_config(page_title="Live Network Monitor", page_icon="⚡", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Live Network Telemetry",
        subtitle="Real-time process attribution, interface counters, and low-level latency probes."
    )
    dark_mode = filters["dark_mode"]

    collector = LiveCollector.get_instance(repo)
    mapper = ProcessMapper()

    # Collector Controls
    c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 2])
    with c_btn1:
        if collector.is_running():
            if st.button("⏹ Stop Live Collector", use_container_width=True):
                collector.stop()
                st.rerun()
        else:
            if st.button("▶ Start Live Collector", type="primary", use_container_width=True):
                collector.start(interval_sec=2.0)
                st.rerun()

    with c_btn2:
        auto_refresh = st.checkbox("Live Polling (2s)", value=collector.is_running())

    with c_btn3:
        status_color = "#5C8065" if collector.is_running() else "#A63D40"
        status_text = "COLLECTOR ACTIVE (SAMPLING EVERY 2S)" if collector.is_running() else "COLLECTOR PAUSED"
        st.markdown(f"""
        <div style="font-size: 0.8rem; font-weight: 600; color: {status_color}; padding-top: 0.6rem; letter-spacing: 0.05em;">
            ● {status_text}
        </div>
        """, unsafe_allow_html=True)

    stats = collector.get_latest_stats()

    # Telemetry KPI Row
    k1, k2, k3, k4 = st.columns(4)
    render_kpi(k1, "Live Upload", f"{stats['mbps_up']:.2f} Mbps", delta="psutil counters", delta_type="neutral")
    render_kpi(k2, "Live Download", f"{stats['mbps_down']:.2f} Mbps", delta="psutil counters", delta_type="neutral")
    render_kpi(k3, "Round-Trip Latency", f"{stats['latency_ms']:.1f} ms", delta=f"Jitter ±{stats['jitter_ms']:.1f} ms", delta_type="neutral")
    render_kpi(k4, "Packet Loss", f"{stats['packet_loss_pct']:.1f}%", delta="ICMP probe", delta_type="neg" if stats["packet_loss_pct"] > 0 else "pos")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    col_procs, col_proto = st.columns([2, 1])

    with col_procs:
        st.subheader("Active Network Processes & Sockets")
        active_items = mapper.scan_active_connections()
        if active_items:
            proc_df = pd.DataFrame(active_items)
            display_df = pd.DataFrame({
                "PID": proc_df["pid"],
                "Process": proc_df["process_name"],
                "Application": proc_df["app_name"],
                "Category": proc_df["category"],
                "Connections": proc_df["connections_count"],
                "Remote Target": proc_df["remote_ips"].apply(lambda ips: ips[0] if ips else "Local/Loopback")
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            download_csv_button(display_df, filename="active_processes.csv", label="Export Processes")
        else:
            st.info("No active sockets detected on local network interface.")

    with col_proto:
        st.subheader("Protocol Distribution")
        proto_dist = mapper.get_protocol_distribution()
        proto_df = pd.DataFrame(list(proto_dist.items()), columns=["Protocol", "Percentage"])
        fig_donut = build_donut_chart(
            df=proto_df,
            names="Protocol",
            values="Percentage",
            height=280,
            dark_mode=dark_mode
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # Ping Probe Telemetry History
    st.subheader("Probe Telemetry (Latency & Jitter History)")
    now_str = stats.get("last_sample_ts") or time.strftime("%Y-%m-%d %H:%M:%S")
    metrics_history = repo.query_df(
        """
        SELECT ts, latency_ms, jitter_ms, packet_loss_pct, utilization_pct
        FROM network_metrics
        ORDER BY ts DESC
        LIMIT 40;
        """
    )

    if not metrics_history.empty:
        metrics_history = metrics_history.sort_values(by="ts")
        fig_lat = build_line_chart(
            df=metrics_history,
            x="ts",
            y=["latency_ms", "jitter_ms"],
            title="Latency & Jitter (ms)",
            y_label="ms",
            height=300,
            dark_mode=dark_mode
        )
        st.plotly_chart(fig_lat, use_container_width=True)
        download_csv_button(metrics_history, filename="live_telemetry_history.csv", label="Export Ping Telemetry")

    if auto_refresh:
        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    main()
