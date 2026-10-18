-- ============================================================================
-- Bandwidth Usage Monitor & Analyzer - Database Schema (SQLite)
-- ============================================================================

PRAGMA foreign_keys = ON;

-- 1. Users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'developer', 'designer', 'manager', 'guest', 'system'))
);

-- 2. Devices
CREATE TABLE IF NOT EXISTS devices (
    device_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    hostname TEXT NOT NULL,
    mac TEXT UNIQUE NOT NULL,
    ip TEXT NOT NULL,
    device_type TEXT NOT NULL CHECK(device_type IN ('workstation', 'laptop', 'mobile', 'server', 'iot', 'tablet')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- 3. Applications
CREATE TABLE IF NOT EXISTS applications (
    app_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('streaming', 'browsing', 'gaming', 'cloud', 'VoIP', 'updates', 'social', 'system', 'other'))
);

-- 4. Network Sessions
CREATE TABLE IF NOT EXISTS network_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    app_id INTEGER NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (app_id) REFERENCES applications(app_id) ON DELETE CASCADE
);

-- 5. Bandwidth Usage (Fine-grained usage samples)
CREATE TABLE IF NOT EXISTS bandwidth_usage (
    usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    device_id INTEGER NOT NULL,
    app_id INTEGER NOT NULL,
    ts TEXT NOT NULL, -- ISO-8601 YYYY-MM-DD HH:MM:SS
    bytes_up INTEGER NOT NULL DEFAULT 0,
    bytes_down INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES network_sessions(session_id) ON DELETE SET NULL,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (app_id) REFERENCES applications(app_id) ON DELETE CASCADE
);

-- 6. Network Metrics (Ping telemetry & link health)
CREATE TABLE IF NOT EXISTS network_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL, -- ISO-8601 YYYY-MM-DD HH:MM:SS
    latency_ms REAL NOT NULL DEFAULT 0.0,
    jitter_ms REAL NOT NULL DEFAULT 0.0,
    packet_loss_pct REAL NOT NULL DEFAULT 0.0,
    capacity_mbps REAL NOT NULL DEFAULT 100.0,
    utilization_pct REAL NOT NULL DEFAULT 0.0
);

-- 7. Alerts
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('application', 'device', 'network', 'system')),
    entity_id INTEGER,
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warn', 'critical')),
    reason TEXT NOT NULL,
    value REAL NOT NULL,
    baseline REAL NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0 CHECK(acknowledged IN (0, 1))
);

-- 8. Predictions
CREATE TABLE IF NOT EXISTS predictions (
    pred_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_generated TEXT NOT NULL,
    target_ts TEXT NOT NULL,
    predicted_mbps REAL NOT NULL,
    actual_mbps REAL,
    model TEXT NOT NULL
);

-- 9. Settings (Key/Value store for configurable parameters)
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 10. Ground Truth Labels (For ML simulator evaluation)
CREATE TABLE IF NOT EXISTS anomaly_labels (
    label_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT NOT NULL
);

-- 11. Hourly Aggregates (For rolling 30-day retention archiving)
CREATE TABLE IF NOT EXISTS hourly_aggregates (
    agg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hour_ts TEXT NOT NULL,
    app_id INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    bytes_up INTEGER NOT NULL,
    bytes_down INTEGER NOT NULL,
    sample_count INTEGER NOT NULL,
    FOREIGN KEY (app_id) REFERENCES applications(app_id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
);

-- Indexes for performance on time-series queries
CREATE INDEX IF NOT EXISTS idx_bandwidth_usage_ts ON bandwidth_usage(ts);
CREATE INDEX IF NOT EXISTS idx_bandwidth_usage_app_ts ON bandwidth_usage(app_id, ts);
CREATE INDEX IF NOT EXISTS idx_bandwidth_usage_dev_ts ON bandwidth_usage(device_id, ts);
CREATE INDEX IF NOT EXISTS idx_network_metrics_ts ON network_metrics(ts);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);
CREATE INDEX IF NOT EXISTS idx_predictions_target ON predictions(target_ts);
CREATE INDEX IF NOT EXISTS idx_anomaly_labels_ts ON anomaly_labels(ts);
CREATE INDEX IF NOT EXISTS idx_hourly_agg_ts ON hourly_aggregates(hour_ts);
