"""
Process and Protocol Mapper for Bandwidth Usage Monitor.
Maps active network sockets to running processes, application categories,
and protocol statistics.
"""

from __future__ import annotations

import logging
from collections import defaultdict
import socket
from typing import Any, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger("process_mapper")

# Mapping keywords in process names to standard applications and categories
KNOWN_APP_MAPPINGS = {
    "chrome": ("Chrome Browser", "browsing"),
    "firefox": ("Firefox", "browsing"),
    "msedgewebview2": ("Microsoft Edge WebView2", "browsing"),
    "msedge": ("Microsoft Edge", "browsing"),
    "brave": ("Brave Browser", "browsing"),
    "slack": ("Slack Messaging", "social"),
    "discord": ("Discord", "VoIP"),
    "zoom": ("Zoom Meetings", "VoIP"),
    "teams": ("Microsoft Teams", "VoIP"),
    "steam": ("Steam Games", "gaming"),
    "epicgames": ("Epic Games", "gaming"),
    "spotify": ("Spotify", "streaming"),
    "vlc": ("VLC media player", "streaming"),
    "netflix": ("Netflix", "streaming"),
    "dropbox": ("Dropbox Backup", "cloud"),
    "googledrive": ("Google Drive", "cloud"),
    "onedrive": ("OneDrive", "cloud"),
    "svchost": ("Service Host", "system"),
    "trustedinstaller": ("Windows Update", "updates"),
    "system": ("System Packages", "updates"),
    "python": ("Python process", "development"),
    "language_server": ("Language Server", "development"),
    "codex": ("Codex Desktop", "productivity"),
    "code": ("Visual Studio Code", "development"),
    "chatgpt": ("ChatGPT", "productivity"),
    "crossdeviceservice": ("Cross-Device Service", "system"),
}

KNOWN_PORTS = {
    80: ("HTTP", "browsing"),
    443: ("HTTPS", "browsing"),
    53: ("DNS", "system"),
    22: ("SSH", "cloud"),
    8080: ("HTTP-Alt", "browsing"),
    8443: ("HTTPS-Alt", "browsing"),
    3478: ("STUN/TURN", "VoIP"),
    5004: ("RTP", "VoIP"),
    27015: ("Steam", "gaming")
}


class ProcessMapper:
    """Discovers local network connections and maps them to named applications."""

    def __init__(self) -> None:
        self.cached_process_names: Dict[int, str] = {}

    def get_process_name(self, pid: int) -> str:
        """Resolve PID to process executable name safely."""
        if pid in self.cached_process_names:
            return self.cached_process_names[pid]
        try:
            p = psutil.Process(pid)
            name = p.name()
            self.cached_process_names[pid] = name
            return name
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return f"PID {pid} (name unavailable)"

    def map_to_app(self, proc_name: str) -> Tuple[str, str]:
        """Map process name to standardized application name and category."""
        proc_lower = proc_name.lower()
        for key, (app_name, category) in KNOWN_APP_MAPPINGS.items():
            if key in proc_lower:
                return app_name, category
        # Keep the executable visible rather than guessing an application.
        return proc_name, "other"

    def scan_active_connections(self) -> List[Dict[str, Any]]:
        """
        Scan active internet connections and group them by process and destination.
        Returns list of active connection metadata dictionaries.
        """
        active_items = []
        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError) as e:
            logger.warning("Access denied scanning net_connections: %s", e)
            connections = []

        seen_pids = defaultdict(lambda: {"count": 0, "remote_ips": set(), "ports": set()})

        for conn in connections:
            if conn.status == psutil.CONN_ESTABLISHED and conn.pid:
                info = seen_pids[conn.pid]
                info["count"] += 1
                if conn.raddr:
                    info["remote_ips"].add(conn.raddr.ip)
                    info["ports"].add(conn.raddr.port)

        for pid, stats in seen_pids.items():
            proc_name = self.get_process_name(pid)
            app_name, category = self.map_to_app(proc_name)
            active_items.append({
                "pid": pid,
                "process_name": proc_name,
                "app_name": app_name,
                "category": category,
                "connections_count": stats["count"],
                "remote_ips": list(stats["remote_ips"]),
                "ports": list(stats["ports"])
            })

        return active_items

    def get_protocol_distribution(self) -> Dict[str, float]:
        """
        Return protocol shares calculated only from observed sockets.
        """
        try:
            connections = psutil.net_connections(kind="inet")
            raw_counts: Dict[str, int] = defaultdict(int)
            for c in connections:
                if c.type == socket.SOCK_STREAM and c.status == psutil.CONN_ESTABLISHED:
                    raw_counts["HTTPS" if c.raddr and c.raddr.port in (443, 8443) else "TCP"] += 1
                elif c.type == socket.SOCK_DGRAM and c.raddr:
                    raw_counts["DNS" if c.raddr.port == 53 else "UDP"] += 1

            total = sum(raw_counts.values())
            if total == 0:
                return {}
            return {k: round(v / total * 100.0, 1) for k, v in raw_counts.items()}
        except (psutil.AccessDenied, PermissionError) as e:
            logger.warning("Access denied scanning protocol distribution: %s", e)
            return {}
