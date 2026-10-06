"""
High-Fidelity 90-Day Bandwidth and Telemetry Simulator.
Generates realistic network traffic with diurnal cycles, weekly seasonality,
and injected labelled anomalies for 5 users, 8 devices, and 12 applications.
"""

from __future__ import annotations

import argparse
import logging
import math
import random
from datetime import datetime, timedelta
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.init_db import init_database
from db.repository import DatabaseRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("simulator")

# Link capacity constant
DEFAULT_CAPACITY_MBPS = 25.0


class NetworkSimulator:
    """Generates synthetic network telemetry and ground-truth labelled anomalies."""

    def __init__(self, repo: DatabaseRepository, days: int = 90) -> None:
        self.repo = repo
        self.days = days
        self.random = random.Random(42)
        np.random.seed(42)

        # Preload IDs
        self.users_df = self.repo.get_users()
        self.devices_df = self.repo.get_devices()
        self.apps_df = self.repo.get_applications()

        self.device_map = {row["hostname"]: row["device_id"] for _, row in self.devices_df.iterrows()}
        self.app_map = {row["name"]: (row["app_id"], row["category"]) for _, row in self.apps_df.iterrows()}

    def generate(self) -> Dict[str, int]:
        """Generate full synthetic dataset and store in SQLite."""
        logger.info("Generating %d days of network traffic...", self.days)

        # Clear existing usage and metrics for clean reproduction
        with self.repo.get_connection() as conn:
            conn.execute("DELETE FROM bandwidth_usage;")
            conn.execute("DELETE FROM network_metrics;")
            conn.execute("DELETE FROM alerts;")
            conn.execute("DELETE FROM anomaly_labels;")
            conn.execute("DELETE FROM network_sessions;")
            conn.execute("DELETE FROM predictions;")
            conn.commit()

        start_time = datetime.now() - timedelta(days=self.days)
        start_time = start_time.replace(minute=0, second=0, microsecond=0)

        usage_batch: List[Dict[str, Any]] = []
        metrics_batch: List[Dict[str, Any]] = []
        alerts_batch: List[Dict[str, Any]] = []
        labels_batch: List[Dict[str, Any]] = []

        total_hours = self.days * 24

        # Predefine anomaly schedule across the timeline
        # (day_offset, hour, anomaly_type)
        anomaly_schedule = {
            (14, 14): "runaway_update",
            (22, 2): "upload_exfiltration",
            (31, 3): "backup_burst",
            (40, 20): "congestion_episode",
            (45, 14): "runaway_update",
            (51, 3): "upload_exfiltration",
            (60, 4): "backup_burst",
            (68, 15): "runaway_update",
            (72, 21): "congestion_episode",
            (79, 2): "upload_exfiltration",
            (83, 3): "backup_burst",
            (87, 20): "congestion_episode"
        }

        for h in range(total_hours):
            current_dt = start_time + timedelta(hours=h)
            current_ts = current_dt.strftime("%Y-%m-%d %H:%M:%S")
            day_offset = h // 24
            hour_of_day = current_dt.hour
            is_weekend = current_dt.weekday() >= 5  # 5=Sat, 6=Sun

            # Base diurnal factor (sinusoidal + evening boost)
            # Troughs at 04:00, peaks at 21:00
            diurnal_wave = 0.4 + 0.35 * math.sin((hour_of_day - 6) * math.pi / 12)
            if is_weekend:
                diurnal_factor = max(0.15, diurnal_wave * 1.2)
                is_work_hours = False
            else:
                is_work_hours = 9 <= hour_of_day <= 17
                diurnal_factor = max(0.1, diurnal_wave)

            # Check if this hour is an injected anomaly
            anomaly_key = (day_offset, hour_of_day)
            active_anomaly = anomaly_schedule.get(anomaly_key, None)

            hour_total_bytes_up = 0
            hour_total_bytes_down = 0

            # Generate app traffic for active devices this hour
            for hostname, dev_id in self.device_map.items():
                active_apps = self._get_active_apps_for_device(
                    hostname, hour_of_day, is_work_hours, is_weekend, active_anomaly
                )

                for app_name, (up_mbps, down_mbps) in active_apps.items():
                    app_id, category = self.app_map[app_name]

                    # Scale by diurnal factor + random jitter + 0.10 realism factor (~1.5 TB for 90 days)
                    jitter = self.random.uniform(0.85, 1.15)
                    SCALE_FACTOR = 0.10
                    actual_up_mbps = max(0.005, up_mbps * diurnal_factor * jitter * SCALE_FACTOR)
                    actual_down_mbps = max(0.005, down_mbps * diurnal_factor * jitter * SCALE_FACTOR)

                    # Anomaly boosts
                    if active_anomaly == "upload_exfiltration" and hostname in ("Office-Server", "Bob-DevStation") and app_name == "Dropbox Backup":
                        actual_up_mbps = self.random.uniform(18.0, 24.0)
                        actual_down_mbps = 0.2
                    elif active_anomaly == "runaway_update" and app_name in ("Windows Update", "System Packages"):
                        actual_down_mbps = self.random.uniform(16.0, 22.0)
                        actual_up_mbps = 0.1
                    elif active_anomaly == "backup_burst" and app_name in ("Google Drive", "Dropbox Backup"):
                        actual_up_mbps = self.random.uniform(10.0, 16.0)
                        actual_down_mbps = 0.8
                    elif active_anomaly == "congestion_episode" and app_name in ("Netflix", "Steam Games", "YouTube"):
                        actual_down_mbps *= 2.8

                    # Convert Mbps to bytes per 1-hour interval
                    # bytes = (mbps * 1,000,000 / 8) * 3600
                    bytes_up = int((actual_up_mbps * 1_000_000 / 8) * 3600)
                    bytes_down = int((actual_down_mbps * 1_000_000 / 8) * 3600)

                    hour_total_bytes_up += bytes_up
                    hour_total_bytes_down += bytes_down

                    usage_batch.append({
                        "session_id": None,
                        "device_id": dev_id,
                        "app_id": app_id,
                        "ts": current_ts,
                        "bytes_up": bytes_up,
                        "bytes_down": bytes_down,
                        "source": "simulated"
                    })

            # Calculate network metrics for this hour
            total_bytes = hour_total_bytes_up + hour_total_bytes_down
            total_mbps = (total_bytes * 8.0) / (3600.0 * 1_000_000.0)
            utilization_pct = min(100.0, round((total_mbps / DEFAULT_CAPACITY_MBPS) * 100.0, 2))

            # Base network health
            if utilization_pct > 80.0:
                # Congestion bufferbloat
                latency_ms = round(self.random.uniform(120.0, 260.0), 1)
                jitter_ms = round(self.random.uniform(35.0, 75.0), 1)
                packet_loss_pct = round(self.random.uniform(3.0, 8.5), 1)
            elif utilization_pct > 60.0:
                latency_ms = round(self.random.uniform(35.0, 70.0), 1)
                jitter_ms = round(self.random.uniform(8.0, 18.0), 1)
                packet_loss_pct = round(self.random.uniform(0.2, 1.2), 1)
            else:
                latency_ms = round(self.random.uniform(14.0, 24.0), 1)
                jitter_ms = round(self.random.uniform(1.2, 4.5), 1)
                packet_loss_pct = 0.0

            metrics_batch.append({
                "ts": current_ts,
                "latency_ms": latency_ms,
                "jitter_ms": jitter_ms,
                "packet_loss_pct": packet_loss_pct,
                "capacity_mbps": DEFAULT_CAPACITY_MBPS,
                "utilization_pct": utilization_pct,
                "source": "simulated"
            })

            # Ground truth anomaly logging & alert injection
            if active_anomaly:
                if active_anomaly == "upload_exfiltration":
                    labels_batch.append({
                        "ts": current_ts,
                        "entity_type": "device",
                        "entity_id": self.device_map["Office-Server"],
                        "anomaly_type": "Upload Exfiltration",
                        "severity": "critical",
                        "description": "Massive uncharacteristic outbound surge detected outside business hours"
                    })
                    alerts_batch.append({
                        "ts": current_ts,
                        "entity_type": "device",
                        "entity_id": self.device_map["Office-Server"],
                        "severity": "critical",
                        "reason": "Abnormal off-hours outbound data surge (>18 Mbps)",
                        "value": 20.4,
                        "baseline": 0.2
                    })
                elif active_anomaly == "runaway_update":
                    labels_batch.append({
                        "ts": current_ts,
                        "entity_type": "application",
                        "entity_id": self.app_map["Windows Update"][0],
                        "anomaly_type": "Runaway Update",
                        "severity": "warn",
                        "description": "Concurrent mass package update saturating downstream bandwidth"
                    })
                    alerts_batch.append({
                        "ts": current_ts,
                        "entity_type": "application",
                        "entity_id": self.app_map["Windows Update"][0],
                        "severity": "warn",
                        "reason": "Runaway background system update spike (>16 Mbps aggregate)",
                        "value": 18.2,
                        "baseline": 0.8
                    })
                elif active_anomaly == "backup_burst":
                    labels_batch.append({
                        "ts": current_ts,
                        "entity_type": "application",
                        "entity_id": self.app_map["Dropbox Backup"][0],
                        "anomaly_type": "Backup Burst Spike",
                        "severity": "info",
                        "description": "Unscheduled large cloud backup snapshot burst"
                    })
                    alerts_batch.append({
                        "ts": current_ts,
                        "entity_type": "application",
                        "entity_id": self.app_map["Dropbox Backup"][0],
                        "severity": "info",
                        "reason": "Scheduled cloud backup payload spike",
                        "value": 14.0,
                        "baseline": 0.5
                    })
                elif active_anomaly == "congestion_episode":
                    labels_batch.append({
                        "ts": current_ts,
                        "entity_type": "network",
                        "entity_id": None,
                        "anomaly_type": "Link Congestion",
                        "severity": "critical",
                        "description": "Link capacity threshold exceeded resulting in severe bufferbloat"
                    })
                    alerts_batch.append({
                        "ts": current_ts,
                        "entity_type": "network",
                        "entity_id": None,
                        "severity": "critical",
                        "reason": f"Link capacity saturation ({utilization_pct}%) with packet loss ({packet_loss_pct}%)",
                        "value": utilization_pct,
                        "baseline": 65.0
                    })

            # Flush in batches of 200 hours to conserve memory
            if len(usage_batch) >= 10000:
                self.repo.insert_usage_batch(usage_batch)
                usage_batch.clear()

        # Flush remaining
        if usage_batch:
            self.repo.insert_usage_batch(usage_batch)
        if metrics_batch:
            self.repo.insert_metrics_batch(metrics_batch)

        for a in alerts_batch:
            self.repo.insert_alert(**a)
        for l in labels_batch:
            self.repo.insert_anomaly_label(**l)

        # Update initial setting
        self.repo.set_setting("data_source", "simulated")

        logger.info(
            "Simulation finished: %d metrics samples, %d alerts, %d anomaly ground-truth labels.",
            len(metrics_batch), len(alerts_batch), len(labels_batch)
        )
        return {
            "hours": total_hours,
            "metrics": len(metrics_batch),
            "alerts": len(alerts_batch),
            "anomalies": len(labels_batch)
        }

    def _get_active_apps_for_device(
        self,
        hostname: str,
        hour: int,
        is_work_hours: bool,
        is_weekend: bool,
        active_anomaly: Any
    ) -> Dict[str, Tuple[float, float]]:
        """
        Determines realistic (upload_mbps, download_mbps) for active apps
        on a specific device given the time of day and schedule.
        """
        apps: Dict[str, Tuple[float, float]] = {}

        # Night time (01:00 - 06:00) baseline
        if 1 <= hour <= 6:
            if hostname == "Office-Server":
                apps["Dropbox Backup"] = (0.4, 0.1)
                apps["System Packages"] = (0.05, 0.2)
            elif hostname == "Smart-TV":
                apps["YouTube"] = (0.01, 0.05)
            return apps

        # Work Hours (09:00 - 17:00, Weekdays)
        if is_work_hours:
            if hostname in ("Bob-DevStation", "David-ThinkPad", "Clara-iMac", "Alice-MacBook"):
                apps["Slack Messaging"] = (0.3, 0.6)
                apps["Chrome Browser"] = (0.8, 3.5)
                if hour in (10, 11, 14, 15):
                    apps["Zoom Meetings"] = (2.2, 2.8)
                if hostname == "Clara-iMac":
                    apps["Google Drive"] = (4.0, 5.5)
                if hostname == "Bob-DevStation":
                    apps["Firefox"] = (0.5, 2.0)
            elif hostname == "Office-Server":
                apps["Google Drive"] = (1.5, 3.0)
                apps["System Packages"] = (0.2, 0.5)
            elif hostname == "Emma-iPhone":
                apps["Slack Messaging"] = (0.1, 0.3)
                apps["Chrome Browser"] = (0.2, 0.8)
            return apps

        # Evening Peak (18:00 - 23:00)
        if 18 <= hour <= 23:
            if hostname == "Smart-TV":
                apps["Netflix"] = (0.2, 14.0)
            if hostname in ("Alice-MacBook", "David-ThinkPad"):
                apps["YouTube"] = (0.2, 8.0)
                apps["Chrome Browser"] = (0.4, 1.8)
            if hostname == "Bob-DevStation":
                apps["Steam Games"] = (1.5, 12.0)
                apps["Discord"] = (0.8, 1.2)
            if hostname == "Emma-iPhone":
                apps["YouTube"] = (0.1, 4.0)
                apps["Slack Messaging"] = (0.1, 0.2)
            if hostname == "Lab-Tablet":
                apps["Netflix"] = (0.1, 6.0)
            return apps

        # Weekend Daytime (10:00 - 18:00)
        if is_weekend and 10 <= hour <= 18:
            if hostname == "Smart-TV":
                apps["YouTube"] = (0.2, 10.0)
            if hostname == "Bob-DevStation":
                apps["Steam Games"] = (2.0, 15.0)
                apps["Discord"] = (1.0, 1.5)
            if hostname in ("Alice-MacBook", "Emma-iPhone"):
                apps["Chrome Browser"] = (0.5, 2.5)
                apps["YouTube"] = (0.2, 5.0)
            return apps

        # Default fallback for other hours
        apps["Chrome Browser"] = (0.2, 1.0)
        return apps


def main() -> None:
    parser = argparse.ArgumentParser(description="Bandwidth & Telemetry Simulator")
    parser.add_argument("--days", type=int, default=90, help="Number of days of data to generate (default: 90)")
    args = parser.parse_args()

    init_database()
    repo = DatabaseRepository()
    simulator = NetworkSimulator(repo, days=args.days)
    stats = simulator.generate()
    print(f"Simulation completed successfully: {stats}")


if __name__ == "__main__":
    main()
