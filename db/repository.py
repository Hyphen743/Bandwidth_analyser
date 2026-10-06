"""
Database repository for Bandwidth Usage Monitor and Analyzer.
Wraps SQLite database access and named parameterized queries loaded from queries.sql.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bandwidth.db"
QUERIES_SQL_PATH = Path(__file__).resolve().parent / "queries.sql"
SCHEMA_SQL_PATH = Path(__file__).resolve().parent / "schema.sql"
VIEWS_SQL_PATH = Path(__file__).resolve().parent / "views.sql"


class DatabaseRepository:
    """Repository wrapping SQLite access with parameterized named queries."""

    _queries_cache: Dict[str, str] = {}

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not DatabaseRepository._queries_cache:
            self._load_queries()

    @classmethod
    def _load_queries(cls) -> None:
        """Parse named queries from queries.sql with pattern '-- name: <name>'."""
        if not QUERIES_SQL_PATH.exists():
            return
        content = QUERIES_SQL_PATH.read_text(encoding="utf-8")
        raw_chunks = re.split(r"--\s*name:\s*(\w+)", content)
        # raw_chunks[0] is preamble, subsequent entries are (name, query_text)
        for i in range(1, len(raw_chunks), 2):
            name = raw_chunks[i].strip()
            query = raw_chunks[i + 1].strip()
            cls._queries_cache[name] = query

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def get_query(self, query_name: str) -> str:
        """Retrieve named SQL query text."""
        if query_name not in self._queries_cache:
            self._load_queries()
        if query_name not in self._queries_cache:
            raise KeyError(f"Named query '{query_name}' not found in queries.sql")
        return self._queries_cache[query_name]

    def execute(self, query_name: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Execute a named query and return lastrowid or affected rows."""
        sql = self.get_query(query_name)
        params = params or {}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.lastrowid or cursor.rowcount

    def execute_raw(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Execute arbitrary raw SQL with parameters."""
        params = params or {}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()

    def query_df(self, query_name_or_sql: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Execute a query and return results as a Pandas DataFrame."""
        sql = self._queries_cache.get(query_name_or_sql, query_name_or_sql)
        params = params or {}
        with self.get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    # -------------------------------------------------------------------------
    # Settings Management
    # -------------------------------------------------------------------------
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Fetch a configuration setting by key."""
        df = self.query_df("get_setting", {"key": key})
        if not df.empty and df.iloc[0]["value"] is not None:
            return str(df.iloc[0]["value"])
        return default

    def set_setting(self, key: str, value: Any) -> None:
        """Store or update a configuration setting."""
        self.execute("set_setting", {"key": key, "value": str(value)})

    def get_all_settings(self) -> Dict[str, str]:
        """Fetch all settings as a key-value dictionary."""
        df = self.query_df("get_all_settings")
        if df.empty:
            return {}
        return dict(zip(df["key"], df["value"]))

    # -------------------------------------------------------------------------
    # Entity Lookups & Insertions
    # -------------------------------------------------------------------------
    def get_users(self) -> pd.DataFrame:
        return self.query_df("get_all_users")

    def get_devices(self) -> pd.DataFrame:
        return self.query_df("get_all_devices")

    def get_applications(self) -> pd.DataFrame:
        return self.query_df("get_all_applications")

    def insert_user(self, name: str, role: str) -> int:
        return self.execute("insert_user", {"name": name, "role": role})

    def insert_device(self, user_id: Optional[int], hostname: str, mac: str, ip: str, device_type: str) -> int:
        return self.execute("insert_device", {
            "user_id": user_id,
            "hostname": hostname,
            "mac": mac,
            "ip": ip,
            "device_type": device_type
        })

    def insert_application(self, name: str, category: str) -> int:
        return self.execute("insert_application", {"name": name, "category": category})

    def insert_session(self, device_id: int, app_id: int, start_ts: str, end_ts: Optional[str] = None) -> int:
        return self.execute("insert_session", {
            "device_id": device_id,
            "app_id": app_id,
            "start_ts": start_ts,
            "end_ts": end_ts
        })

    def insert_bandwidth_usage(
        self,
        session_id: Optional[int],
        device_id: int,
        app_id: int,
        ts: str,
        bytes_up: int,
        bytes_down: int,
        source: str = "simulated"
    ) -> int:
        return self.execute("insert_bandwidth_usage", {
            "session_id": session_id,
            "device_id": device_id,
            "app_id": app_id,
            "ts": ts,
            "bytes_up": bytes_up,
            "bytes_down": bytes_down,
            "source": source
        })

    def insert_usage_batch(self, rows: List[Dict[str, Any]]) -> None:
        """Batch insert usage records for high performance."""
        if not rows:
            return
        for r in rows:
            if "source" not in r:
                r["source"] = "simulated"
        sql = self.get_query("insert_bandwidth_usage")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, rows)
            conn.commit()

    def insert_network_metric(
        self,
        ts: str,
        latency_ms: float,
        jitter_ms: float,
        packet_loss_pct: float,
        capacity_mbps: float,
        utilization_pct: float,
        source: str = "simulated"
    ) -> int:
        return self.execute("insert_network_metric", {
            "ts": ts,
            "latency_ms": latency_ms,
            "jitter_ms": jitter_ms,
            "packet_loss_pct": packet_loss_pct,
            "capacity_mbps": capacity_mbps,
            "utilization_pct": utilization_pct,
            "source": source
        })

    def insert_metrics_batch(self, rows: List[Dict[str, Any]]) -> None:
        """Batch insert network metric records."""
        if not rows:
            return
        for r in rows:
            if "source" not in r:
                r["source"] = "simulated"
        sql = self.get_query("insert_network_metric")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, rows)
            conn.commit()

    def insert_speed_test(
        self,
        ts: str,
        download_mbps: float,
        upload_mbps: float,
        ping_ms: float,
        server: Optional[str] = None
    ) -> int:
        """Record real speed test measurements."""
        return self.execute("insert_speed_test", {
            "ts": ts,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "ping_ms": ping_ms,
            "server": server or "Auto"
        })

    def get_speed_tests(self, limit: int = 50) -> pd.DataFrame:
        """Fetch historical speed test measurements."""
        return self.query_df("get_speed_tests", {"limit": limit})

    def insert_alert(
        self,
        ts: str,
        entity_type: str,
        entity_id: Optional[int],
        severity: str,
        reason: str,
        value: float,
        baseline: float
    ) -> int:
        return self.execute("insert_alert", {
            "ts": ts,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "severity": severity,
            "reason": reason,
            "value": value,
            "baseline": baseline
        })

    def get_alerts(
        self,
        unacknowledged_only: bool = False,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        return self.query_df("get_alerts", {
            "unacknowledged_only": 1 if unacknowledged_only else 0,
            "severity": severity,
            "limit": limit
        })

    def acknowledge_alert(self, alert_id: int) -> None:
        self.execute("acknowledge_alert", {"alert_id": alert_id})

    def insert_prediction(
        self,
        ts_generated: str,
        target_ts: str,
        predicted_mbps: float,
        actual_mbps: Optional[float],
        model: str
    ) -> int:
        return self.execute("insert_prediction", {
            "ts_generated": ts_generated,
            "target_ts": target_ts,
            "predicted_mbps": predicted_mbps,
            "actual_mbps": actual_mbps,
            "model": model
        })

    def insert_anomaly_label(
        self,
        ts: str,
        entity_type: str,
        entity_id: Optional[int],
        anomaly_type: str,
        severity: str,
        description: str
    ) -> int:
        return self.execute("insert_anomaly_label", {
            "ts": ts,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "anomaly_type": anomaly_type,
            "severity": severity,
            "description": description
        })

    def get_anomaly_labels(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_anomaly_labels", {"start_ts": start_ts, "end_ts": end_ts})

    # -------------------------------------------------------------------------
    # Analytics & Aggregations
    # -------------------------------------------------------------------------
    def get_app_analytics(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_app_analytics", {"start_ts": start_ts, "end_ts": end_ts})

    def get_app_timeline(self, start_ts: str, end_ts: str, app_id: Optional[int] = None) -> pd.DataFrame:
        return self.query_df("get_app_timeline", {"start_ts": start_ts, "end_ts": end_ts, "app_id": app_id})

    def get_device_analytics(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_device_analytics", {"start_ts": start_ts, "end_ts": end_ts})

    def get_device_timeline(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_device_timeline", {"start_ts": start_ts, "end_ts": end_ts})

    def get_hourly_usage(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_hourly_usage", {"start_ts": start_ts, "end_ts": end_ts})

    def get_daily_usage(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_daily_usage", {"start_ts": start_ts, "end_ts": end_ts})

    def get_hour_by_weekday_heatmap(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_hour_by_weekday_heatmap", {"start_ts": start_ts, "end_ts": end_ts})

    def get_peak_offpeak_stats(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_peak_offpeak_stats", {"start_ts": start_ts, "end_ts": end_ts})

    def get_updown_summary(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_updown_summary", {"start_ts": start_ts, "end_ts": end_ts})

    def get_updown_by_category(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        return self.query_df("get_updown_by_category", {"start_ts": start_ts, "end_ts": end_ts})

    def get_top_apps(self, start_ts: str, end_ts: str, limit: int = 5) -> pd.DataFrame:
        return self.query_df("get_top_apps_in_window", {"start_ts": start_ts, "end_ts": end_ts, "limit": limit})

    def get_top_devices(self, start_ts: str, end_ts: str, limit: int = 5) -> pd.DataFrame:
        return self.query_df("get_top_devices_in_window", {"start_ts": start_ts, "end_ts": end_ts, "limit": limit})

    def get_recent_live_usage(self, since_ts: str, limit: int = 100) -> pd.DataFrame:
        return self.query_df("get_recent_live_usage", {"since_ts": since_ts, "limit": limit})

    def get_recent_metrics(self, since_ts: str) -> pd.DataFrame:
        return self.query_df("get_recent_metrics", {"since_ts": since_ts})

    def get_congestion_metrics(
        self,
        start_ts: str,
        end_ts: str,
        threshold_util: float = 80.0,
        threshold_latency: float = 50.0,
        threshold_loss: float = 2.0
    ) -> pd.DataFrame:
        return self.query_df("get_congestion_metrics", {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "threshold_util": threshold_util,
            "threshold_latency": threshold_latency,
            "threshold_loss": threshold_loss
        })

    def get_congested_interval_offenders(self, start_ts: str, end_ts: str, limit: int = 5) -> pd.DataFrame:
        return self.query_df("get_congested_interval_offenders", {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "limit": limit
        })

    def get_month_to_date_usage(self, reference_ts: str) -> pd.DataFrame:
        return self.query_df("get_month_to_date_device_usage", {"reference_ts": reference_ts})

    # -------------------------------------------------------------------------
    # Maintenance, Range & Retention
    # -------------------------------------------------------------------------
    def get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        """Get minimum and maximum timestamps stored in bandwidth_usage."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MIN(ts), MAX(ts) FROM bandwidth_usage")
            row = cursor.fetchone()
            if row and row[0] and row[1]:
                return row[0], row[1]
            return None, None

    def get_db_stats(self) -> Dict[str, Any]:
        """Fetch database statistics including row counts and disk size."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            counts = {}
            for table in [
                "users", "devices", "applications", "network_sessions",
                "bandwidth_usage", "network_metrics", "alerts",
                "predictions", "anomaly_labels", "hourly_aggregates"
            ]:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    counts[table] = cursor.fetchone()[0]
                except Exception:
                    counts[table] = 0

            file_size_mb = 0.0
            if self.db_path.exists():
                file_size_mb = round(self.db_path.stat().st_size / (1024 * 1024), 2)

            return {
                "file_size_mb": file_size_mb,
                "counts": counts
            }

    def run_retention_job(self, days_threshold: int = 30) -> Dict[str, int]:
        """
        Roll raw bandwidth_usage rows older than `days_threshold` into hourly_aggregates
        and delete raw records to optimize SQLite storage.
        """
        # Determine cutoff timestamp
        min_ts, max_ts = self.get_date_range()
        if not max_ts:
            return {"archived_samples": 0, "deleted_raw": 0}

        try:
            ref_dt = datetime.strptime(max_ts, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            ref_dt = datetime.now()

        cutoff_dt = ref_dt - timedelta(days=days_threshold)
        cutoff_ts = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Archive
            archive_sql = self.get_query("archive_retention_aggregates")
            cursor.execute(archive_sql, {"cutoff_ts": cutoff_ts})
            archived = cursor.rowcount

            # 2. Prune
            prune_sql = self.get_query("prune_raw_usage")
            cursor.execute(prune_sql, {"cutoff_ts": cutoff_ts})
            deleted = cursor.rowcount

            conn.commit()

        return {"archived_samples": archived, "deleted_raw": deleted, "cutoff_ts": cutoff_ts}
