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

The local database and collected history are computer-specific. The database is intentionally excluded from Git by `.gitignore`; each installation initializes its own database.
