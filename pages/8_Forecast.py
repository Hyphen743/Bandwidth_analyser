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
import streamlit as st

from ml.predictor import BandwidthPredictor
from ui.charts import build_forecast_chart
from ui.common import download_csv_button, render_kpi, setup_page

st.set_page_config(page_title="Demand Forecast", page_icon="📈", layout="wide")


def main() -> None:
    repo, filters = setup_page(
        title="Bandwidth Demand Forecasting",
        subtitle="Multi-step predictive modeling, confidence intervals, and capacity headroom planning."
    )
    dark_mode = filters["dark_mode"]
    start_ts = filters["start_ts"]
    end_ts = filters["end_ts"]

    predictor = BandwidthPredictor(repo)
    series_df = predictor.prepare_series(start_ts, end_ts)

    if series_df.empty or len(series_df) < 48:
        st.warning("Insufficient historical data for forecasting. Please broaden your date range.")
        return

    # Capacity setting
    capacity_mbps = float(repo.get_setting("capacity_mbps", "100.0"))

    # Generate 24h forecast
    forecast_df = predictor.forecast_next_24h(series_df, model_type="Gradient Boosting")

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
        title="24-Hour Forecast Curve with 95% Confidence Bounds",
        height=400,
        dark_mode=dark_mode
    )
    st.plotly_chart(fig_fc, width="stretch")

    # Model Evaluation Comparison Table
    st.subheader("Model Evaluation on Test Holdout (7-Day Split)")
    if eval_results:
        eval_rows = []
        for m_name, metrics in eval_results.items():
            eval_rows.append({
                "Model Architecture": m_name,
                "MAE (Mbps)": metrics["mae"],
                "RMSE (Mbps)": metrics["rmse"],
                "MAPE (%)": f"{metrics['mape']:.1f}%",
                "Evaluation Mode": "Time-based Walk-Forward (Zero Leakage)"
            })
        st.dataframe(pd.DataFrame(eval_rows), width="stretch", hide_index=True)
    else:
        st.info("Evaluation metrics unavailable for current dataset size.")

    # Forecast Tabular Data
    st.subheader("Next 24 Hours Forecast Schedule")
    display_fc = forecast_df[[
        "target_ts", "predicted_mbps", "lower_bound", "upper_bound", "is_capacity_exceeded"
    ]].rename(columns={
        "target_ts": "Target Hour",
        "predicted_mbps": "Predicted Demand (Mbps)",
        "lower_bound": "95% Lower (Mbps)",
        "upper_bound": "95% Upper (Mbps)",
        "is_capacity_exceeded": "Capacity Warning"
    })
    st.dataframe(display_fc, width="stretch", hide_index=True)
    download_csv_button(display_fc, filename="bandwidth_forecast_24h.csv", label="Export Forecast CSV")


if __name__ == "__main__":
    main()
