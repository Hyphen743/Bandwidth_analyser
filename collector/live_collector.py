"""
Live Network Collector for Bandwidth Usage Monitor.
Continuously samples psutil network I/O counters, maps sockets to processes,
probes network latency/loss, and stores telemetry in SQLite.
"""

from __future__ import annotations

import logging
import threading
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psutil

from collector.ping_probe import PingProbe
from collector.process_mapper import ProcessMapper
from db.repository import DatabaseRepository

logger = logging.getLogger("live_collector")


class LiveCollector:
    """Background collector for real-time network traffic and telemetry."""

    _instance: Optional["LiveCollector"] = None
    _lock = threading.Lock()

    def __init__(self, repo: Optional[DatabaseRepository] = None) -> None:
        self.repo = repo or DatabaseRepository()
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
        self.last_sample_ts: Optional[str] = None
        self.is_active: bool = False

    @classmethod
    def get_instance(cls, repo: Optional[DatabaseRepository] = None) -> "LiveCollector":
        """Singleton accessor for use across Streamlit pages."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = LiveCollector(repo)
            return cls._instance

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

    def _get_app_id(self, app_name: str, category: str = "browsing") -> int:
        """Resolve or insert application ID."""
        key = app_name.lower()
        if key in self._app_cache:
            return self._app_cache[key]
        try:
            new_id = self.repo.insert_application(app_name, category)
            self._app_cache[key] = new_id
            return new_id
        except Exception:
            return self._app_cache.get(list(self._app_cache.keys())[0], 1) if self._app_cache else 1

    def start(self, interval_sec: Optional[float] = None) -> None:
        """Start the collector thread in background."""
        if self._thread and self._thread.is_alive():
            logger.info("Collector thread already running.")
            return

        interval = interval_sec or float(self.repo.get_setting("collector_interval_sec", "2.0"))
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
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
            "last_sample_ts": self.last_sample_ts
        }

    def _run_loop(self, interval_sec: float) -> None:
        """Main sampling loop."""
        prev_io = psutil.net_io_counters()
        prev_time = time.time()
        ping_counter = 0

        while not self._stop_event.is_set():
            time.sleep(interval_sec)
            now_time = time.time()
            elapsed = max(0.001, now_time - prev_time)

            current_io = psutil.net_io_counters()
            bytes_sent_delta = max(0, current_io.bytes_sent - prev_io.bytes_sent)
            bytes_recv_delta = max(0, current_io.bytes_recv - prev_io.bytes_recv)

            prev_io = current_io
            prev_time = now_time

            # Compute Mbps
            mbps_up = (bytes_sent_delta * 8.0) / (elapsed * 1000.0 * 1000.0)
            mbps_down = (bytes_recv_delta * 8.0) / (elapsed * 1000.0 * 1000.0)
            self.current_mbps_up = mbps_up
            self.current_mbps_down = mbps_down

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.last_sample_ts = now_str

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

            # Attribute traffic to active processes
            active_procs = self.mapper.scan_active_connections()
            if not active_procs:
                continue

            # Apportion bytes proportionally across discovered sockets
            num_sockets = sum(p.get("connections_count", 1) for p in active_procs)
            num_sockets = max(1, num_sockets)

            usage_rows = []
            for proc in active_procs:
                weight = proc.get("connections_count", 1) / num_sockets
                b_up = int(bytes_sent_delta * weight)
                b_down = int(bytes_recv_delta * weight)
                app_id = self._get_app_id(proc["app_name"], proc["category"])

                usage_rows.append({
                    "session_id": None,
                    "device_id": self._device_id,
                    "app_id": app_id,
                    "ts": now_str,
                    "bytes_up": b_up,
                    "bytes_down": b_down
                })

            if usage_rows:
                try:
                    self.repo.insert_usage_batch(usage_rows)
                except Exception as e:
                    logger.debug("Failed inserting live usage batch: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collector = LiveCollector()
    collector.start(interval_sec=2.0)
    print("Collector running for 6 seconds...")
    time.sleep(6)
    print("Snapshot:", collector.get_latest_stats())
    collector.stop()
    print("Collector stopped.")
