"""
Unit tests for Bandwidth Demand Predictor and Time-Series Modeling.
"""

import pytest
import pandas as pd
from db.repository import DatabaseRepository
from ml.predictor import BandwidthPredictor


@pytest.fixture
def repo():
    return DatabaseRepository()


@pytest.fixture
def predictor(repo):
    return BandwidthPredictor(repo)


@pytest.fixture
def date_window(repo):
    min_ts, max_ts = repo.get_date_range()
    return min_ts, max_ts


def test_prepare_series(predictor, date_window):
    series = predictor.prepare_series(date_window[0], date_window[1])
    assert not series.empty
    assert "hour_ts" in series.columns
    assert "mbps" in series.columns
    assert (series["mbps"] >= 0).all()


def test_evaluate_models(predictor, date_window):
    series = predictor.prepare_series(date_window[0], date_window[1])
    results = predictor.evaluate_models(series, test_hours=48)
    assert "Seasonal Naive" in results
    assert "Holt-Winters" in results
    assert "Gradient Boosting" in results

    for model, m in results.items():
        assert m["mae"] >= 0.0
        assert m["rmse"] >= 0.0
        assert len(m["predictions"]) == 48


def test_forecast_next_24h(predictor, date_window):
    series = predictor.prepare_series(date_window[0], date_window[1])
    fc = predictor.forecast_next_24h(series)
    assert len(fc) == 24
    assert "predicted_mbps" in fc.columns
    assert "lower_bound" in fc.columns
    assert "upper_bound" in fc.columns
    assert (fc["upper_bound"] >= fc["lower_bound"]).all()
    assert (fc["predicted_mbps"] >= 0).all()
