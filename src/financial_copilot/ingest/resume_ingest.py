"""Resume Fortune 500 filings ingestion.

This helper script finds which tickers already have downloaded filings under
`data/filings/` and resumes ingestion for the remaining companies from
`data/fortune_500.csv`.

Usage (from repository root):

    source .venv/bin/activate
    PYTHONPATH=src python3 src/financial_copilot/ingest/resume_ingest.py

The script writes a small temporary CSV `data/fortune_500_resume.csv` containing
only the remaining companies and then calls the existing `ingest_fortune`
function to process those rows. This avoids re-downloading filings that are
already present.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Set

from financial_copilot.config import Settings
from financial_copilot.ingest import fortune_ingest
from financial_copilot.services.blob_storage import BlobStorageService

LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
FORTUNE_CSV = DATA_DIR / "fortune_500.csv"
RESUME_CSV = DATA_DIR / "fortune_500_resume.csv"
FILINGS_DIR = DATA_DIR / "filings"


def existing_tickers(settings: Settings) -> Set[str]:
    """Return a set of tickers already present locally or in Azure blob storage."""
    out: Set[str] = set()
    if FILINGS_DIR.exists():
        for child in FILINGS_DIR.iterdir():
            if child.is_dir():
                out.add(child.name)

    if settings.azure_storage_account_url:
        try:
            blob_service = BlobStorageService(settings)
            blob_names = blob_service.list_blob_names(prefix="filings/")
            for blob_name in blob_names:
                parts = blob_name.split("/")
                if len(parts) >= 2:
                    out.add(parts[1])
        except Exception:
            pass

    return out


def build_resume_csv(skip: Set[str]) -> int:
    """Write `RESUME_CSV` with rows from `FORTUNE_CSV` excluding `skip`.

    Returns the number of rows written.
    """
    if not FORTUNE_CSV.exists():
        LOGGER.error("Fortune CSV not found at %s", FORTUNE_CSV)
        return 0

    written = 0
    with FORTUNE_CSV.open("r", encoding="utf-8") as fh_in, RESUME_CSV.open("w", encoding="utf-8", newline="") as fh_out:
        reader = csv.DictReader(fh_in)
        writer = csv.writer(fh_out)
        writer.writerow(["rank", "ticker", "company", "fortune_url"])
        for row in reader:
            ticker = (row.get("ticker") or "").strip()
            if not ticker or ticker in skip:
                continue
            writer.writerow([row.get("rank", ""), ticker, row.get("company", ""), row.get("fortune_url", "")])
            written += 1

    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    skip = existing_tickers(settings)
    LOGGER.info("Found %d existing tickers, will skip them", len(skip))

    to_process = build_resume_csv(skip)
    if to_process == 0:
        LOGGER.info("No remaining tickers to ingest. Exiting.")
        return

    LOGGER.info("Wrote %d remaining companies to %s", to_process, RESUME_CSV)
    # Call the existing ingestion function with the resume CSV
    saved = fortune_ingest.ingest_fortune(RESUME_CSV)
    LOGGER.info("Ingestion finished, saved %d files", len(saved))


if __name__ == "__main__":
    main()
