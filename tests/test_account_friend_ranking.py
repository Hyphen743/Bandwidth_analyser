from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from accounts import (
    AccountError, add_friend, authenticate, create_account, create_collector_token,
    get_rankings, ingest_usage, list_friends, remove_friend,
)
from backend_api import process_usage_request
from collector.agent import upload_sample
from db.repository import DatabaseRepository


@pytest.fixture
def repo(tmp_path):
    return DatabaseRepository(tmp_path / "test.db")


def test_signup_hash_login_and_unique_friend_codes(repo):
    alice = create_account("alice", "a-strong-password", repo)
    bob = create_account("bob", "another-strong-password", repo)
    assert alice["friend_code"] != bob["friend_code"]
    user = authenticate("alice", "a-strong-password", repo)
    assert user["account_id"] == alice["account_id"]
    assert authenticate("alice", "wrong-password", repo) is None
    with repo.get_connection() as conn:
        encoded = conn.execute("SELECT password_hash FROM accounts WHERE account_id=?", (alice["account_id"],)).fetchone()[0]
    assert encoded.startswith("scrypt$")
    assert "a-strong-password" not in encoded
    with pytest.raises(AccountError, match="already taken"):
        create_account("ALICE", "another-strong-password", repo)


def test_friendships_are_directional_duplicate_safe_and_removable(repo):
    alice = create_account("alice", "a-strong-password", repo)
    bob = create_account("bob", "another-strong-password", repo)
    assert add_friend(alice["account_id"], bob["friend_code"], repo) == "bob"
    assert [f["username"] for f in list_friends(alice["account_id"], repo)] == ["bob"]
    assert list_friends(bob["account_id"], repo) == []
    with pytest.raises(AccountError, match="already"):
        add_friend(alice["account_id"], bob["friend_code"], repo)
    with pytest.raises(AccountError, match="own"):
        add_friend(alice["account_id"], alice["friend_code"], repo)
    with pytest.raises(AccountError, match="No account"):
        add_friend(alice["account_id"], "INVALID", repo)
    remove_friend(alice["account_id"], bob["account_id"], repo)
    assert list_friends(alice["account_id"], repo) == []


def test_rankings_show_only_permitted_actual_samples_and_staleness(repo):
    alice = create_account("alice", "a-strong-password", repo)
    bob = create_account("bob", "another-strong-password", repo)
    charlie = create_account("charlie", "a-third-strong-password", repo)
    dave = create_account("dave", "a-fourth-strong-password", repo)
    add_friend(alice["account_id"], bob["friend_code"], repo)
    add_friend(alice["account_id"], dave["friend_code"], repo)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    token = create_collector_token(bob["account_id"], repo)
    ingest_usage(token, {"ts": now, "bytes_up": 200, "bytes_down": 800, "hostname": "Bob-PC"}, repo)
    ranking = get_rankings(alice["account_id"], now[:10] + " 00:00:00", now, repo)
    assert {row["username"] for row in ranking} == {"alice", "bob", "dave"}
    bob_row = next(row for row in ranking if row["username"] == "bob")
    assert (bob_row["upload_bytes"], bob_row["download_bytes"], bob_row["total_bytes"]) == (200, 800, 1000)
    assert bob_row["status"] == "Live"
    old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    ingest_usage(create_collector_token(dave["account_id"], repo), {"ts": old, "bytes_up": 10, "bytes_down": 20}, repo)
    ranking = get_rankings(alice["account_id"], now[:10] + " 00:00:00", now, repo)
    assert next(row for row in ranking if row["username"] == "alice")["status"] == "Unavailable"
    assert next(row for row in ranking if row["username"] == "dave")["status"] == "Unavailable"
    historical = get_rankings(alice["account_id"], old[:10] + " 00:00:00", now, repo)
    assert next(row for row in historical if row["username"] == "dave")["status"] == "Stale"
    with pytest.raises(PermissionError):
        ingest_usage("not-a-token", {"ts": now, "bytes_up": 1, "bytes_down": 1}, repo)
    with pytest.raises(ValueError):
        ingest_usage(token, {"ts": now, "bytes_up": -1, "bytes_down": 0}, repo)
    assert charlie["account_id"] not in {row["account_id"] for row in ranking}


def test_authenticated_ingestion_endpoint_and_agent_publisher(repo, monkeypatch):
    user = create_account("alice", "a-strong-password", repo)
    token = create_collector_token(user["account_id"], repo)
    sample = {"sample_id": "stable-sample-1", "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "bytes_up": 20, "bytes_down": 30, "hostname": "test"}
    with pytest.raises(PermissionError):
        process_usage_request("", sample, repo)
    with pytest.raises(PermissionError):
        process_usage_request("Bearer incorrect-token", sample, repo)
    process_usage_request(f"Bearer {token}", sample, repo)
    process_usage_request(f"Bearer {token}", sample, repo)

    captured = {}

    class FakeResponse:
        status = 202
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["payload"] = request.data
        return FakeResponse()

    monkeypatch.setattr("collector.agent.urlopen", fake_urlopen)
    upload_sample("http://localhost:8502/api/v1/usage", token, sample)
    assert captured["auth"] == f"Bearer {token}"
    with repo.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM account_usage WHERE account_id=?", (user["account_id"],)).fetchone()[0]
    assert count == 1
