"""
Page 12: System Settings, Alert Rules, Data Budgets & Database Maintenance.
Configurable thresholds, quiet hours, desktop notification testing (plyer),
monthly device data budgets with projected overrun warnings, and retention job executor.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ui.common import download_csv_button, render_kpi, setup_page

st.set_page_config(page_title="Settings & Budgets", page_icon="⚙️", layout="wide")


def test_desktop_notification() -> bool:
    """Send desktop notification via plyer with graceful fallback."""
    try:
        from plyer import notification
        notification.notify(
            title="Bandwidth Analyzer Alert",
            message="Test notification: Network telemetry monitor is operational.",
            app_name="Bandwidth Analyzer",
            timeout=5
        )
        return True
    except Exception as e:
        return False


def main() -> None:
    repo, filters = setup_page(
        title="Settings, Budgets & Maintenance",
        subtitle="Operational parameters, alert rules, endpoint data quota budgets, and data retention policies."
    )
    dark_mode = filters["dark_mode"]

    tab_alerts, tab_budgets, tab_system, tab_retention = st.tabs([
        "Alert Rules & Quiet Hours",
        "Endpoint Data Budgets",
        "Link & Telemetry Configuration",
        "Data Retention & Storage"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: Alert Rules & Quiet Hours
    # -------------------------------------------------------------------------
    with tab_alerts:
        st.subheader("Thresholds & Notification Policies")

        cur_z = float(repo.get_setting("anomaly_z_threshold", "2.5"))
        cur_util = float(repo.get_setting("congestion_util_threshold", "80.0"))
        cur_lat = float(repo.get_setting("latency_alert_threshold", "60.0"))
        cur_loss = float(repo.get_setting("packet_loss_threshold", "3.0"))

        c1, c2 = st.columns(2)
        with c1:
            new_z = st.number_input("Anomaly Sensitivity (Z-Score σ)", min_value=1.5, max_value=5.0, value=cur_z, step=0.1)
            new_util = st.number_input("Congestion Trigger Threshold (%)", min_value=50.0, max_value=98.0, value=cur_util, step=1.0)
        with c2:
            new_lat = st.number_input("High Latency Alert (ms)", min_value=20.0, max_value=500.0, value=cur_lat, step=5.0)
            new_loss = st.number_input("Packet Loss Threshold (%)", min_value=0.5, max_value=20.0, value=cur_loss, step=0.5)

        st.markdown("---")
        st.subheader("Quiet Hours & Desktop Notifications")

        q_enabled = repo.get_setting("quiet_hours_enabled", "0") == "1"
        q_toggle = st.checkbox("Enable Quiet Hours (Suppress non-critical alerts)", value=q_enabled)

        col_q1, col_q2 = st.columns(2)
        with col_q1:
            q_start = st.time_input("Quiet Hours Start", value=datetime.strptime(repo.get_setting("quiet_hours_start", "22:00"), "%H:%M").time())
        with col_q2:
            q_end = st.time_input("Quiet Hours End", value=datetime.strptime(repo.get_setting("quiet_hours_end", "07:00"), "%H:%M").time())

        notif_enabled = repo.get_setting("desktop_notifications", "0") == "1"
        notif_toggle = st.checkbox("Enable Desktop System Notifications (plyer)", value=notif_enabled)

        if st.button("🔔 Send Test Desktop Notification"):
            success = test_desktop_notification()
            if success:
                st.success("Test notification dispatched to operating system.")
            else:
                st.info("Desktop notifications not supported in this headless or sandbox environment.")

        if st.button("Save Alert Rules", type="primary"):
            repo.set_setting("anomaly_z_threshold", str(new_z))
            repo.set_setting("congestion_util_threshold", str(new_util))
            repo.set_setting("latency_alert_threshold", str(new_lat))
            repo.set_setting("packet_loss_threshold", str(new_loss))
            repo.set_setting("quiet_hours_enabled", "1" if q_toggle else "0")
            repo.set_setting("quiet_hours_start", q_start.strftime("%H:%M"))
            repo.set_setting("quiet_hours_end", q_end.strftime("%H:%M"))
            repo.set_setting("desktop_notifications", "1" if notif_toggle else "0")
            st.success("Alert rules saved successfully!")

    # -------------------------------------------------------------------------
    # TAB 2: Endpoint Data Budgets
    # -------------------------------------------------------------------------
    with tab_budgets:
        st.subheader("Monthly Device Data Budgets & Month-End Projections")
        st.caption("Tracks month-to-date data usage per device and flags projected quota overruns.")

        monthly_quota_gb = float(repo.get_setting("monthly_device_budget_gb", "50.0"))
        new_quota = st.number_input("Default Device Monthly Quota (GB)", min_value=5.0, max_value=1000.0, value=monthly_quota_gb, step=10.0)
        if new_quota != monthly_quota_gb:
            repo.set_setting("monthly_device_budget_gb", str(new_quota))

        # Calculate month-to-date
        now = datetime.now()
        ref_ts = now.strftime("%Y-%m-%d %H:%M:%S")
        day_of_month = now.day
        days_in_month = 30  # approximate

        mtd_df = repo.get_month_to_date_usage(ref_ts)
        if not mtd_df.empty:
            mtd_df["budget_gb"] = new_quota
            # Project month-end usage
            mtd_df["projected_month_end_gb"] = (mtd_df["used_gb"] / max(1, day_of_month) * days_in_month).round(2)
            mtd_df["quota_used_pct"] = ((mtd_df["used_gb"] / new_quota) * 100.0).round(1)

            def get_budget_status(row: pd.Series) -> str:
                proj = row["projected_month_end_gb"]
                if proj > new_quota:
                    return "⚠️ OVERRUN PROJECTED"
                elif row["quota_used_pct"] > 80:
                    return "⚡ WARNING"
                return "✓ ON TRACK"

            mtd_df["status"] = mtd_df.apply(get_budget_status, axis=1)

            display_budget = mtd_df[[
                "hostname", "user_name", "device_type", "used_gb",
                "budget_gb", "quota_used_pct", "projected_month_end_gb", "status"
            ]].rename(columns={
                "hostname": "Device",
                "user_name": "Assigned User",
                "device_type": "Type",
                "used_gb": "Used MTD (GB)",
                "budget_gb": "Quota (GB)",
                "quota_used_pct": "Quota %",
                "projected_month_end_gb": "Projected Total (GB)",
                "status": "Budget Status"
            })

            st.dataframe(display_budget, width="stretch", hide_index=True)
            download_csv_button(display_budget, filename="device_budgets.csv", label="Export Budget Report")
        else:
            st.info("No month-to-date traffic recorded.")

    # -------------------------------------------------------------------------
    # TAB 3: Link & Telemetry Config
    # -------------------------------------------------------------------------
    with tab_system:
        st.subheader("Physical Link & Collector Configuration")

        cur_cap = float(repo.get_setting("capacity_mbps", "100.0"))
        cur_ping = repo.get_setting("ping_host", "8.8.8.8")
        cur_interval = float(repo.get_setting("collector_interval_sec", "2.0"))

        c_s1, c_s2, c_s3 = st.columns(3)
        with c_s1:
            new_cap = st.number_input("Link Bandwidth Capacity (Mbps)", min_value=10.0, max_value=10000.0, value=cur_cap, step=10.0)
        with c_s2:
            new_ping = st.text_input("ICMP Ping Host / IP", value=cur_ping)
        with c_s3:
            new_interval = st.number_input("Collector Polling Interval (Sec)", min_value=1.0, max_value=30.0, value=cur_interval, step=1.0)

        if st.button("Save Link Parameters", type="primary"):
            repo.set_setting("capacity_mbps", str(new_cap))
            repo.set_setting("ping_host", new_ping.strip())
            repo.set_setting("collector_interval_sec", str(new_interval))
            st.success("Link parameters saved successfully!")

    # -------------------------------------------------------------------------
    # TAB 4: Retention & Storage
    # -------------------------------------------------------------------------
    with tab_retention:
        st.subheader("Database Health & Rolling 30-Day Retention Job")
        st.caption("Rolls raw per-sample rows older than 30 days into hourly aggregates to conserve disk storage.")

        db_stats = repo.get_db_stats()

        k1, k2, k3 = st.columns(3)
        render_kpi(k1, "Database Disk Size", f"{db_stats['file_size_mb']} MB", delta="SQLite file")
        render_kpi(k2, "Raw Usage Rows", f"{db_stats['counts'].get('bandwidth_usage', 0):,}", delta="High-frequency samples")
        render_kpi(k3, "Hourly Rolled Rows", f"{db_stats['counts'].get('hourly_aggregates', 0):,}", delta="Archived aggregates")

        st.markdown("---")
        ret_days = st.slider("Retention Threshold (Days)", min_value=7, max_value=90, value=30, step=1)

        if st.button("⚡ Run Retention Rollup & Cleanup Job Now", type="primary"):
            with st.spinner("Archiving raw usage rows into hourly_aggregates..."):
                result = repo.run_retention_job(days_threshold=ret_days)
                st.success(f"Retention job completed! Cutoff: {result.get('cutoff_ts')}. Archived: {result.get('archived_samples')} aggregations, Pruned raw rows: {result.get('deleted_raw')}.")
                st.rerun()


if __name__ == "__main__":
    main()
