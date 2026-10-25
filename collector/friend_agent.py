"""Standalone local interface-counter collector for deployed friend rankings."""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.agent import upload_sample

logger = logging.getLogger("friend_collector")


def default_route_interface(counters: dict) -> str | None:
    """Resolve the adapter used for an IPv4 internet route without sending data."""
    try:
        target = socket.getaddrinfo("8.8.8.8", 53, socket.AF_INET, socket.SOCK_DGRAM)[0][4][0]
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((target, 53))
            local_ip = probe.getsockname()[0]
        for name, addresses in psutil.net_if_addrs().items():
            if name in counters and any(
                item.family == socket.AF_INET and item.address == local_ip for item in addresses
            ):
                return name
    except (OSError, IndexError):
        logger.debug("Could not resolve the default-route adapter", exc_info=True)
    if len(counters) == 1:
        return next(iter(counters))
    return None


def _deltas(previous: dict, current: dict, interface: str) -> tuple[int, int] | None:
    if interface not in previous or interface not in current:
        return None
    sent = int(current[interface].bytes_sent) - int(previous[interface].bytes_sent)
    received = int(current[interface].bytes_recv) - int(previous[interface].bytes_recv)
    if sent < 0 or received < 0:
        return None
    return sent, received


def run_collector(backend_url: str, token: str, interval: float) -> None:
    previous = psutil.net_io_counters(pernic=True)
    interface = default_route_interface(previous)
    if not interface:
        raise RuntimeError("Could not identify the active network adapter; no data was uploaded.")
    logger.info("Monitoring adapter %s every %.1f seconds. Press Ctrl+C to stop.", interface, interval)
    last_route_check = time.monotonic()
    last_report = time.monotonic()
    uploaded, failed = 0, 0

    while True:
        time.sleep(interval)
        current = psutil.net_io_counters(pernic=True)
        if time.monotonic() - last_route_check >= 30:
            selected = default_route_interface(current)
            last_route_check = time.monotonic()
            if selected and selected != interface:
                interface = selected
                previous = current
                logger.info("Network route changed; using adapter %s after a fresh baseline.", interface)
                continue

        delta = _deltas(previous, current, interface)
        previous = current
        if delta is None:
            logger.warning("Counter reset or adapter changed; skipping this interval.")
            continue
        sent, received = delta
        sample = {
            "sample_id": uuid.uuid4().hex,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes_up": sent,
            "bytes_down": received,
            "hostname": socket.gethostname(),
            "interface": interface,
        }
        try:
            upload_sample(backend_url, token, sample)
        except Exception as exc:
            failed += 1
        else:
            uploaded += 1
        if time.monotonic() - last_report >= 60:
            logger.info("Last minute: %d intervals uploaded, %d failed.", uploaded, failed)
            uploaded, failed = 0, 0
            last_report = time.monotonic()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-url", required=True, help="HTTPS URL ending in /api/v1/usage")
    parser.add_argument("--token", required=True, help="Collector token created in the Rankings page")
    parser.add_argument("--interval", type=float, default=5.0, help="Sampling/upload interval in seconds (minimum 2)")
    args = parser.parse_args()
    if args.interval < 2:
        parser.error("--interval must be at least 2 seconds")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run_collector(args.backend_url, args.token, args.interval)
    except KeyboardInterrupt:
        logger.info("Collector stopped.")
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
