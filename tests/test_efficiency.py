"""
Unit tests for Efficiency Engine and Optimization Recommendations.
"""

import pytest
from db.repository import DatabaseRepository
from ml.efficiency import EfficiencyEngine


@pytest.fixture
def repo():
    return DatabaseRepository()


@pytest.fixture
def engine(repo):
    return EfficiencyEngine(repo)


@pytest.fixture
def date_window(repo):
    min_ts, max_ts = repo.get_date_range()
    return min_ts, max_ts


def test_calculate_efficiency_bounds(engine, date_window):
    res = engine.calculate_efficiency(date_window[0], date_window[1])
    assert "overall_score" in res
    assert "rating" in res
    assert "subscores" in res
    assert "par" in res

    score = res["overall_score"]
    assert 0.0 <= score <= 100.0
    assert res["rating"] in ("Efficient", "Moderate", "Inefficient")

    sub = res["subscores"]
    for k in ["useful_throughput", "smoothness_par", "offpeak_shifting", "traffic_balance", "network_quality"]:
        assert k in sub
        assert 0.0 <= sub[k] <= 100.0


def test_recommendations_structure(engine, date_window):
    res = engine.calculate_efficiency(date_window[0], date_window[1])
    recs = res["recommendations"]
    assert isinstance(recs, list)
    for r in recs:
        assert "priority" in r
        assert "title" in r
        assert "impact" in r
        assert "estimated_savings_gb" in r
        assert r["estimated_savings_gb"] >= 0.0


def test_compare_entities_efficiency(engine, date_window):
    df = engine.compare_entities_efficiency(date_window[0], date_window[1])
    assert not df.empty
    assert "efficiency_score" in df.columns
    assert "rating" in df.columns
    assert (df["efficiency_score"] >= 0).all()
    assert (df["efficiency_score"] <= 100).all()
