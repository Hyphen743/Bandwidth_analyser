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
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, root_mean_squared_error
from statsmodels.tsa.holtwinters import ExponentialSmoothing

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
            ROUND(SUM(bytes_up + bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS mbps
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
        df["mbps"] = df["mbps"].interpolate(method="linear").fillna(0.0)
        df["hour_ts"] = df.index.strftime("%Y-%m-%d %H:%M:%S")
        return df.reset_index(drop=True)

    def evaluate_models(self, df: pd.DataFrame, test_hours: int = 168) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate Baseline (Seasonal Naive), Holt-Winters, and Gradient Boosting
        using a strict time-based train/test split.
        test_hours defaults to 168 (1 week).
        """
        if len(df) < test_hours + 48:
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
            "mape": round(float(mean_absolute_percentage_error(y_test, naive_preds) * 100.0), 2),
            "predictions": naive_preds.tolist()
        }

        # 2. Holt-Winters Exponential Smoothing
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
            logger.warning("Holt-Winters fitting failed: %s. Using moving average fallback.", e)
            hw_preds = pd.Series(y_train).rolling(24, min_periods=1).mean().iloc[-test_hours:].values

        results["Holt-Winters"] = {
            "mae": round(float(mean_absolute_error(y_test, hw_preds)), 2),
            "rmse": round(float(root_mean_squared_error(y_test, hw_preds)), 2),
            "mape": round(float(mean_absolute_percentage_error(y_test, hw_preds) * 100.0), 2),
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
            "mape": round(float(mean_absolute_percentage_error(y_test, gb_preds) * 100.0), 2),
            "predictions": gb_preds.tolist()
        }

        return results

    def forecast_next_24h(self, df: pd.DataFrame, model_type: str = "Gradient Boosting") -> pd.DataFrame:
        """
        Generate next 24 hours of forecasts with upper/lower confidence bounds
        and link capacity limit comparison.
        """
        if df.empty or len(df) < 48:
            return pd.DataFrame()

        last_dt = pd.to_datetime(df.iloc[-1]["hour_ts"])
        future_dts = [last_dt + timedelta(hours=i) for i in range(1, 25)]
        future_ts = [d.strftime("%Y-%m-%d %H:%M:%S") for d in future_dts]

        # Use Gradient Boosting
        ml_df = self._build_lag_features(df)
        feature_cols = [c for c in ml_df.columns if c not in ("hour_ts", "mbps")]
        clean_ml = ml_df.dropna()

        model = HistGradientBoostingRegressor(max_iter=120, random_state=42)
        model.fit(clean_ml[feature_cols], clean_ml["mbps"])

        # Auto-regressive iterative forecasting for 24 steps
        preds = []
        recent_series = list(df["mbps"].values[-48:])

        for dt in future_dts:
            lag_1 = recent_series[-1]
            lag_2 = recent_series[-2]
            lag_24 = recent_series[-24]
            rolling_mean_24 = float(np.mean(recent_series[-24:]))
            rolling_std_24 = float(np.std(recent_series[-24:]))
            h = dt.hour
            d = dt.weekday()
            is_w = 1 if d >= 5 else 0

            feat = pd.DataFrame([{
                "lag_1": lag_1,
                "lag_2": lag_2,
                "lag_24": lag_24,
                "rolling_mean_24": rolling_mean_24,
                "rolling_std_24": rolling_std_24,
                "hour_of_day": h,
                "day_of_week": d,
                "is_weekend": is_w
            }])

            p = float(max(0.1, model.predict(feat)[0]))
            preds.append(p)
            recent_series.append(p)

        preds_arr = np.array(preds)
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
