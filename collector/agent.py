"""Small authenticated client for publishing actual collector samples."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def normalize_ingest_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Provide a full backend URL ending in /api/v1/usage.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Collector uploads require HTTPS except for local development.")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("Backend URL cannot include credentials, query parameters, or fragments.")
    return value.strip().rstrip("/")


def upload_sample(url: str, token: str, sample: dict) -> None:
    """Send one actual usage sample to the authenticated ingestion endpoint."""
    endpoint = normalize_ingest_url(url)
    if not endpoint.endswith("/api/v1/usage"):
        raise ValueError("Backend URL must end in /api/v1/usage.")
    body = json.dumps(sample, separators=(",", ":")).encode("utf-8")
    request = Request(endpoint, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "BandwidthAnalyzerCollector/1.0",
    })
    with urlopen(request, timeout=10) as response:
        if response.status not in {200, 202}:
            raise RuntimeError(f"Backend rejected sample (HTTP {response.status}).")
