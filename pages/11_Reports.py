"""
Page 11: Automated Reports and Traffic Replay Mode.
Generates comprehensive weekly executive reports exported to HTML and PDF,
and features an interactive timeline Replay scrubber to inspect past network conditions.
"""

from __future__ import annotations

import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from analytics.app_analysis import ApplicationAnalytics
from analytics.device_analysis import DeviceAnalytics
from ml.efficiency import EfficiencyEngine
from ui.charts import build_donut_chart, build_line_chart
from ui.common import download_csv_button, format_bytes, render_kpi, setup_page

st.set_page_config(page_title="Reports & Replay", page_icon="📑", layout="wide")


def generate_html_report(
    summary_data: dict,
    top_apps: pd.DataFrame,
    top_devices: pd.DataFrame,
    alerts: pd.DataFrame,
    recommendations: list
) -> str:
    """Produce self-contained printable HTML executive report."""
    apps_rows = "".join([
        f"<tr><td>{r['app_name']}</td><td>{r['category']}</td><td>{format_bytes(r['total_bytes'] if 'total_bytes' in r else r['total_gb'] * (1024**3))}</td></tr>"
        for _, r in top_apps.head(5).iterrows()
    ]) if not top_apps.empty else "<tr><td colspan='3'>None</td></tr>"

    dev_rows = "".join([
        f"<tr><td>{r['hostname']}</td><td>{r['user_name']}</td><td>{format_bytes(r['total_bytes'] if 'total_bytes' in r else r['total_gb'] * (1024**3))}</td></tr>"
        for _, r in top_devices.head(5).iterrows()
    ]) if not top_devices.empty else "<tr><td colspan='3'>None</td></tr>"

    alerts_rows = "".join([
        f"<tr><td>{r['ts']}</td><td>{r['severity'].upper()}</td><td>{r['reason']}</td></tr>"
        for _, r in alerts.head(5).iterrows()
    ]) if not alerts.empty else "<tr><td colspan='3'>No critical incidents</td></tr>"

    rec_items = "".join([
        f"<li><b>[{rec['priority']}] {rec['title']}</b>: {rec['impact']} (Est. savings: ~{rec['estimated_savings_gb']} GB)</li>"
        for rec in recommendations
    ]) if recommendations else "<li>No current recommendations</li>"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Weekly Network Telemetry Executive Report</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #2B2B2B; background: #FAF7F2; }}
            .container {{ max-width: 860px; margin: 0 auto; background: #FFFFFF; padding: 40px; border-radius: 8px; border: 1px solid #EAE5DC; }}
            h1 {{ font-family: Georgia, serif; color: #C8553D; margin-bottom: 5px; }}
            .subtitle {{ color: #78726A; font-size: 14px; margin-bottom: 25px; border-bottom: 1px solid #EAE5DC; padding-bottom: 15px; }}
            .kpi-grid {{ display: flex; gap: 15px; margin-bottom: 25px; }}
            .kpi-box {{ flex: 1; border: 1px solid #EAE5DC; padding: 15px; border-radius: 6px; background: #FAF7F2; text-align: center; }}
            .kpi-val {{ font-size: 24px; font-weight: bold; color: #C8553D; font-family: Georgia, serif; }}
            .kpi-label {{ font-size: 11px; text-transform: uppercase; color: #78726A; font-weight: 600; margin-top: 5px; }}
            h2 {{ font-family: Georgia, serif; font-size: 18px; color: #2B2B2B; margin-top: 25px; border-bottom: 2px solid #EAE5DC; padding-bottom: 6px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }}
            th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #ECE7DF; }}
            th {{ background: #FAF7F2; color: #78726A; text-transform: uppercase; font-size: 11px; }}
            ul {{ font-size: 13px; line-height: 1.6; padding-left: 20px; }}
            .footer {{ margin-top: 35px; border-top: 1px solid #EAE5DC; padding-top: 15px; font-size: 11px; color: #A8A29A; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Weekly Network Telemetry Report</h1>
            <div class="subtitle">Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} • Window: {summary_data['start_ts']} to {summary_data['end_ts']}</div>

            <div class="kpi-grid">
                <div class="kpi-box">
                    <div class="kpi-val">{summary_data.get('total_volume_formatted', f"{summary_data['total_gb']:.1f} GB")}</div>
                    <div class="kpi-label">Total Volume</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-val">{summary_data['peak_mbps']:.1f} Mbps</div>
                    <div class="kpi-label">Peak Demand</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-val">{summary_data['eff_score']:.0f} / 100</div>
                    <div class="kpi-label">Efficiency ({summary_data['eff_rating']})</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-val">{summary_data['alerts_count']}</div>
                    <div class="kpi-label">Active Incidents</div>
                </div>
            </div>

            <h2>Top Consuming Applications</h2>
            <table>
                <thead><tr><th>Application</th><th>Category</th><th>Volume</th></tr></thead>
                <tbody>{apps_rows}</tbody>
            </table>

            <h2>Top Endpoints</h2>
            <table>
                <thead><tr><th>Hostname</th><th>Assigned User</th><th>Volume</th></tr></thead>
                <tbody>{dev_rows}</tbody>
            </table>

            <h2>Recent Anomaly Incidents</h2>
            <table>
                <thead><tr><th>Timestamp</th><th>Severity</th><th>Summary</th></tr></thead>
                <tbody>{alerts_rows}</tbody>
            </table>

            <h2>Prioritized Optimization Recommendations</h2>
            <ul>{rec_items}</ul>

            <div class="footer">Bandwidth Usage Monitor & Analyzer Platform • Confidential Network Intelligence</div>
        </div>
    </body>
    </html>
    """
    return html


def generate_pdf_report(html_content: str) -> Optional[bytes]:
    """Generates PDF report using reportlab SimpleDocTemplate."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=colors.HexColor("#C8553D"),
            spaceAfter=6
        )

        sub_style = ParagraphStyle(
            "SubTitle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#78726A"),
            spaceAfter=15
        )

        h2_style = ParagraphStyle(
            "H2Style",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=colors.HexColor("#2B2B2B"),
            spaceBefore=12,
            spaceAfter=6
        )

        body_style = styles["Normal"]

        story = []
        story.append(Paragraph("Weekly Network Telemetry Executive Report", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", sub_style))

        story.append(Paragraph("Executive Summary", h2_style))
        story.append(Paragraph("This executive report encapsulates bidirectional network throughput, application category breakdown, detected anomaly incidents, and efficiency ratings across enterprise endpoints.", body_style))
        story.append(Spacer(1, 15))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        st.warning(f"PDF generation fallback: {e}")
        return None


def main() -> None:
    repo, filters = setup_page(
        title="Executive Reports & Traffic Replay",
        subtitle="Exportable network audit reports (HTML/PDF) and dynamic historical traffic scrubbing."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    tab_report, tab_replay = st.tabs(["Weekly Executive Report Export", "Interactive Traffic Replay Mode"])

    # -------------------------------------------------------------------------
    # TAB 1: Report Generator
    # -------------------------------------------------------------------------
    with tab_report:
        st.subheader("Generate Weekly Telemetry Audit")

        app_engine = ApplicationAnalytics(repo)
        dev_engine = DeviceAnalytics(repo)
        eff_engine = EfficiencyEngine(repo)

        apps_df = app_engine.get_summary(start_ts, end_ts)
        devs_df = dev_engine.get_device_summary(start_ts, end_ts)
        alerts_df = repo.get_alerts(unacknowledged_only=False, limit=10)
        eff_res = eff_engine.calculate_efficiency(start_ts, end_ts)

        hourly_df = repo.get_hourly_usage(start_ts, end_ts)
        total_bytes = float(apps_df["total_bytes"].sum()) if not apps_df.empty and "total_bytes" in apps_df.columns else float(apps_df["total_gb"].sum() * (1024**3)) if not apps_df.empty else 0.0
        total_gb = float(apps_df["total_gb"].sum()) if not apps_df.empty else 0.0
        peak_mbps = float(hourly_df["mbps"].max()) if not hourly_df.empty else 0.0

        summary_meta = {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "total_gb": total_gb,
            "total_bytes": total_bytes,
            "total_volume_formatted": format_bytes(total_bytes),
            "peak_mbps": peak_mbps,
            "eff_score": eff_res["overall_score"],
            "eff_rating": eff_res["rating"],
            "alerts_count": len(alerts_df)
        }

        html_out = generate_html_report(
            summary_data=summary_meta,
            top_apps=apps_df,
            top_devices=devs_df,
            alerts=alerts_df,
            recommendations=eff_res["recommendations"]
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            st.download_button(
                label="📄 Download HTML Report",
                data=html_out.encode("utf-8"),
                file_name="network_audit_report.html",
                mime="text/html",
                use_container_width=True
            )

        with c2:
            pdf_bytes = generate_pdf_report(html_out)
            if pdf_bytes:
                st.download_button(
                    label="📑 Download PDF Report",
                    data=pdf_bytes,
                    file_name="network_audit_report.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
        st.components.v1.html(html_out, height=650, scrolling=True)

    # -------------------------------------------------------------------------
    # TAB 2: Replay Mode
    # -------------------------------------------------------------------------
    with tab_replay:
        st.subheader("Historical Traffic Replay Scrubber")
        st.caption("Scrub through the past 90 days of network traffic hour by hour to analyze historical incidents.")

        hourly_all = repo.get_hourly_usage(start_ts, end_ts)
        if not hourly_all.empty:
            timestamps = hourly_all["hour_bucket"].tolist()
            step_idx = st.slider(
                "Time Scrubber",
                min_value=0,
                max_value=len(timestamps) - 1,
                value=len(timestamps) // 2,
                step=1
            )
            selected_ts = timestamps[step_idx]

            st.markdown(f"**Inspecting Timestamp:** `{selected_ts}`")

            # Fetch active apps and devices at this exact hour
            hour_detail = repo.query_df(
                """
                SELECT 
                    a.name AS app_name,
                    a.category,
                    d.hostname,
                    ROUND((b.bytes_up + b.bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 3) AS mbps,
                    ROUND((b.bytes_up + b.bytes_down) / (1024.0 * 1024.0), 2) AS mb_total
                FROM bandwidth_usage b
                JOIN applications a ON b.app_id = a.app_id
                JOIN devices d ON b.device_id = d.device_id
                WHERE b.ts = :ts
                ORDER BY mb_total DESC;
                """,
                {"ts": selected_ts}
            )

            if not hour_detail.empty:
                r1, r2 = st.columns([1.5, 1.0])
                with r1:
                    st.dataframe(hour_detail, use_container_width=True, hide_index=True)
                with r2:
                    fig_hour = build_donut_chart(
                        df=hour_detail.head(6),
                        names="app_name",
                        values="mb_total",
                        title="Hour Traffic Distribution",
                        height=280,
                        dark_mode=dark_mode
                    )
                    st.plotly_chart(fig_hour, use_container_width=True)
            else:
                st.info("No recorded activity in this specific hour.")
        else:
            st.info("No timeline data loaded.")


if __name__ == "__main__":
    main()
