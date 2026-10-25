# Bandwidth Usage Monitor & Analyzer

An enterprise-grade, full-stack network telemetry monitor, analytics platform, and machine learning intelligence system. Built with Python 3.11+, SQLite, Pandas, Scikit-Learn, Statsmodels, Plotly, and Streamlit.

Strictly styled with an editorial, calm, warm palette with **Zero Blue Anywhere** (Terracotta `#C8553D`, Amber `#E0A458`, Sage `#7A9E7E`, Stone `#B8B2A7`, Alert Red `#A63D40`, Background `#FAF7F2`, Surface `#FFFFFF`, Text `#2B2B2B`, and Charcoal Dark Mode `#1C1B1A`).

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph Data Sources
        LC[live_collector.py<br/>psutil net_io_counters]
        PM[process_mapper.py<br/>PID & Process attribution]
        PP[ping_probe.py<br/>Latency / Jitter / Loss ICMP]
        SC[scapy_probe.py (Optional)<br/>Port/IP packet sniffing]
        SIM[simulator.py<br/>90-day seasonal synthesis & labelled anomalies]
    end

    subgraph Storage Layer [SQLite data/bandwidth.db]
        DB[(Relational Tables: users, devices, apps,<br/>sessions, bandwidth_usage, network_metrics,<br/>alerts, predictions, settings, anomaly_labels)]
        VIEWS[Views: v_app_summary, v_device_summary,<br/>v_hourly, v_daily, v_weekday_weekend,<br/>v_updown_ratio, v_top_consumers]
        QUERIES[queries.sql & repository.py<br/>Parameterized Named Queries + 30-Day Retention Job]
    end

    subgraph Analytics & ML Engines
        ANALYTICS[analytics/<br/>App, Device, Time, UpDown, Ranking]
        ML[ml/<br/>Anomaly Detection: Z-Score, IQR, Isolation Forest<br/>Demand Forecasting: Holt-Winters, GBDT Lags<br/>Congestion Modeling & Correlation Matrix<br/>Composite Efficiency Score 0-100]
    end

    subgraph Streamlit UI [12 Pages & Custom Theme]
        APP[app.py Executive Dashboard]
        PAGES[pages/ 1_Live to 12_Settings<br/>Replay Mode, What-If Planner, Budgets, PDF/HTML Reports]
        THEME[.streamlit/config.toml & ui/theme.py<br/>Custom Warm Palette - Zero Blue]
    end

    LC --> DB
    PM --> DB
    PP --> DB
    SC --> DB
    SIM --> DB
    DB --> VIEWS
    DB --> QUERIES
    QUERIES --> ANALYTICS
    QUERIES --> ML
    ANALYTICS --> APP
    ANALYTICS --> PAGES
    ML --> APP
    ML --> PAGES
```

---

## Key Features

1. **Live Network Telemetry (`pages/1_Live.py`)**
   - Live socket sampling via `psutil.net_io_counters(pernic=True)` every 2 seconds.
   - Process attribution mapping local ports to PIDs and application names (`Chrome`, `Discord`, `Steam`, etc.).
   - ICMP ping probe tracking round-trip latency, jitter, and packet loss.
   - Protocol breakdown (HTTPS / TCP / UDP / DNS) and active remote IP endpoints.

2. **Application Analytics (`pages/2_Applications.py`)**
   - High-cardinality ranking of top and lowest consumers.
   - Min/avg/max byte distributions and percentage contribution.
   - Category breakdowns (Streaming, Browsing, Gaming, Cloud, VoIP, Updates, Social).
   - Time-series timeline per application.

3. **Devices & Users (`pages/3_Devices_Users.py`)**
   - Device inventory and user-level rollup.
   - Cross-device comparative statistics.
   - Statistical outlier detection: Z-score spikes of device volume vs its own historical mean/std.

4. **Temporal Patterns (`pages/4_Time.py`)**
   - Hourly, daily, weekly, and monthly aggregations.
   - Peak schedule breakdown (Business Hours 09:00-17:00, Evening Peak 19:00-23:00, Off-Peak).
   - Diurnal curves comparing Weekday vs Weekend.
   - Hour-by-weekday intensity heatmap (00:00 - 23:00) using custom warm amber/terracotta gradients.

5. **Upload vs Download Dynamics (`pages/5_UpDown.py`)**
   - Total volume and bidirectional ratio.
   - Asymmetry categorization: Upload-Heavy, Download-Heavy, and Balanced.
   - Bidirectional stacked area timeline.

6. **Leaderboards & Shifts (`pages/6_Rankings.py`)**
   - Top 5 and Top 10 leaderboards for applications and devices.
   - Period-over-period rank tracking with delta arrows: `↑ +2`, `↓ -1`, `↔ 0`, or `NEW`.
   - Account-based friend leaderboard with one-way friend-code relationships and actual collector-reported upload/download usage.

7. **Multi-Method Anomaly Detection (`pages/7_Anomalies.py`)**
   - Three independent algorithms:
     1. Seasonal Rolling Z-Score (conditioned on hour and day-of-week).
     2. Interquartile Range (IQR) Non-Parametric Fences.
     3. Scikit-learn `IsolationForest` on multi-dimensional telemetry features.
   - Severity classification: `info`, `warn`, `critical`.
   - Alert inbox with one-click acknowledgement.
   - Benchmark evaluation against synthetic ground-truth (Precision, Recall, F1).

8. **Demand Forecasting & Capacity Planning (`pages/8_Forecast.py`)**
   - Autoregressive time-series forecasting: Seasonal Naive vs Holt-Winters vs Gradient Boosting with lag features ($t-1, t-2, t-24$).
   - Strict time-based walk-forward split (Zero data leakage).
   - MAE, RMSE, and MAPE error metrics.
   - Next 24-hour forecast with 95% confidence intervals against link capacity.

9. **Congestion & What-If Planner (`pages/9_Congestion.py`)**
   - Bottleneck saturation incident detection (>80% utilization).
   - Multivariate Pearson correlation matrix: Utilization % vs Latency vs Jitter vs Packet Loss.
   - Top consumer attribution during congested windows.
   - **What-If Capacity Planner**: Interactive sliders to simulate adding active users and upgrading link capacity to calculate congestion relief percentage.

10. **Efficiency Score & Optimization Advisor (`pages/10_Efficiency.py`)**
    - Composite efficiency score ($0 - 100$) combining 5 operational pillars:
      - Useful Throughput Share (25%)
      - Peak-to-Average Ratio Smoothness (25%)
      - Off-Peak Shifting Potential (20%)
      - Bidirectional Balance Health (15%)
      - Packet Loss & Jitter Quality (15%)
    - Ratings: `Efficient` ($\ge 70$), `Moderate` ($40 - 69$), `Inefficient` ($< 40$).
    - Ranked action items with projected monthly GB savings.

11. **Reports & Traffic Replay (`pages/11_Reports.py`)**
    - One-click exportable weekly audit report in standalone HTML and downloadable PDF (`reportlab`).
    - **Replay Mode**: Interactive time slider scrubbing through past 90 days to inspect point-in-time network conditions.

12. **Settings, Budgets & Retention (`pages/12_Settings.py`)**
    - Alert rules, quiet hours (suppress non-critical notifications), and desktop system notifications (`plyer`).
    - Monthly endpoint data quota budgets with projected month-end overrun warnings.
    - Automated 30-day retention job rolling raw samples into `hourly_aggregates`.

---

## SQLite Database Architecture

SQLite does not support stored procedures. To maintain database logic modularity, zero SQL injection, and rapid maintainability:
- Named parameterized SQL queries are defined in [`db/queries.sql`](file:///db/queries.sql) using `-- name: <query_name>` markers.
- Python data access is wrapped by [`db/repository.py`](file:///db/repository.py) using `DatabaseRepository`.
- Foreign key constraints (`PRAGMA foreign_keys = ON;`) and WAL journal mode (`PRAGMA journal_mode = WAL;`) are enforced.
- Relational tables:
  - `users`: User profiles and roles (`admin`, `developer`, `designer`, etc.).
  - `devices`: Endpoints with MAC, IP, and user assignments.
  - `applications`: Catalogs with category classifications.
  - `network_sessions`: Connection sessions per device and application.
  - `bandwidth_usage`: Fine-grained traffic records (`bytes_up`, `bytes_down`).
  - `network_metrics`: ICMP telemetry (`latency_ms`, `jitter_ms`, `packet_loss_pct`, `capacity_mbps`, `utilization_pct`).
  - `alerts`: Anomaly alerts with severities and acknowledgement states.
  - `predictions`: Logged forecasts vs actual throughput.
  - `settings`: Key-value application configuration store.
  - `anomaly_labels`: Ground-truth labels for synthetic anomalies.
  - `hourly_aggregates`: Target table for the 30-day retention cleanup job.

---

## Quick Start & Verification

### 1. Prerequisites
- Python 3.11+
- Virtual environment (recommended)

### 2. Installation & Setup
```bash
# Clone and enter directory
cd bandwidth-analyzer

# Create virtual environment (optional)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install pinned dependencies
pip install -r requirements.txt

# Initialize database schema and views
python db/init_db.py

# Generate 90 days of realistic seasonal telemetry and labelled anomalies
python collector/simulator.py --days 90
```

### 3. Launching the Application
```bash
streamlit run app.py
```
The application will open automatically at **`http://localhost:8501`**.

Alternatively, on Windows run `run.bat` or on Linux/macOS run `./run.sh`.

### Accounts, Friends, and Real Usage Sharing

Create an account through the Sign Up tab. In **Rankings → Devices & Friends**, copy your friend code and enter a friend's code to follow them. The relationship is directional: each person must add the other person's code to see both sides. A friend code only discovers an account; it does not authorize access to metrics. Passwords are stored as salted scrypt hashes.

The account, friend, and aggregate usage tables are added safely to the existing `data/bandwidth.db`; existing telemetry tables and files are retained. The ingestion API exposes no traffic-reading endpoint. It accepts usage samples only with a separate, revocable collector token.

To run the shared backend locally for development, use two terminals in the project directory:

```powershell
python backend_api.py
```

```powershell
python -m streamlit run app.py
```

### 4. Running the Test Suite
```bash
pytest tests/ -v
```
The focused account-ranking tests can be run with `pytest tests/test_live_collector_callback.py tests/test_account_friend_ranking.py -v`.

---

## Research Notebook

Located in [`research/research.ipynb`](file:///research/research.ipynb) with Matplotlib figures saved to `research/figures/`:
1. `fig1_app_consumption.png`: Application consumption distribution across categories.
2. `fig2_congestion_correlation.png`: Multivariate correlation matrix of network bottlenecks.
3. `fig3_anomaly_pr_curves.png`: Precision, Recall, and F1 comparison across anomaly models.
4. `fig4_forecast_comparison.png`: Predicted vs actual demand curves on a 72-hour test horizon.
5. `fig5_optimization_impact.png`: Quantified reduction in congested hours after traffic shifting.

---

## Limitations

- **Encrypted Payloads**: Modern web traffic uses TLS 1.3/HTTPS. Packet inspection attributes flows by socket connection metadata and process executable mappings rather than decrypting application payloads.
- **Root/Admin Socket Capture**: Raw socket packet sniffing via Scapy requires administrator privileges. When run under standard user permissions, the application gracefully degrades to OS-level `psutil` socket connection mappings with zero crashes.
- **Single-Host Concurrency**: SQLite with WAL mode operates with high efficiency for local workloads; for multi-gigabit corporate WAN infrastructures across thousands of probes, a distributed time-series database (TimescaleDB or ClickHouse) is recommended.
#   b a n d w i d t h _ a n a l y z e  
 