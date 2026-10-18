"""
Page 1: Live Network Monitoring and Telemetry Probe.
Real-time psutil traffic counters, active socket processes,
ping probe latency/loss, and protocol breakdown.
"""

from __future__ import annotations

import sys
import json
from urllib.request import Request, urlopen
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
        subtitle="Live interface counters, active socket ownership, and latency probes. Per-process byte totals are not available from socket counts alone."
    )
    dark_mode = filters["dark_mode"]

    collector = LiveCollector.get_instance(repo)
    mapper = ProcessMapper()

    # Collector Controls
    c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 2])
    with c_btn1:
        if collector.is_running():
            if st.button("⏹ Stop Live Collector", width="stretch"):
                st.session_state["live_collector_manually_stopped"] = True
                collector.stop()
                st.rerun()
        else:
            if st.button("▶ Start Live Collector", type="primary", width="stretch"):
                st.session_state["live_collector_manually_stopped"] = False
                collector.start(interval_sec=2.0)
                st.rerun()

    with c_btn2:
        auto_refresh = st.checkbox("Live Polling (2s)", value=False, key="live_page_polling_opt_in_v2")

    with c_btn3:
        status_color = "#5C8065" if collector.is_running() else "#A63D40"
        if collector.is_running():
            status_text = "COLLECTOR ACTIVE (SAMPLING EVERY 2S)"
        else:
            status_text = "COLLECTOR PAUSED"
        st.markdown(
            f'<div style="font-size:0.8rem;font-weight:600;color:{status_color};padding-top:0.6rem;letter-spacing:0.05em;">● {status_text}</div>',
            unsafe_allow_html=True
        )

    st.subheader("Internet Speed Test")
    st.caption("Tests against nearby Chennai and Bengaluru servers, then picks the one with the lowest measured latency. The test transfers data and may briefly affect other internet activity.")
    if st.button("Run Speed Test", type="primary", disabled=st.session_state.get("speed_test_running", False)):
        st.session_state["speed_test_running"] = True
        st.session_state.pop("speed_test_result", None)
        try:
            with st.spinner("Checking Chennai and Bengaluru servers, then measuring your connection…"):
                import speedtest

                tester = speedtest.Speedtest(secure=True)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/132.0.0.0 Safari/537.36",
                    "Referer": "https://www.speedtest.net/",
                }
                candidates = []
                lookup_errors = []
                for city in ("Chennai", "Bangalore"):
                    endpoint = (
                        "https://www.speedtest.net/api/js/servers"
                        f"?engine=js&limit=100&search={city}"
                    )
                    try:
                        request = Request(endpoint, headers=headers)
                        with urlopen(request, timeout=12) as response:
                            directory = json.loads(response.read().decode("utf-8"))

                        city_servers = []
                        for server in directory:
                            if (
                                str(server.get("country", "")).casefold() != "india"
                                or str(server.get("name", "")).casefold() != city.casefold()
                                or not server.get("url")
                                or not server.get("https_functional")
                            ):
                                continue
                            candidate = dict(server)
                            candidate["d"] = float(server.get("distance", float("inf")))
                            city_servers.append(candidate)

                        city_servers.sort(key=lambda server: server["d"])
                        candidates.extend(city_servers[:3])
                    except Exception as exc:
                        lookup_errors.append(f"{city}: {exc}")

                if not candidates:
                    details = "; ".join(lookup_errors)
                    raise RuntimeError(
                        "No Chennai or Bengaluru server is currently available. "
                        "The test stopped instead of selecting an international server. "
                        f"{details}"
                    )

                # Compare a small shortlist from each city using real round-trip
                # latency; don't rely on IP geolocation or an international fallback.
                tester.get_best_server(candidates)
                download_mbps = tester.download() / 1_000_000
                upload_mbps = tester.upload() / 1_000_000
                result = {
                    "Download": f"{download_mbps:.1f} Mbps",
                    "Upload": f"{upload_mbps:.1f} Mbps",
                    "Ping": f"{tester.results.ping:.0f} ms",
                    "Server": f"{tester.results.server.get('name', 'Selected server')}, India",
                }
                st.session_state["speed_test_result"] = result
        except Exception as exc:
            st.error(f"Speed test failed: {exc}")
        finally:
            st.session_state["speed_test_running"] = False

    if st.session_state.get("speed_test_result"):
        speed_result = st.session_state["speed_test_result"]
        test_cols = st.columns(4)
        for column, label in zip(test_cols, ("Download", "Upload", "Ping", "Server")):
            column.metric(label, speed_result[label])

    @st.fragment(run_every=2 if auto_refresh else None)
    def render_live_view() -> None:
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
            st.caption("Shows running processes with established connections, including background services. Unrecognized programs keep their executable names.")
            active_items = mapper.scan_active_connections()
            if active_items:
                proc_df = pd.DataFrame(active_items)
                display_df = pd.DataFrame({
                    "PID": proc_df["pid"], "Process": proc_df["process_name"],
                    "Application": proc_df["app_name"], "Category": proc_df["category"],
                    "Connections": proc_df["connections_count"],
                    "Remote Target": proc_df["remote_ips"].apply(lambda ips: ips[0] if ips else "Local/Loopback")
                })
                st.dataframe(display_df, width="stretch", hide_index=True)
                download_csv_button(display_df, filename="active_processes.csv", label="Export Processes")
            else:
                st.info("No established sockets are visible to this process. Windows permissions can limit socket visibility.")

        with col_proto:
            st.subheader("Protocol Distribution")
            proto_dist = mapper.get_protocol_distribution()
            proto_df = pd.DataFrame(list(proto_dist.items()), columns=["Protocol", "Percentage"])
            if proto_df.empty:
                st.info("No active protocol data is available.")
            else:
                fig_donut = build_donut_chart(
                    df=proto_df, names="Protocol", values="Percentage",
                    height=280, dark_mode=dark_mode
                )
                st.plotly_chart(fig_donut, width="stretch")

        st.subheader("Probe Telemetry (Latency & Jitter History)")
        metrics_history = repo.query_df(
            """
            SELECT ts, latency_ms, jitter_ms, packet_loss_pct, utilization_pct
            FROM network_metrics ORDER BY ts DESC LIMIT 40;
            """
        )

        if not metrics_history.empty:
            metrics_history = metrics_history.sort_values(by="ts")
            fig_lat = build_line_chart(
                df=metrics_history, x="ts", y=["latency_ms", "jitter_ms"],
                title="Latency & Jitter (ms)", y_label="ms", height=300,
                dark_mode=dark_mode
            )
            st.plotly_chart(fig_lat, width="stretch")
            download_csv_button(metrics_history, filename="live_telemetry_history.csv", label="Export Ping Telemetry")

    render_live_view()


if __name__ == "__main__":
    main()
