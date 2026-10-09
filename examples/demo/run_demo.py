"""
Runs the review dashboard on port 8081 against the SYNTHETIC demo data.

Builds the demo data first if it does not exist yet. The working directory is
set to the repository root so the relative paths stored in the demo database
resolve correctly.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "04_Application"))
sys.path.insert(0, str(DEMO_DIR))
os.chdir(REPO_ROOT)

import make_demo  # noqa: E402
from dashboard_server import create_server  # noqa: E402

PORT = 8081

if not (make_demo.DB_PATH.exists() and make_demo.XLSX_PATH.exists()):
    make_demo.main()

server = create_server(port=PORT, db_path=make_demo.DB_PATH, excel_path=make_demo.XLSX_PATH)
print(f"DEMO dashboard (synthetic data) on http://127.0.0.1:{PORT}/  - Ctrl+C to stop")
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
