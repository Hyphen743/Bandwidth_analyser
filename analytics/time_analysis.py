"""
Time-Based Bandwidth Analytics.
Computes temporal distributions: hourly, daily, weekly, monthly,
peak vs off-peak, weekday vs weekend, and hour-by-weekday matrix.
"""

from __future__ import annotations

from typing import Any, Dict
import pandas as pd
from db.repository import DatabaseRepository

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


class TimeAnalytics:
    """Analytical engine for temporal bandwidth patterns and peak discovery."""

    def __init__(self, repo: DatabaseRepository) -> None:
        self.repo = repo

    def get_hourly_series(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Fetch hourly aggregated bandwidth time series with Mbps."""
        return self.repo.get_hourly_usage(start_ts, end_ts)

    def get_daily_series(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Fetch daily aggregated bandwidth series with total GB."""
        return self.repo.get_daily_usage(start_ts, end_ts)

    def get_weekly_series(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Group usage by calendar week."""
        sql = """
        SELECT 
            strftime('%Y-W%W', ts) AS week_bucket,
            SUM(bytes_up) AS total_bytes_up,
            SUM(bytes_down) AS total_bytes_down,
            SUM(bytes_up + bytes_down) AS total_bytes,
            ROUND(SUM(bytes_up + bytes_down) / (1024.0 * 1024.0 * 1024.0), 3) AS total_gb
        FROM bandwidth_usage
        WHERE ts BETWEEN :start_ts AND :end_ts
        GROUP BY week_bucket
        ORDER BY week_bucket ASC;
        """
        return self.repo.query_df(sql, {"start_ts": start_ts, "end_ts": end_ts})

    def get_monthly_series(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Group usage by calendar month."""
        sql = """
        SELECT 
            strftime('%Y-%m', ts) AS month_bucket,
            SUM(bytes_up) AS total_bytes_up,
            SUM(bytes_down) AS total_bytes_down,
            SUM(bytes_up + bytes_down) AS total_bytes,
            ROUND(SUM(bytes_up + bytes_down) / (1024.0 * 1024.0 * 1024.0), 3) AS total_gb
        FROM bandwidth_usage
        WHERE ts BETWEEN :start_ts AND :end_ts
        GROUP BY month_bucket
        ORDER BY month_bucket ASC;
        """
        return self.repo.query_df(sql, {"start_ts": start_ts, "end_ts": end_ts})

    def get_peak_offpeak(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Return business hours vs evening peak vs off-peak consumption."""
        df = self.repo.get_peak_offpeak_stats(start_ts, end_ts)
        if df.empty:
            return df
        total = df["total_bytes"].sum()
        df["pct_share"] = ((df["total_bytes"] / total) * 100.0).round(2) if total > 0 else 0.0
        df["total_gb"] = (df["total_bytes"] / (1024.0 ** 3)).round(3)
        return df

    def get_weekday_vs_weekend(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Compare hourly profiles between Weekday and Weekend."""
        sql = """
        SELECT 
            CASE WHEN CAST(strftime('%w', ts) AS INTEGER) IN (0, 6) THEN 'Weekend' ELSE 'Weekday' END AS day_type,
            CAST(strftime('%H', ts) AS INTEGER) AS hour_of_day,
            ROUND(AVG(bytes_up + bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS avg_mbps,
            ROUND(SUM(bytes_up + bytes_down) / (1024.0 * 1024.0 * 1024.0), 3) AS total_gb
        FROM bandwidth_usage
        WHERE ts BETWEEN :start_ts AND :end_ts
        GROUP BY day_type, hour_of_day
        ORDER BY day_type, hour_of_day ASC;
        """
        return self.repo.query_df(sql, {"start_ts": start_ts, "end_ts": end_ts})

    def get_hour_weekday_matrix(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """
        Produce a 7x24 pivot matrix of average Mbps for heatmap visualization.
        Index: Day names (Sunday to Saturday), Columns: Hour (0 to 23).
        """
        raw_df = self.repo.get_hour_by_weekday_heatmap(start_ts, end_ts)
        if raw_df.empty:
            return pd.DataFrame()

        # Pivot
        pivot = raw_df.pivot(index="day_of_week", columns="hour_of_day", values="avg_mbps").fillna(0.0)
        # Reindex days to 0..6
        pivot = pivot.reindex(index=range(7), columns=range(24), fill_value=0.0)
        pivot.index = DAY_NAMES
        return pivot

    def get_peak_periods(self, start_ts: str, end_ts: str) -> Dict[str, Any]:
        """Find highest and lowest traffic hours within the range."""
        hourly = self.get_hourly_series(start_ts, end_ts)
        if hourly.empty:
            return {"peak_hour": None, "trough_hour": None}

        peak_row = hourly.loc[hourly["mbps"].idxmax()].to_dict()
        trough_row = hourly.loc[hourly["mbps"].idxmin()].to_dict()
        return {
            "peak_hour": peak_row,
            "trough_hour": trough_row
        }
