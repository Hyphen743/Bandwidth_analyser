"""Regression coverage for quiet simulated hours and forecast model choices."""

import pandas as pd

from ml.predictor import BandwidthPredictor


class _SeriesRepo:
    def __init__(self, rows):
        self.rows = rows

    def query_df(self, _sql, _params):
        return pd.DataFrame(self.rows, columns=["hour_ts", "mbps", "sample_count"])

    def get_date_range(self):
        return "2026-01-01 00:00:00", "2026-01-03 23:00:00"

    def get_setting(self, _key, default=None):
        return default or "100.0"

    def insert_prediction(self, **_kwargs):
        pass


def _repo_with_quiet_hours():
    hours = pd.date_range("2026-01-01 00:00:00", periods=72, freq="h")
    rows = [
        (hour.strftime("%Y-%m-%d %H:%M:%S"), float(20 + hour.hour % 8), 1)
        for index, hour in enumerate(hours)
        if index not in {5, 18, 41}
    ]
    return _SeriesRepo(rows)


def test_simulated_quiet_hours_are_zero_but_live_gaps_remain_missing():
    repo = _repo_with_quiet_hours()
    predictor = BandwidthPredictor(repo)

    simulated = predictor.prepare_series(*repo.get_date_range(), simulated=True)
    live = predictor.prepare_series(*repo.get_date_range(), simulated=False)

    assert len(simulated) == 72
    assert simulated["mbps"].isna().sum() == 0
    assert (simulated.loc[[5, 18, 41], "mbps"] == 0).all()
    assert live["mbps"].isna().sum() == 3


def test_all_forecast_models_return_24_hours_for_simulated_history():
    repo = _repo_with_quiet_hours()
    predictor = BandwidthPredictor(repo)
    series = predictor.prepare_series(*repo.get_date_range(), simulated=True)

    for model in ("Gradient Boosting (retrained on refresh)", "Holt-Winters", "Seasonal Naive"):
        forecast = predictor.forecast_next_24h(series, model_type=model)
        assert len(forecast) == 24
        assert (forecast["predicted_mbps"] >= 0).all()

