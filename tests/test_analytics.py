"""
Unit tests for all 5 Analytics Engines.
"""

import pytest
from analytics.app_analysis import ApplicationAnalytics
from analytics.device_analysis import DeviceAnalytics
from analytics.time_analysis import TimeAnalytics
from analytics.updown import UpDownAnalytics
from analytics.ranking import RankingAnalytics
from db.repository import DatabaseRepository


@pytest.fixture
def repo():
    return DatabaseRepository()


@pytest.fixture
def date_window(repo):
    min_ts, max_ts = repo.get_date_range()
    return min_ts, max_ts


def test_application_analytics(repo, date_window):
    engine = ApplicationAnalytics(repo)
    summary = engine.get_summary(date_window[0], date_window[1])
    assert not summary.empty
    assert "total_gb" in summary.columns
    assert "pct_contribution" in summary.columns
    assert round(summary["pct_contribution"].sum(), 0) in (99.0, 100.0, 101.0)

    cats = engine.get_category_breakdown(date_window[0], date_window[1])
    assert not cats.empty
    assert "pct_share" in cats.columns


def test_device_analytics(repo, date_window):
    engine = DeviceAnalytics(repo)
    dev_summary = engine.get_device_summary(date_window[0], date_window[1])
    assert not dev_summary.empty
    assert "hostname" in dev_summary.columns
    assert "total_gb" in dev_summary.columns

    user_summary = engine.get_user_summary(date_window[0], date_window[1])
    assert not user_summary.empty
    assert "user_name" in user_summary.columns


def test_time_analytics(repo, date_window):
    engine = TimeAnalytics(repo)
    hourly = engine.get_hourly_series(date_window[0], date_window[1])
    assert not hourly.empty
    assert "mbps" in hourly.columns

    peak_offpeak = engine.get_peak_offpeak(date_window[0], date_window[1])
    assert not peak_offpeak.empty

    matrix = engine.get_hour_weekday_matrix(date_window[0], date_window[1])
    assert matrix.shape == (7, 24)


def test_updown_analytics(repo, date_window):
    engine = UpDownAnalytics(repo)
    summary = engine.get_summary(date_window[0], date_window[1])
    assert "gb_up" in summary
    assert "gb_down" in summary
    assert "ratio" in summary
    assert summary["ratio"] > 0

    cat_asym = engine.get_category_asymmetry(date_window[0], date_window[1])
    assert not cat_asym.empty
    assert "traffic_character" in cat_asym.columns


def test_ranking_analytics(repo, date_window):
    engine = RankingAnalytics(repo)
    app_ranks = engine.get_app_rankings(date_window[0], date_window[1], limit=5)
    assert not app_ranks.empty
    assert len(app_ranks) <= 5
    assert "current_rank" in app_ranks.columns
    assert "rank_change" in app_ranks.columns

    dev_ranks = engine.get_device_rankings(date_window[0], date_window[1], limit=5)
    assert not dev_ranks.empty
    assert len(dev_ranks) <= 5


def test_format_helpers():
    from ui.common import format_bytes, format_mbps
    assert format_bytes(0) == "0 B"
    assert format_bytes(500) == "500 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1024 * 1024) == "1.00 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
    assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"
    assert format_bytes(1.5 * 1024 * 1024 * 1024 * 1024) == "1.50 TB"

    assert format_mbps(0) == "0.0 Mbps"
    assert format_mbps(0.5) == "500.00 Kbps"
    assert format_mbps(25.4) == "25.40 Mbps"
    assert format_mbps(1200.0) == "1.20 Gbps"

