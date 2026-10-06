"""
Unit tests for Anomaly Detection Engine (Z-Score, IQR, Isolation Forest).
"""

import pytest
import pandas as pd
from db.repository import DatabaseRepository
from ml.anomaly import AnomalyEngine


@pytest.fixture
def repo():
    return DatabaseRepository()


@pytest.fixture
def engine(repo):
    return AnomalyEngine(repo)


@pytest.fixture
def date_window(repo):
    min_ts, max_ts = repo.get_date_range()
    return min_ts, max_ts


def test_prepare_dataset(engine, date_window):
    df = engine.prepare_hourly_dataset(date_window[0], date_window[1])
    assert not df.empty
    assert "mbps" in df.columns
    assert "hour_of_day" in df.columns
    assert "is_weekend" in df.columns


def test_zscore_detection(engine, date_window):
    df = engine.prepare_hourly_dataset(date_window[0], date_window[1])
    res = engine.detect_zscore(df, threshold=2.5)
    assert not res.empty
    assert "is_anomaly" in res.columns
    assert "z_score" in res.columns
    assert "severity" in res.columns
    assert set(res["severity"].unique()).issubset({"normal", "info", "warn", "critical"})


def test_iqr_detection(engine, date_window):
    df = engine.prepare_hourly_dataset(date_window[0], date_window[1])
    res = engine.detect_iqr(df, factor=1.5)
    assert not res.empty
    assert "upper_bound" in res.columns
    assert "is_anomaly" in res.columns


def test_isolation_forest_detection(engine, date_window):
    df = engine.prepare_hourly_dataset(date_window[0], date_window[1])
    res = engine.detect_isolation_forest(df, contamination=0.03)
    assert not res.empty
    assert "is_anomaly" in res.columns
    assert "anomaly_score" in res.columns


def test_evaluation_against_ground_truth(engine, date_window):
    eval_results = engine.evaluate_against_ground_truth(date_window[0], date_window[1])
    for method in ["Z-Score", "IQR", "Isolation Forest"]:
        assert method in eval_results
        metrics = eval_results[method]
        assert 0.0 <= metrics["precision"] <= 1.0
        assert 0.0 <= metrics["recall"] <= 1.0
        assert 0.0 <= metrics["f1"] <= 1.0
