"""
Upload vs Download Traffic Analytics.
Calculates upstream/downstream ratios, identifies asymmetric applications,
and tracks bidirectional trends over time.
"""

from __future__ import annotations

from typing import Any, Dict
import pandas as pd
from db.repository import DatabaseRepository


class UpDownAnalytics:
    """Analytical engine for bidirectional bandwidth asymmetry."""

    def __init__(self, repo: DatabaseRepository) -> None:
        self.repo = repo

    def get_summary(self, start_ts: str, end_ts: str) -> Dict[str, Any]:
        """Fetch total upload/download volumes and overall ratio."""
        df = self.repo.get_updown_summary(start_ts, end_ts)
        if df.empty or pd.isna(df.iloc[0]["total_bytes"]):
            return {
                "gb_up": 0.0,
                "gb_down": 0.0,
                "total_gb": 0.0,
                "ratio": 1.0,
                "pct_up": 50.0,
                "pct_down": 50.0
            }

        row = df.iloc[0]
        b_up = row["total_bytes_up"] or 0
        b_down = row["total_bytes_down"] or 0
        total = b_up + b_down

        gb_up = round(b_up / (1024.0 ** 3), 3)
        gb_down = round(b_down / (1024.0 ** 3), 3)
        ratio = round(b_up / max(1, b_down), 4)
        pct_up = round((b_up / max(1, total)) * 100.0, 1)
        pct_down = round((b_down / max(1, total)) * 100.0, 1)

        return {
            "bytes_up": b_up,
            "bytes_down": b_down,
            "total_bytes": total,
            "gb_up": gb_up,
            "gb_down": gb_down,
            "total_gb": round(total / (1024.0 ** 3), 3),
            "ratio": ratio,
            "pct_up": pct_up,
            "pct_down": pct_down
        }

    def get_category_asymmetry(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Categorize upload/download asymmetry across app types."""
        df = self.repo.get_updown_by_category(start_ts, end_ts)
        if df.empty:
            return df

        df["gb_up"] = (df["bytes_up"] / (1024.0 ** 3)).round(3)
        df["gb_down"] = (df["bytes_down"] / (1024.0 ** 3)).round(3)
        df["total_gb"] = (df["total_bytes"] / (1024.0 ** 3)).round(3)

        def characterize(ratio: float) -> str:
            if ratio >= 1.5:
                return "Upload Heavy"
            elif ratio <= 0.4:
                return "Download Heavy"
            return "Balanced"

        df["traffic_character"] = df["ratio"].apply(characterize)
        return df

    def get_timeline_bidirectional(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Hourly upload and download series for area chart visualization."""
        sql = """
        SELECT 
            strftime('%Y-%m-%d %H:00:00', ts) AS hour_ts,
            ROUND(SUM(bytes_up) * 8.0 / (3600.0 * 1000.0 * 1000.0), 3) AS mbps_up,
            ROUND(SUM(bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 3) AS mbps_down,
            ROUND(SUM(bytes_up + bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 3) AS mbps_total
        FROM bandwidth_usage
        WHERE ts BETWEEN :start_ts AND :end_ts
        GROUP BY hour_ts
        ORDER BY hour_ts ASC;
        """
        return self.repo.query_df(sql, {"start_ts": start_ts, "end_ts": end_ts})
