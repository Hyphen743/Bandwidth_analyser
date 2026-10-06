#!/usr/bin/env bash
set -e

echo "==============================================================================="
echo "Bandwidth Usage Monitor and Analyzer - Startup Script"
echo "==============================================================================="

# 1. Activate venv if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 2. Install dependencies
echo "[1/4] Checking and installing dependencies..."
pip install -r requirements.txt

# 3. Initialize DB
echo "[2/4] Initializing SQLite database schema and views..."
python db/init_db.py

# 4. Generate 90-day simulation if empty
echo "[3/4] Checking telemetry database..."
python -c "from db.repository import DatabaseRepository; repo = DatabaseRepository(); stats = repo.get_db_stats(); exit(0 if stats['counts']['bandwidth_usage'] > 0 else 1)" || {
    echo "Seeding 90 days of realistic seasonal network telemetry..."
    python collector/simulator.py --days 90
}

# 5. Launch Streamlit
echo "[4/4] Launching Streamlit dashboard on http://localhost:8501 ..."
streamlit run app.py
