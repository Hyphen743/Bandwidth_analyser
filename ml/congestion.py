"""
Network Congestion Analysis and Predictive Classification Engine.
Detects saturation episodes, computes correlation matrix across metrics,
attributes bottleneck intervals to top offending applications/devices,
and predicts congestion risk from forecast demand.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from db.repository import DatabaseRepository

logger = logging.getLogger("congestion")


class CongestionAnalyzer:
    """Detects, attributes, and predicts network link congestion episodes."""

    def __init__(self, repo: DatabaseRepository) -> None:
        self.repo = repo

    def get_congestion_events(
        self,
        start_ts: str,
        end_ts: str,
        threshold_util: Optional[float] = None,
        threshold_latency: Optional[float] = None,
        threshold_loss: Optional[float] = None
    ) -> pd.DataFrame:
        """Fetch network metric series with congestion flag markers."""
        t_util = threshold_util or float(self.repo.get_setting("congestion_util_threshold", "80.0"))
        t_lat = threshold_latency or float(self.repo.get_setting("latency_alert_threshold", "60.0"))
        t_loss = threshold_loss or float(self.repo.get_setting("packet_loss_threshold", "3.0"))

        return self.repo.get_congestion_metrics(
            start_ts=start_ts,
            end_ts=end_ts,
            threshold_util=t_util,
            threshold_latency=t_lat,
            threshold_loss=t_loss
        )

    def get_correlation_matrix(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """
        Calculate Pearson correlation matrix between utilization %, latency ms,
        jitter ms, and packet loss %.
        """
        df = self.get_congestion_events(start_ts, end_ts)
        if df.empty or len(df) < 5:
            # Return identity structure
            cols = ["utilization_pct", "latency_ms", "jitter_ms", "packet_loss_pct"]
            return pd.DataFrame(np.eye(4), index=cols, columns=cols)

        metric_cols = ["utilization_pct", "latency_ms", "jitter_ms", "packet_loss_pct"]
        corr = df[metric_cols].corr(method="pearson").round(3)
        return corr

    def attribute_congestion_offenders(
        self,
        start_ts: str,
        end_ts: str,
        limit: int = 5
    ) -> pd.DataFrame:
        """
        Identify top applications and devices consuming traffic during
        the periods marked as congested.
        """
        # Find congested timestamps
        events = self.get_congestion_events(start_ts, end_ts)
        if events.empty:
            return pd.DataFrame()

        congested_ts = events[events["is_congested"] == 1]["ts"].tolist()
        if not congested_ts:
            return pd.DataFrame()

        # Query top consumers during these exact hours
        min_c_ts = min(congested_ts)
        max_c_ts = max(congested_ts)

        return self.repo.get_congested_interval_offenders(min_c_ts, max_c_ts, limit=limit)

    def predict_future_congestion(
        self,
        forecast_df: pd.DataFrame,
        util_threshold: float = 80.0
    ) -> pd.DataFrame:
        """
        Applies a calibrated sigmoid / logistic model to classify forecasted
        bandwidth utilization into Congestion Risk (Low, Medium, High).
        """
        if forecast_df.empty:
            return pd.DataFrame()

        out_df = forecast_df.copy()
        cap = float(out_df.iloc[0].get("capacity_mbps", 100.0))

        def calc_risk(pred_mbps: float) -> Tuple[float, str]:
            util = (pred_mbps / cap) * 100.0
            # Logistic function centered at threshold
            prob = 1.0 / (1.0 + np.exp(-0.15 * (util - util_threshold)))
            prob_pct = round(float(prob) * 100.0, 1)

            if prob_pct >= 70.0:
                risk = "High"
            elif prob_pct >= 40.0:
                risk = "Medium"
            else:
                risk = "Low"
            return prob_pct, risk

        risks = [calc_risk(p) for p in out_df["predicted_mbps"]]
        out_df["congestion_probability_pct"] = [r[0] for r in risks]
        out_df["risk_level"] = [r[1] for r in risks]

        return out_df
