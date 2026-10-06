"""
Entity Ranking and Period-Over-Period Rank Shifts.
Calculates leaderboards for applications and devices, comparing current
period ranks against the preceding period to produce rank delta arrows.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple
import pandas as pd
from db.repository import DatabaseRepository


class RankingAnalytics:
    """Computes Top-N leaderboards and period-over-period rank shifts."""

    def __init__(self, repo: DatabaseRepository) -> None:
        self.repo = repo

    def get_app_rankings(
        self,
        start_ts: str,
        end_ts: str,
        limit: int = 10
    ) -> pd.DataFrame:
        """
        Produce Top-N apps for the given period with rank-change vs preceding equivalent period.
        """
        # Current period rankings
        curr_df = self.repo.get_top_apps(start_ts, end_ts, limit=100)
        if curr_df.empty:
            return pd.DataFrame()

        curr_df["current_rank"] = range(1, len(curr_df) + 1)

        # Calculate preceding time window of same duration
        dt_start = datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S")
        dt_end = datetime.strptime(end_ts, "%Y-%m-%d %H:%M:%S")
        duration = dt_end - dt_start
        prev_start = (dt_start - duration).strftime("%Y-%m-%d %H:%M:%S")
        prev_end = start_ts

        prev_df = self.repo.get_top_apps(prev_start, prev_end, limit=100)
        if not prev_df.empty:
            prev_df["prev_rank"] = range(1, len(prev_df) + 1)
            merged = pd.merge(
                curr_df.head(limit),
                prev_df[["app_id", "prev_rank"]],
                on="app_id",
                how="left"
            )
        else:
            merged = curr_df.head(limit).copy()
            merged["prev_rank"] = None

        # Format rank shifts
        merged["rank_change"] = merged.apply(self._format_rank_shift, axis=1)
        return merged

    def get_device_rankings(
        self,
        start_ts: str,
        end_ts: str,
        limit: int = 10
    ) -> pd.DataFrame:
        """
        Produce Top-N devices with period-over-period rank shift indicators.
        """
        curr_df = self.repo.get_top_devices(start_ts, end_ts, limit=100)
        if curr_df.empty:
            return pd.DataFrame()

        curr_df["current_rank"] = range(1, len(curr_df) + 1)

        dt_start = datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S")
        dt_end = datetime.strptime(end_ts, "%Y-%m-%d %H:%M:%S")
        duration = dt_end - dt_start
        prev_start = (dt_start - duration).strftime("%Y-%m-%d %H:%M:%S")
        prev_end = start_ts

        prev_df = self.repo.get_top_devices(prev_start, prev_end, limit=100)
        if not prev_df.empty:
            prev_df["prev_rank"] = range(1, len(prev_df) + 1)
            merged = pd.merge(
                curr_df.head(limit),
                prev_df[["device_id", "prev_rank"]],
                on="device_id",
                how="left"
            )
        else:
            merged = curr_df.head(limit).copy()
            merged["prev_rank"] = None

        merged["rank_change"] = merged.apply(self._format_rank_shift, axis=1)
        return merged

    @staticmethod
    def _format_rank_shift(row: pd.Series) -> str:
        """Render arrow and delta for rank change."""
        curr = row["current_rank"]
        prev = row.get("prev_rank")
        if pd.isna(prev) or prev is None:
            return "NEW"
        prev = int(prev)
        diff = prev - curr  # positive means improved rank (e.g. 5 -> 2 is +3)
        if diff > 0:
            return f"↑ +{diff}"
        elif diff < 0:
            return f"↓ {diff}"
        else:
            return "↔ 0"
