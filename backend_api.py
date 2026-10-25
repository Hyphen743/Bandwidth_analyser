"""Authenticated ingestion API for local collector agents.

Run behind a trusted HTTPS reverse proxy for internet access. The service binds
to loopback by default and exposes no account, friend, or usage read endpoint.
"""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from accounts import AccountError, ensure_account_schema, ingest_usage
from db.repository import DatabaseRepository
from shared_rankings import SharedRankingError, SharedRankingStore, shared_database_url

logger = logging.getLogger("bandwidth_backend")


def process_usage_request(
    auth_header: str,
    payload: dict,
    repo: DatabaseRepository,
    shared_store: SharedRankingStore | None = None,
) -> None:
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise PermissionError("collector token required")
    if shared_store is not None:
        shared_store.ingest_usage(token.strip(), payload)
    else:
        ingest_usage(token.strip(), payload, repo)


class Handler(BaseHTTPRequestHandler):
    server_version = "BandwidthAnalyzerIngest/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        logger.info("%s - %s", self.client_address[0], fmt % args)

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/v1/usage":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send(400, {"error": "invalid content length"})
            return
        if length <= 0 or length > 4096:
            self._send(413, {"error": "sample body must be 1–4096 bytes"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            process_usage_request(
                self.headers.get("Authorization", ""), payload, self.server.repo,
                getattr(self.server, "shared_store", None),
            )
        except PermissionError:
            self._send(401, {"error": "invalid collector token"})
            return
        except (AccountError, ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
            return
        except SharedRankingError as exc:
            logger.error("Shared ranking ingestion failed: %s", exc)
            self._send(503, {"error": "shared usage storage is temporarily unavailable"})
            return
        self._send(202, {"status": "accepted"})


def main() -> None:
    repo = DatabaseRepository()
    shared_store = None
    if shared_database_url():
        shared_store = SharedRankingStore(shared_database_url())
        shared_store.ensure_schema()
    else:
        repo = ensure_account_schema(repo)
    host = os.environ.get("BANDWIDTH_API_HOST", "127.0.0.1")
    port = int(os.environ.get("BANDWIDTH_API_PORT", os.environ.get("PORT", "8502")))
    server = ThreadingHTTPServer((host, port), Handler)
    server.repo = repo
    server.shared_store = shared_store
    logger.info("Collector ingestion API listening at %s:%s", host, port)
    print(f"Collector ingestion API listening at http://{host}:{port}")
    print("For internet access, put a trusted HTTPS proxy in front of this loopback service.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
