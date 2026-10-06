-- ============================================================================
-- Named Parameterized SQL Queries (SQLite Stored Procedure Equivalents)
-- Loaded and executed via repository.py
-- ============================================================================

-- name: insert_user
INSERT OR IGNORE INTO users (name, role)
VALUES (:name, :role);

-- name: insert_device
INSERT OR IGNORE INTO devices (user_id, hostname, mac, ip, device_type)
VALUES (:user_id, :hostname, :mac, :ip, :device_type);

-- name: insert_application
INSERT OR IGNORE INTO applications (name, category)
VALUES (:name, :category);

-- name: insert_session
INSERT INTO network_sessions (device_id, app_id, start_ts, end_ts)
VALUES (:device_id, :app_id, :start_ts, :end_ts);

-- name: insert_bandwidth_usage
INSERT INTO bandwidth_usage (session_id, device_id, app_id, ts, bytes_up, bytes_down, source)
VALUES (:session_id, :device_id, :app_id, :ts, :bytes_up, :bytes_down, :source);

-- name: insert_network_metric
INSERT INTO network_metrics (ts, latency_ms, jitter_ms, packet_loss_pct, capacity_mbps, utilization_pct, source)
VALUES (:ts, :latency_ms, :jitter_ms, :packet_loss_pct, :capacity_mbps, :utilization_pct, :source);

-- name: insert_alert
INSERT INTO alerts (ts, entity_type, entity_id, severity, reason, value, baseline, acknowledged)
VALUES (:ts, :entity_type, :entity_id, :severity, :reason, :value, :baseline, 0);

-- name: acknowledge_alert
UPDATE alerts
SET acknowledged = 1
WHERE alert_id = :alert_id;

-- name: get_alerts
SELECT 
    a.alert_id,
    a.ts,
    a.entity_type,
    a.entity_id,
    CASE 
        WHEN a.entity_type = 'application' THEN app.name
        WHEN a.entity_type = 'device' THEN dev.hostname
        ELSE 'Network Link'
    END AS entity_name,
    a.severity,
    a.reason,
    a.value,
    a.baseline,
    a.acknowledged
FROM alerts a
LEFT JOIN applications app ON a.entity_type = 'application' AND a.entity_id = app.app_id
LEFT JOIN devices dev ON a.entity_type = 'device' AND a.entity_id = dev.device_id
WHERE (:unacknowledged_only = 0 OR a.acknowledged = 0)
  AND (:severity IS NULL OR a.severity = :severity)
ORDER BY a.ts DESC
LIMIT :limit;

-- name: insert_prediction
INSERT INTO predictions (ts_generated, target_ts, predicted_mbps, actual_mbps, model)
VALUES (:ts_generated, :target_ts, :predicted_mbps, :actual_mbps, :model);

-- name: update_prediction_actual
UPDATE predictions
SET actual_mbps = :actual_mbps
WHERE target_ts = :target_ts AND model = :model;

-- name: insert_anomaly_label
INSERT INTO anomaly_labels (ts, entity_type, entity_id, anomaly_type, severity, description)
VALUES (:ts, :entity_type, :entity_id, :anomaly_type, :severity, :description);

-- name: get_anomaly_labels
SELECT * FROM anomaly_labels
WHERE ts BETWEEN :start_ts AND :end_ts
ORDER BY ts ASC;

-- name: get_setting
SELECT value FROM settings WHERE key = :key;

-- name: set_setting
INSERT INTO settings (key, value)
VALUES (:key, :value)
ON CONFLICT(key) DO UPDATE SET value = excluded.value;

-- name: get_all_settings
SELECT key, value FROM settings;

-- name: get_all_users
SELECT user_id, name, role FROM users ORDER BY name;

-- name: get_all_devices
SELECT d.device_id, d.hostname, d.mac, d.ip, d.device_type, u.user_id, u.name AS user_name
FROM devices d
LEFT JOIN users u ON d.user_id = u.user_id
ORDER BY d.hostname;

-- name: get_all_applications
SELECT app_id, name, category FROM applications ORDER BY name;

-- name: get_recent_metrics
SELECT ts, latency_ms, jitter_ms, packet_loss_pct, capacity_mbps, utilization_pct
FROM network_metrics
WHERE ts >= :since_ts
ORDER BY ts ASC;

-- name: get_recent_live_usage
SELECT 
    b.ts,
    a.name AS app_name,
    a.category,
    d.hostname,
    b.bytes_up,
    b.bytes_down,
    ROUND((b.bytes_up + b.bytes_down) * 8.0 / (1000.0 * 1000.0), 4) AS mbps
FROM bandwidth_usage b
JOIN applications a ON b.app_id = a.app_id
JOIN devices d ON b.device_id = d.device_id
WHERE b.ts >= :since_ts
ORDER BY b.ts DESC
LIMIT :limit;

-- name: get_app_analytics
SELECT 
    a.app_id,
    a.name AS app_name,
    a.category,
    COALESCE(SUM(b.bytes_up), 0) AS total_bytes_up,
    COALESCE(SUM(b.bytes_down), 0) AS total_bytes_down,
    COALESCE(SUM(b.bytes_up + b.bytes_down), 0) AS total_bytes,
    ROUND(COALESCE(SUM(b.bytes_up + b.bytes_down), 0) / (1024.0 * 1024.0 * 1024.0), 4) AS total_gb,
    ROUND(AVG(b.bytes_up + b.bytes_down), 2) AS avg_bytes_per_sample,
    MIN(b.bytes_up + b.bytes_down) AS min_bytes_sample,
    MAX(b.bytes_up + b.bytes_down) AS max_bytes_sample,
    COUNT(b.usage_id) AS sample_count
FROM applications a
LEFT JOIN bandwidth_usage b ON a.app_id = b.app_id AND b.ts BETWEEN :start_ts AND :end_ts
GROUP BY a.app_id, a.name, a.category
ORDER BY total_bytes DESC;

-- name: get_app_timeline
SELECT 
    strftime('%Y-%m-%d %H:00:00', b.ts) AS hour_ts,
    a.name AS app_name,
    SUM(b.bytes_up) AS bytes_up,
    SUM(b.bytes_down) AS bytes_down,
    SUM(b.bytes_up + b.bytes_down) AS total_bytes,
    ROUND(SUM(b.bytes_up + b.bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS mbps
FROM bandwidth_usage b
JOIN applications a ON b.app_id = a.app_id
WHERE b.ts BETWEEN :start_ts AND :end_ts
  AND (:app_id IS NULL OR b.app_id = :app_id)
GROUP BY hour_ts, a.name
ORDER BY hour_ts ASC;

-- name: get_device_analytics
SELECT 
    d.device_id,
    d.hostname,
    d.ip,
    d.device_type,
    u.user_id,
    COALESCE(u.name, 'Unassigned') AS user_name,
    COALESCE(u.role, 'none') AS user_role,
    COALESCE(SUM(b.bytes_up), 0) AS total_bytes_up,
    COALESCE(SUM(b.bytes_down), 0) AS total_bytes_down,
    COALESCE(SUM(b.bytes_up + b.bytes_down), 0) AS total_bytes,
    ROUND(COALESCE(SUM(b.bytes_up + b.bytes_down), 0) / (1024.0 * 1024.0 * 1024.0), 4) AS total_gb,
    ROUND(AVG(b.bytes_up + b.bytes_down), 2) AS avg_bytes_per_sample
FROM devices d
LEFT JOIN users u ON d.user_id = u.user_id
LEFT JOIN bandwidth_usage b ON d.device_id = b.device_id AND b.ts BETWEEN :start_ts AND :end_ts
GROUP BY d.device_id, d.hostname, d.ip, d.device_type, u.user_id, u.name, u.role
ORDER BY total_bytes DESC;

-- name: get_device_timeline
SELECT 
    strftime('%Y-%m-%d %H:00:00', b.ts) AS hour_ts,
    d.hostname,
    SUM(b.bytes_up + b.bytes_down) AS total_bytes,
    ROUND(SUM(b.bytes_up + b.bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS mbps
FROM bandwidth_usage b
JOIN devices d ON b.device_id = d.device_id
WHERE b.ts BETWEEN :start_ts AND :end_ts
GROUP BY hour_ts, d.hostname
ORDER BY hour_ts ASC;

-- name: get_hourly_usage
SELECT 
    strftime('%Y-%m-%d %H:00:00', ts) AS hour_bucket,
    strftime('%H', ts) AS hour_of_day,
    strftime('%w', ts) AS day_of_week,
    SUM(bytes_up) AS total_bytes_up,
    SUM(bytes_down) AS total_bytes_down,
    SUM(bytes_up + bytes_down) AS total_bytes,
    ROUND(SUM(bytes_up + bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS mbps
FROM bandwidth_usage
WHERE ts BETWEEN :start_ts AND :end_ts
GROUP BY hour_bucket
ORDER BY hour_bucket ASC;

-- name: get_daily_usage
SELECT 
    strftime('%Y-%m-%d', ts) AS date_bucket,
    strftime('%w', ts) AS day_of_week,
    SUM(bytes_up) AS total_bytes_up,
    SUM(bytes_down) AS total_bytes_down,
    SUM(bytes_up + bytes_down) AS total_bytes,
    ROUND(SUM(bytes_up + bytes_down) / (1024.0 * 1024.0 * 1024.0), 4) AS total_gb,
    ROUND(SUM(bytes_up + bytes_down) * 8.0 / (86400.0 * 1000.0 * 1000.0), 4) AS avg_mbps
FROM bandwidth_usage
WHERE ts BETWEEN :start_ts AND :end_ts
GROUP BY date_bucket
ORDER BY date_bucket ASC;

-- name: get_hour_by_weekday_heatmap
SELECT 
    CAST(strftime('%w', ts) AS INTEGER) AS day_of_week, -- 0=Sunday..6=Saturday
    CAST(strftime('%H', ts) AS INTEGER) AS hour_of_day,
    ROUND(AVG(bytes_up + bytes_down) * 8.0 / (1000.0 * 1000.0), 4) AS avg_mbps,
    SUM(bytes_up + bytes_down) AS total_bytes
FROM bandwidth_usage
WHERE ts BETWEEN :start_ts AND :end_ts
GROUP BY day_of_week, hour_of_day
ORDER BY day_of_week ASC, hour_of_day ASC;

-- name: get_peak_offpeak_stats
SELECT 
    CASE 
        WHEN CAST(strftime('%H', ts) AS INTEGER) BETWEEN 9 AND 17 THEN 'Business Hours (09-17)'
        WHEN CAST(strftime('%H', ts) AS INTEGER) BETWEEN 19 AND 23 THEN 'Evening Peak (19-23)'
        ELSE 'Off-Peak'
    END AS period_type,
    COUNT(*) AS sample_count,
    SUM(bytes_up) AS total_bytes_up,
    SUM(bytes_down) AS total_bytes_down,
    SUM(bytes_up + bytes_down) AS total_bytes,
    ROUND(AVG(bytes_up + bytes_down) * 8.0 / (1000.0 * 1000.0), 4) AS avg_mbps
FROM bandwidth_usage
WHERE ts BETWEEN :start_ts AND :end_ts
GROUP BY period_type;

-- name: get_updown_summary
SELECT 
    SUM(bytes_up) AS total_bytes_up,
    SUM(bytes_down) AS total_bytes_down,
    SUM(bytes_up + bytes_down) AS total_bytes,
    ROUND(CAST(SUM(bytes_up) AS REAL) / NULLIF(SUM(bytes_down), 0), 4) AS overall_updown_ratio
FROM bandwidth_usage
WHERE ts BETWEEN :start_ts AND :end_ts;

-- name: get_updown_by_category
SELECT 
    a.category,
    SUM(b.bytes_up) AS bytes_up,
    SUM(b.bytes_down) AS bytes_down,
    SUM(b.bytes_up + b.bytes_down) AS total_bytes,
    ROUND(CAST(SUM(b.bytes_up) AS REAL) / NULLIF(SUM(b.bytes_down), 0), 4) AS ratio
FROM bandwidth_usage b
JOIN applications a ON b.app_id = a.app_id
WHERE b.ts BETWEEN :start_ts AND :end_ts
GROUP BY a.category
ORDER BY total_bytes DESC;

-- name: get_top_apps_in_window
SELECT 
    a.app_id,
    a.name AS app_name,
    a.category,
    SUM(b.bytes_up + b.bytes_down) AS total_bytes,
    ROUND(SUM(b.bytes_up + b.bytes_down) / (1024.0 * 1024.0 * 1024.0), 4) AS total_gb
FROM bandwidth_usage b
JOIN applications a ON b.app_id = a.app_id
WHERE b.ts BETWEEN :start_ts AND :end_ts
GROUP BY a.app_id, a.name, a.category
ORDER BY total_bytes DESC
LIMIT :limit;

-- name: get_top_devices_in_window
SELECT 
    d.device_id,
    d.hostname,
    d.device_type,
    SUM(b.bytes_up + b.bytes_down) AS total_bytes,
    ROUND(SUM(b.bytes_up + b.bytes_down) / (1024.0 * 1024.0 * 1024.0), 4) AS total_gb
FROM bandwidth_usage b
JOIN devices d ON b.device_id = d.device_id
WHERE b.ts BETWEEN :start_ts AND :end_ts
GROUP BY d.device_id, d.hostname, d.device_type
ORDER BY total_bytes DESC
LIMIT :limit;

-- name: get_congestion_metrics
SELECT 
    m.ts,
    m.latency_ms,
    m.jitter_ms,
    m.packet_loss_pct,
    m.capacity_mbps,
    m.utilization_pct,
    CASE 
        WHEN m.utilization_pct >= :threshold_util OR m.latency_ms >= :threshold_latency OR m.packet_loss_pct >= :threshold_loss
        THEN 1 ELSE 0 
    END AS is_congested
FROM network_metrics m
WHERE m.ts BETWEEN :start_ts AND :end_ts
ORDER BY m.ts ASC;

-- name: get_congested_interval_offenders
SELECT 
    a.name AS app_name,
    a.category,
    d.hostname,
    SUM(b.bytes_up + b.bytes_down) AS total_bytes,
    ROUND(SUM(b.bytes_up + b.bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS avg_mbps
FROM bandwidth_usage b
JOIN applications a ON b.app_id = a.app_id
JOIN devices d ON b.device_id = d.device_id
WHERE b.ts BETWEEN :start_ts AND :end_ts
GROUP BY a.name, a.category, d.hostname
ORDER BY total_bytes DESC
LIMIT :limit;

-- name: archive_retention_aggregates
INSERT INTO hourly_aggregates (hour_ts, app_id, device_id, bytes_up, bytes_down, sample_count)
SELECT 
    strftime('%Y-%m-%d %H:00:00', ts) AS hour_ts,
    app_id,
    device_id,
    SUM(bytes_up) AS bytes_up,
    SUM(bytes_down) AS bytes_down,
    COUNT(*) AS sample_count
FROM bandwidth_usage
WHERE ts < :cutoff_ts
GROUP BY hour_ts, app_id, device_id;

-- name: prune_raw_usage
DELETE FROM bandwidth_usage
WHERE ts < :cutoff_ts;

-- name: get_month_to_date_device_usage
SELECT 
    d.device_id,
    d.hostname,
    d.device_type,
    COALESCE(u.name, 'Unassigned') AS user_name,
    COALESCE(SUM(b.bytes_up + b.bytes_down), 0) AS total_bytes,
    ROUND(COALESCE(SUM(b.bytes_up + b.bytes_down), 0) / (1024.0 * 1024.0 * 1024.0), 4) AS used_gb
FROM devices d
LEFT JOIN users u ON d.user_id = u.user_id
LEFT JOIN bandwidth_usage b ON d.device_id = b.device_id 
    AND b.ts >= strftime('%Y-%m-01 00:00:00', :reference_ts)
    AND b.ts <= :reference_ts
GROUP BY d.device_id, d.hostname, d.device_type, u.name;

-- name: insert_speed_test
INSERT INTO speed_tests (ts, download_mbps, upload_mbps, ping_ms, server)
VALUES (:ts, :download_mbps, :upload_mbps, :ping_ms, :server);

-- name: get_speed_tests
SELECT speed_id, ts, download_mbps, upload_mbps, ping_ms, server
FROM speed_tests
ORDER BY ts DESC
LIMIT :limit;

