@echo off
echo ===============================================================================
echo Bandwidth Usage Monitor and Analyzer - Startup Script
echo ===============================================================================

REM 1. Activate virtual environment if present
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM 2. Install dependencies
echo [1/4] Checking and installing dependencies...
pip install -r requirements.txt

REM 3. Initialize SQLite database
echo [2/4] Initializing SQLite database schema and views...
python db\init_db.py

REM 4. Generate 90-day simulated telemetry if database is empty
echo [3/4] Checking telemetry database...
python -c "from db.repository import DatabaseRepository; repo = DatabaseRepository(); stats = repo.get_db_stats(); exit(0 if stats['counts']['bandwidth_usage'] > 0 else 1)"
if errorlevel 1 (
    echo Seeding 90 days of realistic seasonal network telemetry...
    python collector\simulator.py --days 90
)

REM 5. Launch Streamlit UI
echo [4/4] Launching Streamlit dashboard on http://localhost:8501 ...
streamlit run app.py
