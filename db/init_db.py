"""
Database initialization script for Bandwidth Usage Monitor and Analyzer.
Creates schema, views, default settings, and seeds initial entities.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_db")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "bandwidth.db"
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"
VIEWS_PATH = BASE_DIR / "db" / "views.sql"

DEFAULT_SETTINGS = {
    "capacity_mbps": "25.0",
    "congestion_util_threshold": "80.0",
    "latency_alert_threshold": "60.0",
    "packet_loss_threshold": "3.0",
    "anomaly_z_threshold": "2.5",
    "ping_host": "8.8.8.8",
    "collector_interval_sec": "2",
    "scapy_enabled": "0",
    "theme_mode": "light",
    "quiet_hours_enabled": "0",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
    "desktop_notifications": "0",
    "data_source": "simulated",
    "monthly_device_budget_gb": "50.0",
    "auto_start_collector": "0",
    "speedtest_auto_interval_min": "0"
}

SEED_USERS = [
    ("Alice Morgan", "admin"),
    ("Bob Chen", "developer"),
    ("Clara Oswald", "designer"),
    ("David Kim", "manager"),
    ("Emma Watson", "guest"),
]

SEED_APPLICATIONS = [
    ("YouTube", "streaming"),
    ("Netflix", "streaming"),
    ("Chrome Browser", "browsing"),
    ("Firefox", "browsing"),
    ("Steam Games", "gaming"),
    ("Discord", "VoIP"),
    ("Zoom Meetings", "VoIP"),
    ("Google Drive", "cloud"),
    ("Dropbox Backup", "cloud"),
    ("Windows Update", "updates"),
    ("System Packages", "updates"),
    ("Slack Messaging", "social"),
]

SEED_DEVICES = [
    (1, "Alice-MacBook", "00:1A:2B:3C:4D:01", "192.168.1.101", "laptop"),
    (2, "Bob-DevStation", "00:1A:2B:3C:4D:02", "192.168.1.102", "workstation"),
    (3, "Clara-iMac", "00:1A:2B:3C:4D:03", "192.168.1.103", "workstation"),
    (4, "David-ThinkPad", "00:1A:2B:3C:4D:04", "192.168.1.104", "laptop"),
    (5, "Emma-iPhone", "00:1A:2B:3C:4D:05", "192.168.1.105", "mobile"),
    (1, "Office-Server", "00:1A:2B:3C:4D:06", "192.168.1.10", "server"),
    (2, "Lab-Tablet", "00:1A:2B:3C:4D:07", "192.168.1.107", "tablet"),
    (5, "Smart-TV", "00:1A:2B:3C:4D:08", "192.168.1.108", "iot"),
]


def init_database(db_file: Path = DB_PATH) -> None:
    """Initialize database tables, views, settings, and seed records."""
    db_file.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Initializing database at: %s", db_file)

    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")

        # 0. Check and migrate existing tables before indices are applied
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bandwidth_usage';")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(bandwidth_usage);")
            bu_cols = [c[1] for c in cursor.fetchall()]
            if "source" not in bu_cols:
                logger.info("Migrating bandwidth_usage: adding source column...")
                cursor.execute("ALTER TABLE bandwidth_usage ADD COLUMN source TEXT NOT NULL DEFAULT 'simulated';")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='network_metrics';")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(network_metrics);")
            nm_cols = [c[1] for c in cursor.fetchall()]
            if "source" not in nm_cols:
                logger.info("Migrating network_metrics: adding source column...")
                cursor.execute("ALTER TABLE network_metrics ADD COLUMN source TEXT NOT NULL DEFAULT 'simulated';")
        conn.commit()

        # 1. Schema
        logger.info("Applying schema.sql...")
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)

        # 2. Views
        logger.info("Applying views.sql...")
        views_sql = VIEWS_PATH.read_text(encoding="utf-8")
        conn.executescript(views_sql)

        # 3. Default Settings
        logger.info("Configuring default settings...")
        cursor = conn.cursor()
        for k, v in DEFAULT_SETTINGS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                (k, v)
            )

        # 4. Seed Users
        cursor.execute("SELECT COUNT(*) FROM users;")
        if cursor.fetchone()[0] == 0:
            logger.info("Seeding users...")
            cursor.executemany("INSERT INTO users (name, role) VALUES (?, ?);", SEED_USERS)

        # 5. Seed Applications
        cursor.execute("SELECT COUNT(*) FROM applications;")
        if cursor.fetchone()[0] == 0:
            logger.info("Seeding applications...")
            cursor.executemany("INSERT INTO applications (name, category) VALUES (?, ?);", SEED_APPLICATIONS)

        # 6. Seed Devices
        cursor.execute("SELECT COUNT(*) FROM devices;")
        if cursor.fetchone()[0] == 0:
            logger.info("Seeding devices...")
            cursor.executemany(
                "INSERT INTO devices (user_id, hostname, mac, ip, device_type) VALUES (?, ?, ?, ?, ?);",
                SEED_DEVICES
            )

        conn.commit()
        logger.info("Database initialized successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
