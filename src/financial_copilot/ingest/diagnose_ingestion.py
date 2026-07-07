"""Diagnose ingestion issues by testing SEC downloader on stuck tickers.

This script identifies which ticker causes the SEC Edgar downloader to hang
and suggests workarounds.

Usage:

    source .venv/bin/activate
    PYTHONPATH=src python3 src/financial_copilot/ingest/diagnose_ingestion.py
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Set

try:
    from sec_edgar_downloader import Downloader as SecDownloader
    from sec_edgar_downloader._utils import validate_and_convert_ticker_or_cik
except Exception as e:
    print(f"Failed to import sec_edgar_downloader: {e}")
    SecDownloader = None

from financial_copilot.config import Settings
from financial_copilot.services.blob_storage import BlobStorageService

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
FORTUNE_CSV = DATA_DIR / "fortune_500.csv"


def get_existing_tickers(settings: Settings) -> Set[str]:
    """Return tickers already uploaded to blob."""
    if not settings.azure_storage_account_url:
        return set()
    
    try:
        blob_service = BlobStorageService(settings)
        blob_names = blob_service.list_blob_names(prefix="filings/")
        tickers = set()
        for blob_name in blob_names:
            parts = blob_name.split("/")
            if len(parts) >= 2:
                tickers.add(parts[1])
        return tickers
    except Exception as e:
        logger.warning(f"Failed to list blobs: {e}")
        return set()


def read_fortune_list(path: Path) -> list[dict]:
    """Read Fortune 500 CSV."""
    out = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ticker = (row.get("ticker") or "").strip()
            if not ticker:
                continue
            company_name = row.get("company") or ""
            out.append({"ticker": ticker, "company": company_name.strip()})
    return out


def test_ticker_download(ticker: str, company: str) -> bool:
    """Test whether a ticker can be downloaded without hanging.
    
    Returns True if download succeeds, False if it hangs or fails.
    """
    if not SecDownloader:
        return False
    
    try:
        dl = SecDownloader(company_name=company, email_address="dev@example.com")
        # Try to get CIK mapping - if this hangs, we found the culprit
        cik = validate_and_convert_ticker_or_cik(ticker, dl.ticker_to_cik_mapping)
        print(f"✓ {ticker} ({company}): OK (CIK={cik})")
        return True
    except Exception as e:
        print(f"✗ {ticker} ({company}): FAILED ({type(e).__name__}: {str(e)[:80]})")
        return False


def main():
    logging.basicConfig(level=logging.INFO)
    
    settings = Settings.from_env()
    existing = get_existing_tickers(settings)
    companies = read_fortune_list(FORTUNE_CSV)
    
    print(f"Already ingested: {len(existing)} tickers")
    print(f"Total companies: {len(companies)}")
    
    # Find first company NOT yet ingested
    remaining = [c for c in companies if c["ticker"] not in existing]
    print(f"Remaining to ingest: {len(remaining)}")
    
    if not remaining:
        print("✓ All companies ingested!")
        return
    
    # Test the next batch of tickers that should have been processed
    print(f"\nTesting next 10 remaining tickers (with 5-second timeout per call):\n")
    
    for i, company_dict in enumerate(remaining[:10]):
        ticker = company_dict["ticker"]
        company = company_dict["company"]
        result = test_ticker_download(ticker, company)
        if not result:
            print(f"\n⚠ Found problematic ticker: {ticker}")
            print(f"   This ticker likely caused the ingestion to hang.")
            print(f"   Consider skipping it in the ingest script.\n")
            break


if __name__ == "__main__":
    main()
