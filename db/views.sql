-- ============================================================================
-- Bandwidth Usage Monitor & Analyzer - Analytical Views
-- ============================================================================

-- 1. v_app_summary: Summary of bandwidth usage across all applications
CREATE VIEW IF NOT EXISTS v_app_summary AS
SELECT 
    a.app_id,
    a.name AS app_name,
    a.category,
    COALESCE(SUM(b.bytes_up), 0) AS total_bytes_up,
    COALESCE(SUM(b.bytes_down), 0) AS total_bytes_down,
    COALESCE(SUM(b.bytes_up + b.bytes_down), 0) AS total_bytes,
    ROUND(COALESCE(SUM(b.bytes_up + b.bytes_down), 0) / (1024.0 * 1024.0 * 1024.0), 4) AS total_gb,
    COUNT(b.usage_id) AS sample_count,
    MIN(b.ts) AS first_seen,
    MAX(b.ts) AS last_seen
FROM applications a
LEFT JOIN bandwidth_usage b ON a.app_id = b.app_id
GROUP BY a.app_id, a.name, a.category;

-- 2. v_device_summary: Summary of bandwidth consumption by device and associated user
CREATE VIEW IF NOT EXISTS v_device_summary AS
SELECT 
    d.device_id,
    d.hostname,
    d.ip,
    d.mac,
    d.device_type,
    u.user_id,
    COALESCE(u.name, 'Unassigned') AS user_name,
    COALESCE(u.role, 'none') AS user_role,
    COALESCE(SUM(b.bytes_up), 0) AS total_bytes_up,
    COALESCE(SUM(b.bytes_down), 0) AS total_bytes_down,
    COALESCE(SUM(b.bytes_up + b.bytes_down), 0) AS total_bytes,
    ROUND(COALESCE(SUM(b.bytes_up + b.bytes_down), 0) / (1024.0 * 1024.0 * 1024.0), 4) AS total_gb
FROM devices d
LEFT JOIN users u ON d.user_id = u.user_id
LEFT JOIN bandwidth_usage b ON d.device_id = b.device_id
GROUP BY d.device_id, d.hostname, d.ip, d.mac, d.device_type, u.user_id, u.name, u.role;

-- 3. v_hourly: Aggregated usage by hour
CREATE VIEW IF NOT EXISTS v_hourly AS
SELECT 
    strftime('%Y-%m-%d %H:00:00', ts) AS hour_bucket,
    strftime('%H', ts) AS hour_of_day,
    strftime('%w', ts) AS day_of_week, -- 0=Sunday, 6=Saturday
    SUM(bytes_up) AS total_bytes_up,
    SUM(bytes_down) AS total_bytes_down,
    SUM(bytes_up + bytes_down) AS total_bytes,
    ROUND(SUM(bytes_up + bytes_down) * 8.0 / (3600.0 * 1000.0 * 1000.0), 4) AS avg_mbps
FROM bandwidth_usage
GROUP BY strftime('%Y-%m-%d %H:00:00', ts);

-- 4. v_daily: Aggregated usage by day
CREATE VIEW IF NOT EXISTS v_daily AS
SELECT 
    strftime('%Y-%m-%d', ts) AS date_bucket,
    strftime('%w', ts) AS day_of_week,
    SUM(bytes_up) AS total_bytes_up,
    SUM(bytes_down) AS total_bytes_down,
    SUM(bytes_up + bytes_down) AS total_bytes,
    ROUND(SUM(bytes_up + bytes_down) / (1024.0 * 1024.0 * 1024.0), 4) AS total_gb,
    ROUND(SUM(bytes_up + bytes_down) * 8.0 / (86400.0 * 1000.0 * 1000.0), 4) AS avg_mbps
FROM bandwidth_usage
GROUP BY strftime('%Y-%m-%d', ts);

-- 5. v_weekday_weekend: Comparison between weekdays and weekends
CREATE VIEW IF NOT EXISTS v_weekday_weekend AS
SELECT 
    CASE 
        WHEN strftime('%w', ts) IN ('0', '6') THEN 'Weekend'
        ELSE 'Weekday'
    END AS day_type,
    strftime('%H', ts) AS hour_of_day,
    ROUND(AVG(bytes_up), 2) AS avg_bytes_up,
    ROUND(AVG(bytes_down), 2) AS avg_bytes_down,
    ROUND(AVG(bytes_up + bytes_down), 2) AS avg_total_bytes,
    SUM(bytes_up + bytes_down) AS total_bytes
FROM bandwidth_usage
GROUP BY day_type, hour_of_day;

-- 6. v_updown_ratio: Upload vs Download ratio and traffic characterization
CREATE VIEW IF NOT EXISTS v_updown_ratio AS
SELECT 
    a.app_id,
    a.name AS app_name,
    a.category,
    COALESCE(SUM(b.bytes_up), 0) AS bytes_up,
    COALESCE(SUM(b.bytes_down), 0) AS bytes_down,
    CASE 
        WHEN COALESCE(SUM(b.bytes_down), 0) = 0 THEN 999.0
        ELSE ROUND(CAST(SUM(b.bytes_up) AS REAL) / SUM(b.bytes_down), 4)
    END AS up_down_ratio,
    CASE
        WHEN CAST(SUM(b.bytes_up) AS REAL) / NULLIF(SUM(b.bytes_down), 0) > 1.5 THEN 'Upload Heavy'
        WHEN CAST(SUM(b.bytes_down) AS REAL) / NULLIF(SUM(b.bytes_up), 0) > 2.5 THEN 'Download Heavy'
        ELSE 'Balanced'
    END AS traffic_character
FROM applications a
JOIN bandwidth_usage b ON a.app_id = b.app_id
GROUP BY a.app_id, a.name, a.category;

-- 7. v_top_consumers: Overall ranking of top consumers across apps and devices
CREATE VIEW IF NOT EXISTS v_top_consumers AS
SELECT 
    'application' AS entity_type,
    a.app_id AS entity_id,
    a.name AS entity_name,
    SUM(b.bytes_up + b.bytes_down) AS total_bytes,
    SUM(b.bytes_up) AS bytes_up,
    SUM(b.bytes_down) AS bytes_down,
    ROUND(SUM(b.bytes_up + b.bytes_down) / (1024.0 * 1024.0 * 1024.0), 3) AS total_gb
FROM applications a
JOIN bandwidth_usage b ON a.app_id = b.app_id
GROUP BY a.app_id, a.name
UNION ALL
SELECT 
    'device' AS entity_type,
    d.device_id AS entity_id,
    d.hostname AS entity_name,
    SUM(b.bytes_up + b.bytes_down) AS total_bytes,
    SUM(b.bytes_up) AS bytes_up,
    SUM(b.bytes_down) AS bytes_down,
    ROUND(SUM(b.bytes_up + b.bytes_down) / (1024.0 * 1024.0 * 1024.0), 3) AS total_gb
FROM devices d
JOIN bandwidth_usage b ON d.device_id = b.device_id
GROUP BY d.device_id, d.hostname;
