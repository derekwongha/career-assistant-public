"""
Career evidence catalog: save and load.

Public version. The pipeline reads a saved, validated evidence catalog
(see career_evidence_schema.py). Building that catalog from your own resume,
portfolio and capability documents is out of scope for this repository:
bring your own catalog in the same schema.

Catalog location, in order of precedence:
  1. CAREER_EVIDENCE_CATALOG environment variable
  2. 04_Application/career_evidence_catalog.json (gitignored)

A fictional example lives in examples/synthetic_career_evidence_catalog.json.
"""

import json
import os
from pathlib import Path

from career_evidence_schema import (
    CareerEvidenceCatalog,
)


APPLICATION_DIR = Path(
    __file__
).resolve().parent

CATALOG_PATH = Path(
    os.environ.get(
        "CAREER_EVIDENCE_CATALOG",
        str(APPLICATION_DIR / "career_evidence_catalog.json"),
    )
)


def save_career_evidence_catalog(
    catalog: CareerEvidenceCatalog,
    output_path: Path = CATALOG_PATH,
) -> Path:
    output_data = (
        catalog.model_dump(
            mode="json"
        )
    )

    output_path.write_text(
        json.dumps(
            output_data,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return output_path


def load_saved_career_evidence_catalog(
    catalog_path: Path = CATALOG_PATH,
) -> CareerEvidenceCatalog:
    if not catalog_path.exists():
        raise FileNotFoundError(
            "Career evidence catalog "
            "does not exist: "
            f"{catalog_path}. "
            "Set CAREER_EVIDENCE_CATALOG or create "
            "04_Application/career_evidence_catalog.json "
            "(see examples/synthetic_career_evidence_catalog.json)."
        )

    raw_data = json.loads(
        catalog_path.read_text(
            encoding="utf-8"
        )
    )

    return (
        CareerEvidenceCatalog
        .model_validate(
            raw_data
        )
    )
