# Run Bandwidth Analyzer on another computer

## Requirements

- Python 3.11 or newer (64-bit recommended)
- Visual Studio Code
- VS Code's Microsoft Python extension
- Internet access for the first install (`pip install -r requirements.txt`)

The Python packages are listed in [`requirements.txt`](requirements.txt). SQLite is included with Python; there is no separate database server to install. The app creates its local database at `data/bandwidth.db` when initialized.

## Windows + VS Code

1. Copy or clone the complete project folder onto the computer. Keep the `db`, `analytics`, `collector`, `ml`, `pages`, and `ui` folders alongside `app.py`.
2. Open that folder in VS Code (`File > Open Folder`).
3. Open **Terminal > New Terminal** and run:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   python db\init_db.py
   python collector\simulator.py --days 90
   streamlit run app.py
   ```

   If PowerShell blocks activation, you can skip the activation step and use the environment's executables directly:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe db\init_db.py
   .\.venv\Scripts\python.exe collector\simulator.py --days 90
   .\.venv\Scripts\streamlit.exe run app.py
   ```

4. Open [http://localhost:8501](http://localhost:8501) in a browser.
5. In VS Code, select the `.venv` interpreter with **Ctrl+Shift+P > Python: Select Interpreter** so Run/Debug uses the same installed packages.

For later launches, open the project folder and run `streamlit run app.py` from the activated `.venv`. On Windows, `run.bat` is also provided to install dependencies, initialize the database, seed demo data if needed, and launch the app.

## macOS / Linux

From a terminal opened in the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python db/init_db.py
python collector/simulator.py --days 90
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501). `run.sh` is also included.

## What works on the other computer

- **Simulated (90 Days)** works after the demo-data generation step and needs no network adapter permissions.
- **Live Network (psutil)** reads aggregate traffic counters from the computer running the app. It does not bring over your current machine's live data or historic database.
- Socket/process visibility depends on operating-system permissions. Per-process byte totals are not available from socket counts alone.
- The Internet Speed Test needs internet access and downloads/uploads test data when run.
- Packet capture through Scapy is optional and may require administrator/root privileges and OS-specific packet-capture support. The dashboard's normal live counter mode does not require Scapy.

## Deployment-wide friend and device rankings

The default friend list remains in the local SQLite account database. To share rankings across deployed users, configure a separate PostgreSQL database for the ranking feature. The application creates only `ba_shared_*` tables in that PostgreSQL database; the existing SQLite telemetry database, its schema, and the normal dashboards are not migrated or reset.

1. Create a PostgreSQL database with a TLS connection URL. Do not commit the URL or put it in source control.
2. Set `BANDWIDTH_SHARED_DATABASE_URL` as a secret for the Streamlit app and for the ingestion API service. Add `BANDWIDTH_API_URL` to the Streamlit app, for example `https://your-api-host.example/api/v1/usage`.
3. Run `python backend_api.py` as a separate internet-facing service behind HTTPS. Configure its host platform to route HTTPS to the service's `PORT` (or set `BANDWIDTH_API_PORT`) and set `BANDWIDTH_API_HOST=0.0.0.0`. The API accepts authenticated collector samples only; it does not provide public account or ranking reads.
4. Each user must sign in, open **Rankings** once to register their friend code in the shared ranking store, then share the code. Adding a code is directional, so each person adds the other's code to see both sides.
5. In **Rankings**, create a collector token on each computer to include. Clone/download the project on that computer, install its requirements, then run the displayed `collector/friend_agent.py` command. Keep the process running while collecting. It measures aggregate byte deltas on that computer's default-route adapter and sends them over HTTPS.

Without `BANDWIDTH_SHARED_DATABASE_URL`, the Rankings page keeps its existing local-only SQLite behavior. A separate deployed API and shared PostgreSQL database are required for different computers to contribute to one ranking. Per-application traffic is not inferred from adapter counters.

The local database and collected history are computer-specific. The database is intentionally excluded from Git by `.gitignore`; each installation initializes its own database.
