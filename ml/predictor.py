"""
Bandwidth Demand Forecasting and Capacity Prediction Engine.
Implements:
1. Baseline: Moving Average & Seasonal Naive
2. Holt-Winters Exponential Smoothing (statsmodels)
3. Machine Learning: Gradient Boosting / Random Forest Regressor with lag features
Evaluates with time-based train/test split (MAE, RMSE, MAPE).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    r2_score,
    root_mean_squared_error,
)

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    HAS_STATSMODELS = True
except (ImportError, Exception):
    ExponentialSmoothing = None
    HAS_STATSMODELS = False

from db.repository import DatabaseRepository

logger = logging.getLogger("predictor")


class BandwidthPredictor:
    """Predicts future bandwidth utilization and warns of potential capacity saturation."""

    def __init__(self, repo: DatabaseRepository) -> None:
        self.repo = repo

    def prepare_series(self, start_ts: str, end_ts: str) -> pd.DataFrame:
        """Fetch and format clean continuous hourly time-series."""
        sql = """
        SELECT 
            strftime('%Y-%m-%d %H:00:00', ts) AS hour_ts,
            ROUND(SUM(bytes_up + bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS mbps,
            COUNT(*) AS sample_count
        FROM bandwidth_usage
        WHERE ts BETWEEN :start_ts AND :end_ts
        GROUP BY hour_ts
        ORDER BY hour_ts ASC;
        """
        df = self.repo.query_df(sql, {"start_ts": start_ts, "end_ts": end_ts})
        if df.empty:
            return df

        df["dt"] = pd.to_datetime(df["hour_ts"])
        df = df.set_index("dt").asfreq("h")
        # A missing hour means the collector was not running. Preserve the gap
        # instead of inventing interpolated traffic for charts and forecasts.
        df["mbps"] = df["mbps"].where(df["sample_count"].fillna(0) > 0)
        df["hour_ts"] = df.index.strftime("%Y-%m-%d %H:%M:%S")
        return df.drop(columns=["sample_count"]).reset_index(drop=True)

    def evaluate_models(self, df: pd.DataFrame, test_hours: int = 168) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate Baseline (Seasonal Naive), Holt-Winters, and Gradient Boosting
        using a strict time-based train/test split.
        test_hours defaults to 168 (1 week).
        """
        if len(df) < test_hours + 48 or df["mbps"].isna().any():
            return {}

        train_df = df.iloc[:-test_hours].copy()
        test_df = df.iloc[-test_hours:].copy()

        y_train = train_df["mbps"].values
        y_test = test_df["mbps"].values

        results = {}

        # 1. Baseline: Seasonal Naive (value 24h prior)
        naive_preds = []
        for i in range(len(test_df)):
            idx = len(train_df) + i - 24
            if idx >= 0:
                naive_preds.append(df.iloc[idx]["mbps"])
            else:
                naive_preds.append(train_df["mbps"].mean())
        naive_preds = np.array(naive_preds)

        results["Seasonal Naive"] = {
            "mae": round(float(mean_absolute_error(y_test, naive_preds)), 2),
            "rmse": round(float(root_mean_squared_error(y_test, naive_preds)), 2),
            "mape": self._safe_mape(y_test, naive_preds),
            "r2": round(float(r2_score(y_test, naive_preds)), 4),
            "predictions": naive_preds.tolist()
        }

        # 2. Holt-Winters Exponential Smoothing
        hw_preds = None
        if HAS_STATSMODELS and ExponentialSmoothing is not None:
            try:
                hw_model = ExponentialSmoothing(
                    y_train,
                    seasonal_periods=24,
                    trend="add",
                    seasonal="add",
                    initialization_method="estimated"
                ).fit()
                hw_preds = np.maximum(0, hw_model.forecast(test_hours))
            except Exception as e:
                logger.debug("Statsmodels Holt-Winters failed: %s. Using native fallback.", e)
                hw_preds = None

        if hw_preds is None:
            hw_preds = self._native_holt_winters(y_train, forecast_len=test_hours, season_len=24)

        results["Holt-Winters"] = {
            "mae": round(float(mean_absolute_error(y_test, hw_preds)), 2),
            "rmse": round(float(root_mean_squared_error(y_test, hw_preds)), 2),
            "mape": self._safe_mape(y_test, hw_preds),
            "r2": round(float(r2_score(y_test, hw_preds)), 4),
            "predictions": hw_preds.tolist()
        }

        # 3. Machine Learning: Gradient Boosting with Lags
        ml_df = self._build_lag_features(df)
        ml_train = ml_df.iloc[:-test_hours].dropna()
        ml_test = ml_df.iloc[-test_hours:].copy()

        feature_cols = [c for c in ml_df.columns if c not in ("hour_ts", "mbps")]
        X_train = ml_train[feature_cols]
        y_train_ml = ml_train["mbps"]
        X_test = ml_test[feature_cols]

        gb_model = HistGradientBoostingRegressor(max_iter=100, random_state=42)
        gb_model.fit(X_train, y_train_ml)
        gb_preds = np.maximum(0, gb_model.predict(X_test))

        results["Gradient Boosting"] = {
            "mae": round(float(mean_absolute_error(y_test, gb_preds)), 2),
            "rmse": round(float(root_mean_squared_error(y_test, gb_preds)), 2),
            "mape": self._safe_mape(y_test, gb_preds),
            "r2": round(float(r2_score(y_test, gb_preds)), 4),
            "predictions": gb_preds.tolist()
        }

        return results

    @staticmethod
    def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
        """MAPE over nonzero actuals; the metric is undefined when actual is zero."""
        nonzero = np.asarray(y_true) != 0
        if not np.any(nonzero):
            return None
        return round(
            float(mean_absolute_percentage_error(np.asarray(y_true)[nonzero], np.asarray(y_pred)[nonzero]) * 100.0),
            2,
        )

    @staticmethod
    def _native_holt_winters(
        series: np.ndarray,
        forecast_len: int,
        season_len: int = 24,
        alpha: float = 0.3,
        beta: float = 0.05,
        gamma: float = 0.3
    ) -> np.ndarray:
        """Native pure-NumPy additive Holt-Winters exponential smoothing."""
        n = len(series)
        if n < season_len * 2:
            return np.full(forecast_len, max(0.1, float(np.mean(series))))

        level = float(np.mean(series[:season_len]))
        trend = float((np.mean(series[season_len:2*season_len]) - np.mean(series[:season_len])) / season_len)
        seasonals = [float(series[i] - level) for i in range(season_len)]

        for i in range(season_len, n):
            val = float(series[i])
            last_level = level
            last_season = seasonals[i % season_len]

            level = alpha * (val - last_season) + (1.0 - alpha) * (last_level + trend)
            trend = beta * (level - last_level) + (1.0 - beta) * trend
            seasonals[i % season_len] = gamma * (val - level) + (1.0 - gamma) * last_season

        forecast = []
        for m in range(1, forecast_len + 1):
            s_idx = (n + m - 1) % season_len
            pred = level + m * trend + seasonals[s_idx]
            forecast.append(max(0.1, float(pred)))

        return np.array(forecast)

    def forecast_next_24h(self, df: pd.DataFrame, model_type: str = "Gradient Boosting") -> pd.DataFrame:
        """
        Generate next 24 hours of forecasts with upper/lower confidence bounds
        and link capacity limit comparison.
        """
        if df.empty:
            return pd.DataFrame()

        observed_mask = df["mbps"].notna().to_numpy()
        valid_positions = np.flatnonzero(observed_mask)
        if not len(valid_positions):
            return pd.DataFrame()
        end_position = int(valid_positions[-1])
        start_position = end_position
        while start_position > 0 and observed_mask[start_position - 1]:
            start_position -= 1
        # Forecast from the most recent continuous run only. Earlier gaps are
        # retained in the chart and never filled with fabricated observations.
        df = df.iloc[start_position:end_position + 1].reset_index(drop=True)
        if len(df) < 49:
            return pd.DataFrame()

        last_dt = pd.to_datetime(df.iloc[-1]["hour_ts"])
        future_dts = [last_dt + timedelta(hours=i) for i in range(1, 25)]
        future_ts = [d.strftime("%Y-%m-%d %H:%M:%S") for d in future_dts]

        values = df["mbps"].to_numpy(dtype=float)
        timestamps = pd.to_datetime(df["hour_ts"]).reset_index(drop=True)
        training_examples = len(values)
        if model_type == "Seasonal Naive":
            # Repeat the most recently observed daily profile.
            preds_arr = np.maximum(0.0, values[-24:].copy())
        elif model_type == "Holt-Winters":
            if HAS_STATSMODELS and ExponentialSmoothing is not None:
                try:
                    fitted = ExponentialSmoothing(
                        values,
                        seasonal_periods=24,
                        trend="add",
                        seasonal="add",
                        initialization_method="estimated",
                    ).fit()
                    preds_arr = np.maximum(0.0, fitted.forecast(24))
                except Exception as exc:
                    logger.debug("Holt-Winters forecast failed; using native fallback: %s", exc)
                    preds_arr = self._native_holt_winters(values, forecast_len=24, season_len=24)
            else:
                preds_arr = self._native_holt_winters(values, forecast_len=24, season_len=24)
        else:
            # Refit from the latest observed continuous history on every
            # forecast refresh. New collector samples therefore become new
            # training examples; this is batch retraining, not online learning.
            feature_columns = [
                "lag_1", "lag_2", "lag_24", "rolling_mean_24", "rolling_std_24",
                "hour_of_day", "day_of_week", "is_weekend", "horizon",
            ]
            train_features: list[dict[str, float]] = []
            train_targets: list[float] = []
            for origin in range(24, len(values) - 24):
                observed = values[origin - 23:origin + 1]
                for horizon in range(1, 25):
                    target_index = origin + horizon
                    target_time = timestamps.iloc[target_index]
                    train_features.append({
                        "lag_1": float(observed[-1]),
                        "lag_2": float(observed[-2]),
                        "lag_24": float(values[origin - 24]),
                        "rolling_mean_24": float(np.mean(observed)),
                        "rolling_std_24": float(np.std(observed)),
                        "hour_of_day": float(target_time.hour),
                        "day_of_week": float(target_time.dayofweek),
                        "is_weekend": float(target_time.dayofweek >= 5),
                        "horizon": float(horizon),
                    })
                    train_targets.append(float(values[target_index]))

            model = HistGradientBoostingRegressor(max_iter=120, random_state=42)
            model.fit(pd.DataFrame(train_features, columns=feature_columns), train_targets)
            training_examples = len(train_targets)

            observed = values[-24:]
            future_features = pd.DataFrame([
                {
                    "lag_1": float(observed[-1]),
                    "lag_2": float(observed[-2]),
                    "lag_24": float(values[-25]),
                    "rolling_mean_24": float(np.mean(observed)),
                    "rolling_std_24": float(np.std(observed)),
                    "hour_of_day": float(dt.hour),
                    "day_of_week": float(dt.weekday()),
                    "is_weekend": float(dt.weekday() >= 5),
                    "horizon": float(horizon),
                }
                for horizon, dt in enumerate(future_dts, start=1)
            ], columns=feature_columns)
            preds_arr = np.maximum(0.0, model.predict(future_features))
        capacity_mbps = float(self.repo.get_setting("capacity_mbps", "100.0"))

        # Std error proxy based on recent historical volatility
        sigma = float(df["mbps"].tail(72).std() or 4.0)

        forecast_df = pd.DataFrame({
            "target_ts": future_ts,
            "predicted_mbps": np.round(preds_arr, 2),
            "lower_bound": np.round(np.maximum(0, preds_arr - 1.96 * sigma), 2),
            "upper_bound": np.round(preds_arr + 1.96 * sigma, 2),
            "capacity_mbps": capacity_mbps,
            "is_capacity_exceeded": (preds_arr >= capacity_mbps * 0.85).astype(int),
            "model": model_type
        })
        forecast_df.attrs["training_examples"] = training_examples
        forecast_df.attrs["trained_through"] = str(df.iloc[-1]["hour_ts"])

        # Log predictions to database
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for _, row in forecast_df.iterrows():
            try:
                self.repo.insert_prediction(
                    ts_generated=now_str,
                    target_ts=row["target_ts"],
                    predicted_mbps=float(row["predicted_mbps"]),
                    actual_mbps=None,
                    model=model_type
                )
            except Exception:
                pass

        return forecast_df

    def _build_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Construct temporal and autoregressive features."""
        data = df.copy()
        data["dt"] = pd.to_datetime(data["hour_ts"])
        data["hour_of_day"] = data["dt"].dt.hour
        data["day_of_week"] = data["dt"].dt.dayofweek
        data["is_weekend"] = (data["day_of_week"] >= 5).astype(int)

        data["lag_1"] = data["mbps"].shift(1)
        data["lag_2"] = data["mbps"].shift(2)
        data["lag_24"] = data["mbps"].shift(24)
        data["rolling_mean_24"] = data["mbps"].shift(1).rolling(24).mean()
        data["rolling_std_24"] = data["mbps"].shift(1).rolling(24).std().fillna(0)

        data = data.drop(columns=["dt"])
        return data
