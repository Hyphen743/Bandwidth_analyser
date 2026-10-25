"""Optional PostgreSQL store for deployment-wide directional friend rankings.

This module intentionally uses a separate database from the app's SQLite
telemetry and account database. Set BANDWIDTH_SHARED_DATABASE_URL in both the
Streamlit app and ingestion API to enable cross-device rankings.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any


class SharedRankingError(RuntimeError):
    """A safe, user-displayable shared-ranking error."""


def shared_database_url() -> str | None:
    return os.environ.get("BANDWIDTH_SHARED_DATABASE_URL", "").strip() or None


class SharedRankingStore:
    """Small isolated persistence layer for shared friend ranking data."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise SharedRankingError("BANDWIDTH_SHARED_DATABASE_URL must be a PostgreSQL connection URL.")
        self.database_url = database_url

    def _connect(self):
        try:
            import psycopg
            return psycopg.connect(self.database_url, connect_timeout=8)
        except ImportError as exc:
            raise SharedRankingError("Install the PostgreSQL driver with: pip install 'psycopg[binary]>=3.2'") from exc
        except Exception as exc:
            raise SharedRankingError("Could not connect to the shared ranking database. Check its URL and availability.") from exc

    def ensure_schema(self) -> None:
        """Create only namespaced tables in the separate shared database."""
        statements = (
        """CREATE TABLE IF NOT EXISTS ba_shared_accounts (
            friend_code TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            collector_token_hash TEXT UNIQUE,
            registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS ba_shared_collectors (
            collector_id BIGSERIAL PRIMARY KEY,
            friend_code TEXT NOT NULL REFERENCES ba_shared_accounts(friend_code) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            device_name TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen TIMESTAMPTZ
        )""",
        """CREATE TABLE IF NOT EXISTS ba_shared_friendships (
            owner_code TEXT NOT NULL REFERENCES ba_shared_accounts(friend_code) ON DELETE CASCADE,
            friend_code TEXT NOT NULL REFERENCES ba_shared_accounts(friend_code) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (owner_code, friend_code),
            CHECK (owner_code <> friend_code)
        )""",
        """CREATE TABLE IF NOT EXISTS ba_shared_usage (
            usage_id BIGSERIAL PRIMARY KEY,
            friend_code TEXT NOT NULL REFERENCES ba_shared_accounts(friend_code) ON DELETE CASCADE,
            sample_id TEXT,
            ts TIMESTAMPTZ NOT NULL,
            received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            bytes_up BIGINT NOT NULL CHECK (bytes_up >= 0),
            bytes_down BIGINT NOT NULL CHECK (bytes_down >= 0),
            hostname TEXT NOT NULL DEFAULT '',
            UNIQUE (friend_code, sample_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_ba_shared_usage_owner_time ON ba_shared_usage(friend_code, ts)",
        )
        try:
            with self._connect() as conn:
                for statement in statements:
                    conn.execute(statement)
        except SharedRankingError:
            raise
        except Exception as exc:
            raise SharedRankingError("Could not initialize the separate shared ranking tables.") from exc

    def register_account(self, friend_code: str, username: str) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO ba_shared_accounts(friend_code, username) VALUES (%s, %s)
                       ON CONFLICT(friend_code) DO UPDATE SET username=EXCLUDED.username""",
                    (friend_code.strip().upper(), username.strip()),
                )
        except SharedRankingError:
            raise
        except Exception as exc:
            raise SharedRankingError("Could not register this account in the shared ranking database.") from exc

    def add_friend(self, owner_code: str, friend_code: str) -> str:
        owner_code, friend_code = owner_code.strip().upper(), friend_code.strip().upper()
        if not friend_code:
            raise SharedRankingError("Enter your friend's code.")
        if owner_code == friend_code:
            raise SharedRankingError("You cannot add your own account.")
        try:
            with self._connect() as conn:
                friend = conn.execute(
                    "SELECT username FROM ba_shared_accounts WHERE friend_code=%s", (friend_code,)
                ).fetchone()
                if not friend:
                    raise SharedRankingError("That friend code is not registered in the shared ranking service yet.")
                conn.execute(
                    "INSERT INTO ba_shared_friendships(owner_code, friend_code) VALUES (%s, %s)",
                    (owner_code, friend_code),
                )
            return str(friend[0])
        except SharedRankingError:
            raise
        except Exception as exc:
            if "ba_shared_friendships_pkey" in str(exc) or "duplicate key" in str(exc).lower():
                raise SharedRankingError("This friend is already on your list.") from exc
            raise SharedRankingError("Could not add this friend. Check the shared database connection.") from exc

    def remove_friend(self, owner_code: str, friend_code: str) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM ba_shared_friendships WHERE owner_code=%s AND friend_code=%s",
                    (owner_code.strip().upper(), friend_code.strip().upper()),
                )
        except Exception as exc:
            raise SharedRankingError("Could not remove this friend from the shared ranking database.") from exc

    def list_friends(self, owner_code: str) -> list[dict[str, str]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT a.friend_code, a.username
                       FROM ba_shared_friendships f
                       JOIN ba_shared_accounts a ON a.friend_code=f.friend_code
                       WHERE f.owner_code=%s ORDER BY a.username""",
                    (owner_code.strip().upper(),),
                ).fetchall()
        except Exception as exc:
            raise SharedRankingError("Could not load the friend list from the shared ranking database.") from exc
        return [{"friend_code": str(code), "username": str(name)} for code, name in rows]

    def list_collectors(self, friend_code: str) -> list[dict[str, Any]]:
        """List a user's registered computers without exposing collector secrets."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT collector_id, device_name, created_at, last_seen
                       FROM ba_shared_collectors WHERE friend_code=%s
                       ORDER BY created_at, collector_id""",
                    (friend_code.strip().upper(),),
                ).fetchall()
        except Exception as exc:
            raise SharedRankingError("Could not load registered computers from the shared ranking database.") from exc
        return [
            {
                "collector_id": int(row[0]),
                "device_name": str(row[1] or "Computer not yet seen"),
                "created_at": row[2].isoformat() if row[2] else None,
                "last_seen": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]

    def revoke_collector(self, friend_code: str, collector_id: int) -> None:
        """Revoke only the selected computer's collector token."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM ba_shared_collectors WHERE friend_code=%s AND collector_id=%s",
                    (friend_code.strip().upper(), int(collector_id)),
                )
        except Exception as exc:
            raise SharedRankingError("Could not revoke that computer's collector token.") from exc

    def rankings(self, owner_code: str, start_ts: str, end_ts: str, stale_after_seconds: int = 120) -> list[dict[str, Any]]:
        start = datetime.fromisoformat(start_ts).astimezone(timezone.utc)
        end = datetime.fromisoformat(end_ts).astimezone(timezone.utc)
        sql = """
        WITH visible_accounts AS (
            SELECT %s::text AS friend_code
            UNION
            SELECT friend_code FROM ba_shared_friendships WHERE owner_code=%s
        ), period_usage AS (
            SELECT friend_code, SUM(bytes_up) AS bytes_up, SUM(bytes_down) AS bytes_down,
                   COUNT(*) AS sample_count,
                   COUNT(DISTINCT NULLIF(hostname, '')) AS device_count
            FROM ba_shared_usage WHERE ts >= %s AND ts <= %s
            GROUP BY friend_code
        ), latest AS (
            SELECT friend_code, MAX(received_at) AS last_seen
            FROM ba_shared_usage GROUP BY friend_code
        )
        SELECT a.friend_code, a.username, COALESCE(p.device_count, 0) AS device_count,
               p.bytes_up, p.bytes_down, COALESCE(p.sample_count, 0) AS sample_count, l.last_seen
        FROM visible_accounts v
        JOIN ba_shared_accounts a ON a.friend_code=v.friend_code
        LEFT JOIN period_usage p ON p.friend_code=a.friend_code
        LEFT JOIN latest l ON l.friend_code=a.friend_code
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, (owner_code.upper(), owner_code.upper(), start, end)).fetchall()
        except Exception as exc:
            raise SharedRankingError("Could not load metrics from the shared ranking database.") from exc
        now = datetime.now(timezone.utc)
        results = []
        for code, username, device_count, up, down, count, last_seen in rows:
            unavailable = int(count or 0) == 0
            stale = last_seen is None or (now - last_seen).total_seconds() > stale_after_seconds
            up_bytes = int(up or 0) if not unavailable else None
            down_bytes = int(down or 0) if not unavailable else None
            results.append({
                "friend_code": code,
                "username": username,
                "device_count": int(device_count or 0),
                "download_bytes": down_bytes,
                "upload_bytes": up_bytes,
                "total_bytes": (up_bytes + down_bytes) if up_bytes is not None else None,
                "last_seen": last_seen.isoformat() if last_seen else None,
                "status": "Unavailable" if unavailable else ("Stale" if stale else "Live"),
            })
        results.sort(key=lambda item: (item["total_bytes"] is None, -(item["total_bytes"] or 0), item["username"].casefold()))
        return results

    def register_collector_token(self, friend_code: str, token: str, device_name: str = "") -> None:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        friend_code = friend_code.strip().upper()
        try:
            with self._connect() as conn:
                inserted = conn.execute(
                    """INSERT INTO ba_shared_collectors(friend_code, token_hash, device_name)
                       VALUES (%s, %s, %s) ON CONFLICT(token_hash) DO NOTHING""",
                    (friend_code, digest, device_name.strip()[:100]),
                ).rowcount
                existing = conn.execute(
                    "SELECT friend_code FROM ba_shared_collectors WHERE token_hash=%s",
                    (digest,),
                ).fetchone()
                if not existing or existing[0] != friend_code:
                    raise SharedRankingError("Could not register a collector token for this account.")
        except SharedRankingError:
            raise
        except Exception as exc:
            raise SharedRankingError("Could not register this computer with the shared ranking database.") from exc

    def ingest_usage(self, token: str, payload: dict[str, Any]) -> bool:
        try:
            up, down = int(payload["bytes_up"]), int(payload["bytes_down"])
            ts = datetime.fromisoformat(str(payload["ts"]).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.astimezone()
            ts = ts.astimezone(timezone.utc)
        except (KeyError, ValueError, TypeError) as exc:
            raise SharedRankingError("Sample must contain an ISO timestamp and nonnegative byte counters.") from exc
        if min(up, down) < 0 or max(up, down) > 2**63 - 1:
            raise SharedRankingError("Byte counters are outside the allowed range.")
        sample_id = str(payload.get("sample_id", "")).strip()[:100] or None
        hostname = str(payload.get("hostname", ""))[:100]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        try:
            with self._connect() as conn:
                account = conn.execute(
                    """SELECT friend_code FROM ba_shared_collectors WHERE token_hash=%s
                       UNION ALL
                       SELECT friend_code FROM ba_shared_accounts WHERE collector_token_hash=%s
                       LIMIT 1""",
                    (token_hash, token_hash),
                ).fetchone()
                if not account:
                    raise PermissionError("Invalid collector token.")
                conn.execute(
                    """UPDATE ba_shared_collectors
                       SET device_name=COALESCE(NULLIF(%s, ''), device_name), last_seen=NOW()
                       WHERE token_hash=%s""",
                    (hostname, token_hash),
                )
                cursor = conn.execute(
                    """INSERT INTO ba_shared_usage(friend_code, sample_id, ts, bytes_up, bytes_down, hostname)
                       VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (friend_code, sample_id) DO NOTHING""",
                    (account[0], sample_id, ts, up, down, hostname),
                )
                return cursor.rowcount == 1
        except PermissionError:
            raise
        except Exception as exc:
            raise SharedRankingError("Could not store the collector sample in the shared ranking database.") from exc
