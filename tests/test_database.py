"""
Unit tests for Database Schema, Repository and Retention Job.
"""

import pytest
from db.repository import DatabaseRepository


@pytest.fixture
def repo():
    return DatabaseRepository()


def test_db_tables_exist(repo):
    stats = repo.get_db_stats()
    assert "users" in stats["counts"]
    assert "devices" in stats["counts"]
    assert "applications" in stats["counts"]
    assert "bandwidth_usage" in stats["counts"]
    assert "network_metrics" in stats["counts"]
    assert "alerts" in stats["counts"]
    assert stats["counts"]["applications"] >= 12
    assert stats["counts"]["devices"] >= 8


def test_settings_get_set(repo):
    repo.set_setting("test_key_xyz", "value_123")
    val = repo.get_setting("test_key_xyz")
    assert val == "value_123"

    repo.set_setting("test_key_xyz", "updated_456")
    val_updated = repo.get_setting("test_key_xyz")
    assert val_updated == "updated_456"


def test_date_range_not_empty(repo):
    min_ts, max_ts = repo.get_date_range()
    assert min_ts is not None
    assert max_ts is not None
    assert min_ts < max_ts


def test_retention_job_dry_run(repo):
    # Running retention with 120 days threshold should retain 90-day simulation
    result = repo.run_retention_job(days_threshold=120)
    assert "archived_samples" in result
    assert "deleted_raw" in result
    assert result["deleted_raw"] == 0
