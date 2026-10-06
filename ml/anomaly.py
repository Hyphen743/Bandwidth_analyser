"""
Multi-Method Anomaly Detection Engine.
Implements:
1. Seasonal Rolling Z-Score
2. Interquartile Range (IQR) Fence Detection
3. Scikit-learn Isolation Forest
Evaluates detections against injected ground-truth labels (Precision, Recall, F1).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from db.repository import DatabaseRepository

logger = logging.getLogger("anomaly_engine")


class AnomalyEngine:
    """Detects bandwidth anomalies using statistical and machine learning approaches."""

    def __init__(self, repo: DatabaseRepository) -> None:
        self.repo = repo

    def prepare_hourly_dataset(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """
        Fetch hourly dataset with temporal features for anomaly detection.
        """
        sql = """
        SELECT 
            strftime('%Y-%m-%d %H:00:00', ts) AS hour_ts,
            CAST(strftime('%H', ts) AS INTEGER) AS hour_of_day,
            CAST(strftime('%w', ts) AS INTEGER) AS day_of_week,
            CASE WHEN CAST(strftime('%w', ts) AS INTEGER) IN (0, 6) THEN 1 ELSE 0 END AS is_weekend,
            SUM(bytes_up) AS bytes_up,
            SUM(bytes_down) AS bytes_down,
            SUM(bytes_up + bytes_down) AS total_bytes,
            ROUND(SUM(bytes_up + bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS mbps
        FROM bandwidth_usage
        WHERE ts BETWEEN :start_ts AND :end_ts
        GROUP BY hour_ts
        ORDER BY hour_ts ASC;
        """
        df = self.repo.query_df(sql, {"start_ts": start_ts, "end_ts": end_ts})
        return df

    def detect_zscore(self, df: pd.DataFrame, threshold: float = 2.5) -> pd.DataFrame:
        """
        Method 1: Z-Score compared to same hour-of-day and weekday/weekend baseline.
        """
        if df.empty:
            return pd.DataFrame()

        data = df.copy()
        # Group by hour_of_day and is_weekend to compute seasonal baseline
        grouped = data.groupby(["hour_of_day", "is_weekend"])["mbps"]
        means = grouped.transform("mean")
        stds = grouped.transform("std").replace(0, 1.0).fillna(1.0)

        data["baseline_mean"] = means.round(2)
        data["baseline_std"] = stds.round(2)
        data["z_score"] = ((data["mbps"] - data["baseline_mean"]) / data["baseline_std"]).round(2)
        data["is_anomaly"] = (data["z_score"] >= threshold).astype(int)

        def assign_severity(z: float) -> str:
            if z >= 4.5:
                return "critical"
            elif z >= 3.0:
                return "warn"
            elif z >= threshold:
                return "info"
            return "normal"

        data["severity"] = data["z_score"].apply(assign_severity)
        data["method"] = "Z-Score"
        return data

    def detect_iqr(self, df: pd.DataFrame, factor: float = 1.5) -> pd.DataFrame:
        """
        Method 2: Interquartile Range (IQR) Outlier Detection per seasonal bucket.
        """
        if df.empty:
            return pd.DataFrame()

        data = df.copy()

        def calc_bounds(sub_df: pd.DataFrame) -> Tuple[float, float, float]:
            q25 = sub_df["mbps"].quantile(0.25)
            q75 = sub_df["mbps"].quantile(0.75)
            iqr = q75 - q25
            upper_bound = q75 + (factor * iqr)
            return q25, q75, max(0.1, upper_bound)

        bounds = {}
        for (h, w), group in data.groupby(["hour_of_day", "is_weekend"]):
            bounds[(h, w)] = calc_bounds(group)

        upper_limits = [bounds[(row["hour_of_day"], row["is_weekend"])][2] for _, row in data.iterrows()]
        medians = [data.loc[(data["hour_of_day"] == row["hour_of_day"]) & (data["is_weekend"] == row["is_weekend"]), "mbps"].median() for _, row in data.iterrows()]

        data["upper_bound"] = np.round(upper_limits, 2)
        data["baseline_median"] = np.round(medians, 2)
        data["is_anomaly"] = (data["mbps"] > data["upper_bound"]).astype(int)

        def assign_severity(row: pd.Series) -> str:
            if not row["is_anomaly"]:
                return "normal"
            ratio = row["mbps"] / max(0.1, row["upper_bound"])
            if ratio >= 2.0:
                return "critical"
            elif ratio >= 1.3:
                return "warn"
            return "info"

        data["severity"] = data.apply(assign_severity, axis=1)
        data["method"] = "IQR"
        return data

    def detect_isolation_forest(self, df: pd.DataFrame, contamination: float = 0.03) -> pd.DataFrame:
        """
        Method 3: Scikit-learn Isolation Forest on multi-dimensional telemetry features.
        """
        if df.empty or len(df) < 20:
            return pd.DataFrame()

        data = df.copy()
        feature_cols = ["mbps", "bytes_up", "bytes_down", "hour_of_day", "day_of_week"]
        X = data[feature_cols].fillna(0)

        model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        preds = model.fit_predict(X)
        scores = model.decision_function(X)

        data["anomaly_score"] = np.round(-scores, 3)
        data["is_anomaly"] = (preds == -1).astype(int)

        # Baseline mean for display
        data["baseline_mean"] = data.groupby(["hour_of_day", "is_weekend"])["mbps"].transform("mean").round(2)

        def assign_severity(row: pd.Series) -> str:
            if not row["is_anomaly"]:
                return "normal"
            score = row["anomaly_score"]
            if score >= 0.15:
                return "critical"
            elif score >= 0.05:
                return "warn"
            return "info"

        data["severity"] = data.apply(assign_severity, axis=1)
        data["method"] = "Isolation Forest"
        return data

    def evaluate_against_ground_truth(self, start_ts: str, end_ts: str) -> Dict[str, Dict[str, float]]:
        """
        Compare the three anomaly detection methods against injected ground-truth labels.
        Returns Precision, Recall, and F1-Score for each method.
        """
        hourly_df = self.prepare_hourly_dataset(start_ts, end_ts)
        labels_df = self.repo.get_anomaly_labels(start_ts, end_ts)

        if hourly_df.empty or labels_df.empty:
            return {
                "Z-Score": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 0},
                "IQR": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 0},
                "Isolation Forest": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0, "fn": 0}
            }

        # Format ground truth timestamps to hour buckets
        gt_hours = set(labels_df["ts"].str.slice(0, 13) + ":00:00")

        results = {}
        methods = {
            "Z-Score": self.detect_zscore(hourly_df),
            "IQR": self.detect_iqr(hourly_df),
            "Isolation Forest": self.detect_isolation_forest(hourly_df)
        }

        for method_name, det_df in methods.items():
            if det_df.empty:
                continue

            detected_hours = set(det_df[det_df["is_anomaly"] == 1]["hour_ts"])

            tp = len(detected_hours.intersection(gt_hours))
            fp = len(detected_hours - gt_hours)
            fn = len(gt_hours - detected_hours)

            precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
            recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0
            f1 = round((2 * precision * recall) / (precision + recall), 3) if (precision + recall) > 0 else 0.0

            results[method_name] = {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "total_detected": len(detected_hours),
                "total_ground_truth": len(gt_hours)
            }

        return results

    def save_detected_alerts(self, df_anomalies: pd.DataFrame) -> int:
        """Persist newly detected anomalies into the alerts table."""
        count = 0
        for _, row in df_anomalies[df_anomalies["is_anomaly"] == 1].iterrows():
            ts = row["hour_ts"]
            val = float(row["mbps"])
            base = float(row.get("baseline_mean", row.get("upper_bound", 10.0)))
            sev = str(row.get("severity", "warn"))
            method = str(row.get("method", "Detector"))
            reason = f"{method} flagged anomalous traffic spike ({val:.1f} Mbps vs {base:.1f} Mbps baseline)"
            try:
                self.repo.insert_alert(
                    ts=ts,
                    entity_type="network",
                    entity_id=None,
                    severity=sev,
                    reason=reason,
                    value=val,
                    baseline=base
                )
                count += 1
            except Exception:
                pass
        return count
