from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pandas as pd

from collector.live_collector import LiveCollector


class FakeRepo:
    db_path = "unused-test-db"

    def __init__(self):
        self.usage = []

    def get_setting(self, key, default=None):
        return {"ping_host": "127.0.0.1", "capacity_mbps": "100.0"}.get(key, default)

    def get_applications(self):
        return pd.DataFrame(columns=["app_id", "name"])

    def get_devices(self):
        return pd.DataFrame([{"device_id": 1}])

    def insert_application(self, name, category):
        return 7

    def insert_usage_batch(self, rows):
        self.usage.extend(rows)

    def insert_network_metric(self, **kwargs):
        pass


def test_existing_live_collector_continues_persisting_and_publishing_deltas(monkeypatch):
    repo = FakeRepo()
    sent = []
    collector = LiveCollector(repo, sample_callback=sent.append)
    monkeypatch.setattr(collector.ping_probe, "probe", lambda count=2: {"latency_ms": 1.0, "jitter_ms": 0.0, "packet_loss_pct": 0.0})
    calls = iter(range(1000))
    def counters(pernic=False):
        assert pernic is True
        value = next(calls)
        return {"Ethernet": SimpleNamespace(bytes_sent=value * 100, bytes_recv=value * 200)}
    monkeypatch.setattr("collector.live_collector.psutil.net_io_counters", counters)

    thread = threading.Thread(target=collector._collect_loop, args=(0.005,), daemon=True)
    thread.start()
    time.sleep(0.04)
    collector._stop_event.set()
    thread.join(timeout=1)

    assert repo.usage
    assert sent
    assert sent[0]["bytes_up"] > 0
    assert sent[0]["bytes_down"] > 0
    assert sent[0]["ts"] == repo.usage[0]["ts"]
