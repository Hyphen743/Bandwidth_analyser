"""
Page 8: Bandwidth Demand Forecasting and Capacity Headroom.
Time-series forecasting with Seasonal Naive, Holt-Winters, and Gradient Boosting.
Predicts next 24-hour peak demand, evaluates MAE/RMSE/MAPE without data leakage,
and compares forecasted throughput against provisioned link capacity.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import streamlit as st
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from ml.predictor import BandwidthPredictor
from ui.charts import build_forecast_chart
from ui.common import download_csv_button, render_kpi, setup_page

st.set_page_config(page_title="Demand Forecast", page_icon="📈", layout="wide")


def _fit_linear_trend(series: pd.DataFrame) -> dict:
    """Fit the coursework regression equation directly from the selected series."""
    observed = series.loc[:, ["hour_ts", "mbps"]].dropna(subset=["mbps"])
    if len(observed) < 2:
        return {}

    timestamps = pd.to_datetime(observed["hour_ts"])
    x_hours = (timestamps - timestamps.iloc[0]).dt.total_seconds().to_numpy() / 3600.0
    y_mbps = observed["mbps"].to_numpy(dtype=float)
    if not np.isfinite(x_hours).all() or not np.isfinite(y_mbps).all():
        return {}

    model = LinearRegression().fit(x_hours.reshape(-1, 1), y_mbps)
    fitted = model.predict(x_hours.reshape(-1, 1))
    return {
        "slope_mbps_per_hour": float(model.coef_[0]),
        "intercept_mbps": float(model.intercept_),
        "r2": float(r2_score(y_mbps, fitted)),
        "samples": int(len(y_mbps)),
        "start_ts": timestamps.iloc[0],
        "end_ts": timestamps.iloc[-1],
    }


def main() -> None:
    repo, filters = setup_page(
        title="Bandwidth Demand Forecasting",
        subtitle="Multi-step predictive modeling, confidence intervals, and capacity headroom planning."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    predictor = BandwidthPredictor(repo)
    series_df = predictor.prepare_series(
        start_ts,
        end_ts,
        simulated=filters["data_source"] == "simulated",
    )

    if series_df.empty or len(series_df) < 49:
        st.warning("Insufficient historical data for forecasting. At least 49 hourly observations are needed; broaden your date range.")
        return

    # Capacity setting
    capacity_mbps = float(repo.get_setting("capacity_mbps", "100.0"))

    selected_model = st.selectbox(
        "Forecast model",
        [
            "Gradient Boosting (retrained on refresh)",
            "Holt-Winters",
            "Seasonal Naive",
        ],
        help=(
            "Gradient Boosting is batch-retrained from the latest observed history whenever this page refreshes. "
            "It learns from newly collected samples but does not retain model weights between runs."
        ),
    )
    forecast_df = predictor.forecast_next_24h(series_df, model_type=selected_model)
    if forecast_df.empty:
        st.warning(
            "Forecast unavailable: this view needs at least 49 consecutive hourly observations. "
            "Simulated quiet hours count as zero traffic; gaps in live collection remain unfilled."
        )
        return

    st.caption(
        f"Model: {selected_model} · trained through {forecast_df.attrs.get('trained_through', 'unknown')} · "
        f"{forecast_df.attrs.get('training_examples', 0):,} training examples. "
        "Newly collected data is used the next time this forecast is recalculated."
    )

    # Evaluate models on test split
    eval_results = predictor.evaluate_models(series_df, test_hours=168)

    # Forecast KPIs
    k1, k2, k3, k4 = st.columns(4)
    next_hour_pred = forecast_df.iloc[0]["predicted_mbps"]
    max_24h_pred = forecast_df["predicted_mbps"].max()
    headroom_mbps = max(0.0, capacity_mbps - max_24h_pred)
    sat_risk = "High Risk" if max_24h_pred >= (capacity_mbps * 0.85) else "Normal"

    render_kpi(k1, "Next Hour Predicted", f"{next_hour_pred:.1f} Mbps", delta=f"{forecast_df.iloc[0]['target_ts'][11:16]} Forecast", delta_type="neutral")
    render_kpi(k2, "24h Peak Predicted", f"{max_24h_pred:.1f} Mbps", delta=f"Limit: {capacity_mbps:.0f} Mbps", delta_type="neg" if sat_risk == "High Risk" else "pos")
    render_kpi(k3, "Capacity Headroom", f"{headroom_mbps:.1f} Mbps", delta=f"{(headroom_mbps/capacity_mbps)*100:.0f}% buffer remaining", delta_type="pos" if headroom_mbps > 20 else "neg")
    render_kpi(k4, "Saturation Status", sat_risk, delta="Upcoming 24 Hours", delta_type="neg" if sat_risk == "High Risk" else "pos")

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Forecast Chart
    st.subheader("24-Hour Predictive Demand vs Link Capacity")
    fig_fc = build_forecast_chart(
        historical_df=series_df,
        forecast_df=forecast_df,
        capacity_mbps=capacity_mbps,
        title="24-Hour Forecast with Recent-Variation Band",
        height=400,
        dark_mode=dark_mode
    )
    st.plotly_chart(fig_fc, width="stretch")
    st.caption("The shaded band reflects recent traffic variation; it is not a calibrated 95% confidence interval.")

    # Model Evaluation Comparison Table
    st.subheader("Model Evaluation on Test Holdout (7-Day Split)")
    if eval_results:
        eval_rows = []
        for m_name, metrics in eval_results.items():
            eval_rows.append({
                "Model Architecture": m_name,
                "MAE (Mbps)": metrics["mae"],
                "RMSE (Mbps)": metrics["rmse"],
                "MAPE (%)": f"{metrics['mape']:.1f}%" if metrics["mape"] is not None else "N/A (actual is zero)",
                "R²": metrics["r2"],
                "Evaluation Mode": "Chronological 7-Day Holdout"
            })
        st.dataframe(pd.DataFrame(eval_rows), width="stretch", hide_index=True)
        st.caption("R² is calculated on the held-out hours. It may be negative when predictions perform worse than the test-period mean.")
    else:
        st.info("Evaluation metrics unavailable for current dataset size.")

    # Simple regression-equation goodness of fit, kept distinct from the
    # chronological forecast scores above.
    trend_fit = _fit_linear_trend(series_df)
    st.subheader("Linear Regression Equation (Selected History)")
    if trend_fit:
        slope = trend_fit["slope_mbps_per_hour"]
        intercept = trend_fit["intercept_mbps"]
        intercept_sign = "+" if intercept >= 0 else "−"
        st.code(
            f"Mbps = {slope:.6f} × elapsed_hours {intercept_sign} {abs(intercept):.4f}",
            language="text",
        )
        fit_col, slope_col, sample_col = st.columns(3)
        fit_col.metric("Regression Fit R²", f"{trend_fit['r2']:.4f}")
        slope_col.metric("Slope", f"{slope:.6f} Mbps/hour")
        sample_col.metric("Observed Samples", f"{trend_fit['samples']:,}")
        st.caption(
            f"In-sample linear fit from {trend_fit['start_ts']} through {trend_fit['end_ts']}. "
            "Here x is elapsed hours from the first observed sample and y is measured throughput in Mbps. "
            "This regression-equation R² is separate from the 7-day forecast holdout R² above."
        )
    else:
        st.info("A linear regression fit needs at least two valid observed samples.")

    # Forecast Tabular Data
    st.subheader("Next 24 Hours Forecast Schedule")
    display_fc = forecast_df[[
        "target_ts", "predicted_mbps", "lower_bound", "upper_bound", "is_capacity_exceeded"
    ]].rename(columns={
        "target_ts": "Target Hour",
        "predicted_mbps": "Predicted Demand (Mbps)",
        "lower_bound": "Variation Lower (Mbps)",
        "upper_bound": "Variation Upper (Mbps)",
        "is_capacity_exceeded": "Capacity Warning"
    })
    st.dataframe(display_fc, width="stretch", hide_index=True)
    download_csv_button(display_fc, filename="bandwidth_forecast_24h.csv", label="Export Forecast CSV")


if __name__ == "__main__":
    main()
