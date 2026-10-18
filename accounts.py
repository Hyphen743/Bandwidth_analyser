"""Account, directional friendship, and shared usage storage."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from db.repository import DatabaseRepository


class AccountError(ValueError):
    pass


def ensure_account_schema(repo: DatabaseRepository | None = None) -> DatabaseRepository:
    repo = repo or DatabaseRepository()
    with repo.get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            friend_code TEXT NOT NULL UNIQUE,
            collector_token_hash TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS friendships (
            owner_user_id INTEGER NOT NULL,
            friend_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (owner_user_id, friend_user_id),
            CHECK (owner_user_id <> friend_user_id),
            FOREIGN KEY (owner_user_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
            FOREIGN KEY (friend_user_id) REFERENCES accounts(account_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS account_usage (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            sample_id TEXT,
            ts TEXT NOT NULL,
            bytes_up INTEGER NOT NULL CHECK (bytes_up >= 0),
            bytes_down INTEGER NOT NULL CHECK (bytes_down >= 0),
            hostname TEXT NOT NULL DEFAULT '',
            received_at TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_account_usage_account_ts ON account_usage(account_id, ts);
        CREATE INDEX IF NOT EXISTS idx_accounts_collector_token ON accounts(collector_token_hash);
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(account_usage)")}
        if "sample_id" not in columns:
            conn.execute("ALTER TABLE account_usage ADD COLUMN sample_id TEXT")
        if "received_at" not in columns:
            conn.execute("ALTER TABLE account_usage ADD COLUMN received_at TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_account_usage_idempotency ON account_usage(account_id,sample_id) WHERE sample_id IS NOT NULL")
    return repo


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=32768, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
    return f"scrypt$32768$8$1${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=32, maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_account(username: str, password: str, repo: DatabaseRepository | None = None) -> dict[str, Any]:
    repo = ensure_account_schema(repo)
    username = username.strip()
    if not 3 <= len(username) <= 32 or any(ch.isspace() for ch in username):
        raise AccountError("Username must be 3–32 characters with no spaces.")
    if len(password) < 8:
        raise AccountError("Password must be at least 8 characters.")
    with repo.get_connection() as conn:
        for _ in range(5):
            code = secrets.token_hex(6).upper()
            try:
                cur = conn.execute("INSERT INTO accounts(username,password_hash,friend_code) VALUES(?,?,?)", (username, _password_hash(password), code))
                return {"account_id": cur.lastrowid, "username": username, "friend_code": code}
            except sqlite3.IntegrityError as exc:
                if "username" in str(exc).lower():
                    raise AccountError("That username is already taken.") from exc
                if "friend_code" not in str(exc).lower():
                    raise
        raise AccountError("Could not generate a unique friend code. Please retry.")


def authenticate(username: str, password: str, repo: DatabaseRepository | None = None) -> dict[str, Any] | None:
    repo = ensure_account_schema(repo)
    with repo.get_connection() as conn:
        row = conn.execute("SELECT account_id, username, password_hash, friend_code FROM accounts WHERE username = ?", (username.strip(),)).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        return None
    return {"account_id": row["account_id"], "username": row["username"], "friend_code": row["friend_code"]}


def get_friend_code(account_id: int, repo: DatabaseRepository | None = None) -> str:
    repo = ensure_account_schema(repo)
    with repo.get_connection() as conn:
        row = conn.execute("SELECT friend_code FROM accounts WHERE account_id=?", (int(account_id),)).fetchone()
    if not row:
        raise AccountError("Account not found.")
    return row["friend_code"]


def add_friend(account_id: int, friend_code: str, repo: DatabaseRepository | None = None) -> str:
    repo = ensure_account_schema(repo)
    with repo.get_connection() as conn:
        friend = conn.execute("SELECT account_id, username FROM accounts WHERE friend_code=?", (friend_code.strip().upper(),)).fetchone()
        if not friend:
            raise AccountError("No account has that friend code.")
        if friend["account_id"] == int(account_id):
            raise AccountError("You cannot add your own account.")
        try:
            conn.execute("INSERT INTO friendships(owner_user_id,friend_user_id) VALUES(?,?)", (int(account_id), friend["account_id"]))
        except sqlite3.IntegrityError as exc:
            raise AccountError("This friend is already on your list.") from exc
        return friend["username"]


def remove_friend(account_id: int, friend_id: int, repo: DatabaseRepository | None = None) -> None:
    repo = ensure_account_schema(repo)
    with repo.get_connection() as conn:
        conn.execute("DELETE FROM friendships WHERE owner_user_id=? AND friend_user_id=?", (int(account_id), int(friend_id)))


def get_rankings(account_id: int, start_ts: str, end_ts: str, repo: DatabaseRepository | None = None, stale_after_seconds: int = 120) -> list[dict[str, Any]]:
    repo = ensure_account_schema(repo)
    with repo.get_connection() as conn:
        rows = conn.execute("""
            SELECT a.account_id, a.username,
                   SUM(CASE WHEN u.ts >= ? AND u.ts <= ? THEN u.bytes_down ELSE 0 END) AS bytes_down,
                   SUM(CASE WHEN u.ts >= ? AND u.ts <= ? THEN u.bytes_up ELSE 0 END) AS bytes_up,
                   MAX(u.ts) AS last_seen,
                   SUM(CASE WHEN u.ts >= ? AND u.ts <= ? THEN 1 ELSE 0 END) AS sample_count
            FROM accounts a
            LEFT JOIN account_usage u ON u.account_id=a.account_id
            WHERE a.account_id=? OR a.account_id IN (SELECT friend_user_id FROM friendships WHERE owner_user_id=?)
            GROUP BY a.account_id, a.username
        """, (start_ts, end_ts, start_ts, end_ts, start_ts, end_ts, int(account_id), int(account_id))).fetchall()
    cutoff = datetime.now() - timedelta(seconds=stale_after_seconds)
    results = []
    for row in rows:
        sample_count = int(row["sample_count"] or 0)
        last_seen = row["last_seen"]
        stale = True
        if last_seen:
            try:
                stale = datetime.strptime(last_seen[:19], "%Y-%m-%d %H:%M:%S") < cutoff
            except ValueError:
                stale = True
        unavailable = sample_count == 0
        down = int(row["bytes_down"] or 0) if not unavailable else None
        up = int(row["bytes_up"] or 0) if not unavailable else None
        results.append({"account_id": row["account_id"], "username": row["username"], "download_bytes": down,
                        "upload_bytes": up, "total_bytes": (down + up) if down is not None else None,
                        "last_seen": last_seen, "status": "Unavailable" if unavailable else ("Stale" if stale else "Live")})
    results.sort(key=lambda item: (item["total_bytes"] is None, -(item["total_bytes"] or 0), item["username"].casefold()))
    return results


def list_friends(account_id: int, repo: DatabaseRepository | None = None) -> list[dict[str, Any]]:
    repo = ensure_account_schema(repo)
    with repo.get_connection() as conn:
        rows = conn.execute("SELECT a.account_id,a.username,a.friend_code FROM friendships f JOIN accounts a ON a.account_id=f.friend_user_id WHERE f.owner_user_id=? ORDER BY a.username", (int(account_id),)).fetchall()
    return [dict(row) for row in rows]


def create_collector_token(account_id: int, repo: DatabaseRepository | None = None) -> str:
    repo = ensure_account_schema(repo)
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with repo.get_connection() as conn:
        conn.execute("UPDATE accounts SET collector_token_hash=? WHERE account_id=?", (digest, int(account_id)))
    return token


def ingest_usage(token: str, payload: dict[str, Any], repo: DatabaseRepository | None = None) -> bool:
    repo = ensure_account_schema(repo)
    try:
        up, down = int(payload["bytes_up"]), int(payload["bytes_down"])
        ts = datetime.strptime(str(payload["ts"]), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except (KeyError, ValueError, TypeError) as exc:
        raise AccountError("Sample must contain a timestamp and nonnegative byte counters.") from exc
    if min(up, down) < 0 or max(up, down) > 2**63 - 1:
        raise AccountError("Byte counters are outside the allowed range.")
    hostname = str(payload.get("hostname", ""))[:100]
    sample_id = str(payload.get("sample_id", "")).strip()[:100] or None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with repo.get_connection() as conn:
        account = conn.execute("SELECT account_id FROM accounts WHERE collector_token_hash=?", (digest,)).fetchone()
        if not account:
            raise PermissionError("Invalid collector token.")
        cursor = conn.execute("""INSERT INTO account_usage(account_id,sample_id,ts,bytes_up,bytes_down,hostname,received_at)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
            (account["account_id"], sample_id, ts, up, down, hostname, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return cursor.rowcount == 1


def get_account_usage_summary(account_id: int, repo: DatabaseRepository | None = None) -> dict[str, Any]:
    repo = ensure_account_schema(repo)
    with repo.get_connection() as conn:
        row = conn.execute("""SELECT COALESCE(SUM(bytes_up),0) AS bytes_up,
            COALESCE(SUM(bytes_down),0) AS bytes_down, MAX(ts) AS last_sample_ts,
            MAX(received_at) AS last_sync_ts FROM account_usage WHERE account_id=?""", (int(account_id),)).fetchone()
    return dict(row)
