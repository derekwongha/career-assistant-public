"""
Test configuration for the public repository.

Tests run against the fictional candidate in
examples/synthetic_career_evidence_catalog.json, never against a personal
catalog. Explicit environment variables still take precedence.
"""

import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent

os.environ.setdefault(
    "CAREER_EVIDENCE_CATALOG",
    str(REPO_ROOT / "examples" / "synthetic_career_evidence_catalog.json"),
)
os.environ.setdefault("CANDIDATE_NAME", "Casey Placeholder")

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
