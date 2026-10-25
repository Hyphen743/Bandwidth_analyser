"""Unit checks for cross-desktop account-level ranking totals."""

from contextlib import contextmanager
from datetime import datetime, timezone

from shared_rankings import SharedRankingStore


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.query = ""
        self.collectors = {}
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, _params):
        self.query = query
        if query.lstrip().startswith("INSERT INTO ba_shared_collectors"):
            friend_code, token_hash, device_name = _params
            if token_hash not in self.collectors:
                self.collectors[token_hash] = (friend_code, device_name)
                self.rowcount = 1
            else:
                self.rowcount = 0
            return self
        if query.lstrip().startswith("SELECT friend_code FROM ba_shared_collectors"):
            token_hash = _params[0]
            found = self.collectors.get(token_hash)
            self.result = (found[0],) if found else None
            return self
        return self

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.result


def test_rankings_return_one_friend_row_with_cross_computer_totals(monkeypatch):
    received_at = datetime.now(timezone.utc)
    connection = _FakeConnection([
        ("FRIEND1", "Asha", 2, 125, 375, 8, received_at),
    ])
    store = SharedRankingStore("postgresql://user:pass@localhost/test")

    @contextmanager
    def fake_connect():
        yield connection

    monkeypatch.setattr(store, "_connect", fake_connect)
    rows = store.rankings("OWNER1", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00")

    assert "GROUP BY friend_code" in connection.query
    assert "COUNT(DISTINCT NULLIF(hostname, '')) AS device_count" in connection.query
    assert len(rows) == 1
    assert rows[0]["device_count"] == 2
    assert rows[0]["upload_bytes"] == 125
    assert rows[0]["download_bytes"] == 375
    assert rows[0]["total_bytes"] == 500
    assert rows[0]["status"] == "Live"


def test_account_can_register_independent_tokens_for_multiple_computers(monkeypatch):
    connection = _FakeConnection([])
    store = SharedRankingStore("postgresql://user:pass@localhost/test")

    @contextmanager
    def fake_connect():
        yield connection

    monkeypatch.setattr(store, "_connect", fake_connect)
    store.register_collector_token("OWNER1", "desktop-one-token", "Desktop One")
    store.register_collector_token("OWNER1", "desktop-two-token", "Desktop Two")

    assert len(connection.collectors) == 2
    assert {owner for owner, _label in connection.collectors.values()} == {"OWNER1"}

