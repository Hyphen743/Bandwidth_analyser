"""
Application Bandwidth Analytics.
Computes application consumption summaries, min/avg/max statistics,
upload vs download distribution, and time-series trends.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import pandas as pd
from db.repository import DatabaseRepository


class ApplicationAnalytics:
    """Analytical engine for application-level bandwidth metrics."""

    def __init__(self, repo: DatabaseRepository) -> None:
        self.repo = repo

    def get_summary(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """
        Get aggregated application consumption with percentage contribution,
        min/avg/max bytes per sample, and upload/download breakdown.
        """
        df = self.repo.get_app_analytics(start_ts, end_ts)
        if df.empty or df["total_bytes"].sum() == 0:
            df["pct_contribution"] = 0.0
            return df

        total_network_bytes = df["total_bytes"].sum()
        df["pct_contribution"] = ((df["total_bytes"] / total_network_bytes) * 100.0).round(2)
        df["gb_up"] = (df["total_bytes_up"] / (1024.0 ** 3)).round(3)
        df["gb_down"] = (df["total_bytes_down"] / (1024.0 ** 3)).round(3)
        df["up_down_ratio"] = (df["total_bytes_up"] / df["total_bytes_down"].replace(0, 1)).round(3)
        return df

    def get_category_breakdown(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Aggregate usage by application category."""
        df = self.get_summary(start_ts, end_ts)
        if df.empty:
            return pd.DataFrame()
        cat_df = df.groupby("category").agg(
            total_bytes=("total_bytes", "sum"),
            total_gb=("total_gb", "sum"),
            total_bytes_up=("total_bytes_up", "sum"),
            total_bytes_down=("total_bytes_down", "sum"),
            app_count=("app_id", "count")
        ).reset_index()
        total = cat_df["total_bytes"].sum()
        cat_df["pct_share"] = ((cat_df["total_bytes"] / total) * 100.0).round(2) if total > 0 else 0.0
        return cat_df.sort_values(by="total_bytes", ascending=False)

    def get_app_timeline(self, start_ts: str, end_ts: str, app_id: Optional[int] = None) -> pd.DataFrame:
        """Fetch hourly usage timeline for a specific application or all apps."""
        return self.repo.get_app_timeline(start_ts, end_ts, app_id=app_id)

    def get_extremes(self, start_ts: str, end_ts: str) -> Dict[str, Any]:
        """Return the highest and lowest consuming applications."""
        df = self.get_summary(start_ts, end_ts)
        if df.empty:
            return {"highest": None, "lowest": None}
        sorted_df = df.sort_values(by="total_bytes", ascending=False)
        highest = sorted_df.iloc[0].to_dict()
        lowest = sorted_df.iloc[-1].to_dict()
        return {"highest": highest, "lowest": lowest}
