"""
Device and User Bandwidth Analytics.
Evaluates cross-device utilization, user-level aggregations,
and historical z-score anomalies per device.
"""

from __future__ import annotations

from typing import Any, Dict, List
import numpy as np
import pandas as pd
from db.repository import DatabaseRepository


class DeviceAnalytics:
    """Analytical engine for device- and user-level bandwidth consumption."""

    def __init__(self, repo: DatabaseRepository) -> None:
        self.repo = repo

    def get_device_summary(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Fetch device summaries with GB, upload/download split and network share."""
        df = self.repo.get_device_analytics(start_ts, end_ts)
        if df.empty or df["total_bytes"].sum() == 0:
            df["pct_contribution"] = 0.0
            return df

        total = df["total_bytes"].sum()
        df["pct_contribution"] = ((df["total_bytes"] / total) * 100.0).round(2)
        df["gb_up"] = (df["total_bytes_up"] / (1024.0 ** 3)).round(3)
        df["gb_down"] = (df["total_bytes_down"] / (1024.0 ** 3)).round(3)
        return df

    def get_user_summary(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Aggregate usage across all devices mapped to each user."""
        df = self.get_device_summary(start_ts, end_ts)
        if df.empty:
            return pd.DataFrame()
        user_df = df.groupby(["user_id", "user_name", "user_role"]).agg(
            total_bytes=("total_bytes", "sum"),
            total_gb=("total_gb", "sum"),
            gb_up=("gb_up", "sum"),
            gb_down=("gb_down", "sum"),
            device_count=("device_id", "count")
        ).reset_index()
        total = user_df["total_bytes"].sum()
        user_df["pct_contribution"] = ((user_df["total_bytes"] / total) * 100.0).round(2) if total > 0 else 0.0
        return user_df.sort_values(by="total_bytes", ascending=False)

    def detect_unusual_device_consumption(
        self,
        start_ts: str,
        end_ts: str,
        z_threshold: float = 2.0
    ) -> pd.DataFrame:
        """
        Calculates device daily traffic and scores unusual spikes against
        each device's historical mean and standard deviation.
        """
        # Fetch daily usage per device across the entire history
        sql = """
        SELECT 
            d.device_id,
            d.hostname,
            strftime('%Y-%m-%d', b.ts) AS date_str,
            SUM(b.bytes_up + b.bytes_down) AS daily_bytes
        FROM devices d
        JOIN bandwidth_usage b ON d.device_id = b.device_id
        GROUP BY d.device_id, d.hostname, date_str
        ORDER BY d.device_id, date_str ASC;
        """
        daily_df = self.repo.query_df(sql)
        if daily_df.empty:
            return pd.DataFrame()

        records = []
        for dev_id, group in daily_df.groupby("device_id"):
            mean_bytes = group["daily_bytes"].mean()
            std_bytes = group["daily_bytes"].std()
            if std_bytes is None or std_bytes == 0 or np.isnan(std_bytes):
                std_bytes = 1.0

            # Filter to requested window
            window_group = group[(group["date_str"] >= start_ts[:10]) & (group["date_str"] <= end_ts[:10])]
            for _, row in window_group.iterrows():
                val = row["daily_bytes"]
                z = (val - mean_bytes) / std_bytes
                if z >= z_threshold:
                    records.append({
                        "device_id": dev_id,
                        "hostname": row["hostname"],
                        "date": row["date_str"],
                        "daily_gb": round(val / (1024.0 ** 3), 3),
                        "historical_avg_gb": round(mean_bytes / (1024.0 ** 3), 3),
                        "z_score": round(z, 2),
                        "severity": "critical" if z >= 3.5 else "warn"
                    })

        return pd.DataFrame(records).sort_values(by="z_score", ascending=False) if records else pd.DataFrame()

    def get_extremes(self, start_ts: str, end_ts: str) -> Dict[str, Any]:
        """Return highest and lowest consuming devices."""
        df = self.get_device_summary(start_ts, end_ts)
        if df.empty:
            return {"highest": None, "lowest": None}
        sorted_df = df.sort_values(by="total_bytes", ascending=False)
        return {
            "highest": sorted_df.iloc[0].to_dict(),
            "lowest": sorted_df.iloc[-1].to_dict()
        }
