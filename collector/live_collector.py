"""
Live Network Collector for Bandwidth Usage Monitor.
Continuously samples psutil network I/O counters, maps sockets to processes,
probes network latency/loss, and stores telemetry in SQLite.
"""

from __future__ import annotations

import logging
from collections import deque
import socket
import threading
import time
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil

from collector.ping_probe import PingProbe
from collector.process_mapper import ProcessMapper
from db.repository import DatabaseRepository

logger = logging.getLogger("live_collector")


class LiveCollector:
    """Background collector for real-time network traffic and telemetry."""

    _instances: Dict[str, "LiveCollector"] = {}
    _lock = threading.Lock()

    def __init__(self, repo: Optional[DatabaseRepository] = None, sample_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        self.repo = repo or DatabaseRepository()
        self.sample_callback = sample_callback
        self.mapper = ProcessMapper()
        self.ping_probe = PingProbe(target_host=self.repo.get_setting("ping_host", "8.8.8.8"))
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Cached entity maps
        self._app_cache: Dict[str, int] = {}
        self._device_id: int = 1
        self._load_entity_cache()

        # Telemetry state
        self.current_mbps_up: float = 0.0
        self.current_mbps_down: float = 0.0
        self.current_latency_ms: float = 0.0
        self.current_jitter_ms: float = 0.0
        self.current_loss_pct: float = 0.0
        self.current_utilization_pct: float = 0.0
        self.network_interface: Optional[str] = None
        self.last_sample_ts: Optional[str] = None
        self.is_active: bool = False
        self._sample_lock = threading.Lock()
        self._samples = deque(maxlen=180)

    @classmethod
    def get_instance(cls, repo: Optional[DatabaseRepository] = None) -> "LiveCollector":
        """Singleton accessor for use across Streamlit pages."""
        instance_repo = repo or DatabaseRepository()
        key = str(instance_repo.db_path.resolve())
        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = LiveCollector(instance_repo)
            return cls._instances[key]

    def _load_entity_cache(self) -> None:
        """Cache application and device IDs from database."""
        try:
            apps = self.repo.get_applications()
            for _, row in apps.iterrows():
                self._app_cache[row["name"].lower()] = row["app_id"]

            devices = self.repo.get_devices()
            if not devices.empty:
                self._device_id = int(devices.iloc[0]["device_id"])
        except Exception as e:
            logger.warning("Failed loading entity cache from DB: %s", e)
            self._device_id = 1

    def _get_app_id(self, app_name: str, category: str = "browsing") -> Optional[int]:
        """Resolve or insert application ID."""
        key = app_name.lower()
        if key in self._app_cache:
            return self._app_cache[key]
        try:
            new_id = self.repo.insert_application(app_name, category)
            self._app_cache[key] = new_id
            return new_id
        except Exception as e:
            logger.warning("Failed resolving application %s: %s", app_name, e)
            return None

    def start(self, interval_sec: Optional[float] = None) -> None:
        """Start the collector thread in the background."""
        if self._thread and self._thread.is_alive():
            logger.info("Collector thread already running.")
            return

        interval = interval_sec or float(self.repo.get_setting("collector_interval_sec", "2.0"))
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._collect_loop,
            args=(interval,),
            name="LiveCollectorThread",
            daemon=True
        )
        self.is_active = True
        self._thread.start()
        logger.info("LiveCollector started with interval %.1fs", interval)

    def stop(self) -> None:
        """Stop the background collector thread."""
        self._stop_event.set()
        self.is_active = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("LiveCollector stopped.")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop_event.is_set()

    def get_latest_stats(self) -> Dict[str, Any]:
        """Return current live telemetry snapshot."""
        return {
            "is_running": self.is_running(),
            "mbps_up": round(self.current_mbps_up, 2),
            "mbps_down": round(self.current_mbps_down, 2),
            "total_mbps": round(self.current_mbps_up + self.current_mbps_down, 2),
            "latency_ms": round(self.current_latency_ms, 1),
            "jitter_ms": round(self.current_jitter_ms, 1),
            "packet_loss_pct": round(self.current_loss_pct, 1),
            "utilization_pct": round(self.current_utilization_pct, 1),
            "network_interface": self.network_interface,
            "last_sample_ts": self.last_sample_ts
        }

    def get_recent_samples(self, limit: int = 60) -> list[Dict[str, Any]]:
        """Return the newest in-memory interface counter samples."""
        with self._sample_lock:
            return list(self._samples)[-limit:]

    def _collect_loop(self, interval_sec: float) -> None:
        """Sample the default-route interface, avoiding overlapping adapter totals."""
        prev_io = psutil.net_io_counters(pernic=True)
        prev_time = time.time()
        self.network_interface = self._resolve_default_route_interface(prev_io)
        last_route_check = time.monotonic()
        ping_counter = 0

        prev_sample_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        while not self._stop_event.is_set():
            if self._stop_event.wait(interval_sec):
                break
            now_time = time.time()
            elapsed = max(0.001, now_time - prev_time)

            current_io = psutil.net_io_counters(pernic=True)
            if time.monotonic() - last_route_check >= 30:
                selected_interface = self._resolve_default_route_interface(current_io)
                last_route_check = time.monotonic()
                if selected_interface != self.network_interface:
                    self.network_interface = selected_interface
                    prev_io = current_io
                    prev_time = now_time
                    logger.info("Live counter interface changed to %s; establishing a fresh baseline.", selected_interface)
                    continue

            bytes_sent_delta, bytes_recv_delta = self._single_interface_deltas(
                prev_io, current_io, self.network_interface
            )

            prev_io = current_io
            prev_time = now_time

            # If the default route cannot be mapped to a local adapter, skip
            # this interval instead of summing virtual interfaces and reporting
            # an inflated volume as real usage.
            if bytes_sent_delta is None or bytes_recv_delta is None:
                self.current_mbps_up = 0.0
                self.current_mbps_down = 0.0
                continue

            # Compute Mbps
            mbps_up = (bytes_sent_delta * 8.0) / (elapsed * 1000.0 * 1000.0)
            mbps_down = (bytes_recv_delta * 8.0) / (elapsed * 1000.0 * 1000.0)
            self.current_mbps_up = mbps_up
            self.current_mbps_down = mbps_down

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sample_id = uuid.uuid4().hex
            self.last_sample_ts = now_str
            with self._sample_lock:
                self._samples.append({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "mbps_up": mbps_up,
                    "mbps_down": mbps_down,
                    "mbps_total": mbps_up + mbps_down,
                })

            # Periodic ping probe (every ~6 seconds)
            ping_counter += 1
            if ping_counter >= 3:
                ping_counter = 0
                telemetry = self.ping_probe.probe(count=2)
                self.current_latency_ms = telemetry["latency_ms"]
                self.current_jitter_ms = telemetry["jitter_ms"]
                self.current_loss_pct = telemetry["packet_loss_pct"]

                cap_mbps = float(self.repo.get_setting("capacity_mbps", "100.0"))
                self.current_utilization_pct = min(100.0, ((mbps_up + mbps_down) / cap_mbps) * 100.0)

                # Store metrics
                try:
                    self.repo.insert_network_metric(
                        ts=now_str,
                        latency_ms=self.current_latency_ms,
                        jitter_ms=self.current_jitter_ms,
                        packet_loss_pct=self.current_loss_pct,
                        capacity_mbps=cap_mbps,
                        utilization_pct=self.current_utilization_pct
                    )
                except Exception as e:
                    logger.debug("Failed saving live network metric: %s", e)

            # Socket counts cannot tell us per-process byte totals. Persist the
            # exact interface-counter delta as unattributed traffic instead of
            # inventing per-app shares from connection counts.
            app_id = self._get_app_id("Unattributed interface traffic", "other")
            if app_id is not None:
                try:
                    self.repo.insert_usage_batch([{
                        "session_id": None,
                        "device_id": self._device_id,
                        "app_id": app_id,
                        "ts": now_str,
                        "bytes_up": bytes_sent_delta,
                        "bytes_down": bytes_recv_delta,
                    }])
                except Exception as e:
                    logger.warning("Failed inserting live interface usage: %s", e)

            sample = {
                "sample_id": sample_id,
                "ts": now_str,
                "bytes_up": bytes_sent_delta,
                "bytes_down": bytes_recv_delta,
                "hostname": socket.gethostname(),
                "previous_sample_ts": prev_sample_ts,
            }
            if self.sample_callback:
                try:
                    self.sample_callback(sample)
                except Exception:
                    logger.warning("Live sample callback failed; local collection continues.", exc_info=True)
            prev_sample_ts = now_str

    @staticmethod
    def _resolve_default_route_interface(counters: Dict[str, Any]) -> Optional[str]:
        """Find the NIC used by the IPv4 default route without sending traffic."""
        try:
            host = "8.8.8.8"
            try:
                addresses = socket.getaddrinfo(host, 53, socket.AF_INET, socket.SOCK_DGRAM)
                target = addresses[0][4][0]
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route_probe:
                    route_probe.connect((target, 53))
                    local_ip = route_probe.getsockname()[0]
                for name, interface_addresses in psutil.net_if_addrs().items():
                    if name in counters and any(
                        address.family == socket.AF_INET and address.address == local_ip
                        for address in interface_addresses
                    ):
                        return name
            except (OSError, IndexError):
                pass
        except Exception as exc:
            logger.debug("Could not resolve the active route interface: %s", exc)

        # A single adapter is unambiguous (also supports restricted/test hosts).
        if len(counters) == 1:
            return next(iter(counters))
        return None

    @staticmethod
    def _single_interface_deltas(
        previous: Dict[str, Any], current: Dict[str, Any], interface: Optional[str]
    ) -> tuple[Optional[int], Optional[int]]:
        """Return byte deltas for one adapter; skip new/reset/missing baselines."""
        if not interface or interface not in previous or interface not in current:
            return None, None
        old, new = previous[interface], current[interface]
        sent_now, sent_before = int(new.bytes_sent), int(old.bytes_sent)
        recv_now, recv_before = int(new.bytes_recv), int(old.bytes_recv)
        if sent_now < sent_before or recv_now < recv_before:
            return None, None
        return sent_now - sent_before, recv_now - recv_before

    @staticmethod
    def _interface_deltas(previous: Dict[str, Any], current: Dict[str, Any]) -> tuple[int, int, list[str]]:
        """Sum only per-interface increments; establish baselines for new adapters."""
        sent = received = 0
        notes: list[str] = []
        prior_names, current_names = set(previous), set(current)
        for name in sorted(current_names):
            counters = current[name]
            old = previous.get(name)
            if old is None:
                notes.append(f"New interface {name!r} baseline established; prior adapter counters were not counted.")
                continue
            for field, target in (("bytes_sent", "sent"), ("bytes_recv", "received")):
                value = int(getattr(counters, field, 0))
                prior_value = int(getattr(old, field, 0))
                delta = value - prior_value if value >= prior_value else value
                if value < prior_value:
                    notes.append(f"Counter reset detected on {name!r}; restarted from the new baseline.")
                if target == "sent":
                    sent += delta
                else:
                    received += delta
        removed = prior_names - current_names
        if removed:
            notes.append(f"Interface(s) disconnected: {', '.join(sorted(removed))}.")
        return sent, received, notes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collector = LiveCollector()
    collector.start(interval_sec=2.0)
    print("Collector running for 6 seconds...")
    time.sleep(6)
    print("Snapshot:", collector.get_latest_stats())
    collector.stop()
    print("Collector stopped.")
