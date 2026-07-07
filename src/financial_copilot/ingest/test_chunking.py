"""Quick test of the chunking orchestrator on a sample ticker.

This allows testing the chunking pipeline on a few ingested filings
before running the full orchestrator on all tickers.

Usage:

    source .venv/bin/activate
    PYTHONPATH=src python3 src/financial_copilot/ingest/test_chunking.py --ticker MMM --limit 2

"""

from __future__ import annotations

import argparse
import logging
from typing import Optional

from financial_copilot.config import Settings
from financial_copilot.ingest.chunk_filings import (
    chunk_ticker_filings,
    get_filings_from_blob,
    save_chunk_manifest_to_blob,
)

logger = logging.getLogger(__name__)


def test_chunk_ticker(settings: Settings, ticker: str, limit: Optional[int] = None) -> None:
    """Test chunking for a single ticker.
    
    Args:
        settings: Configuration
        ticker: Company ticker to test
        limit: Max number of filings to process
    """
    logging.basicConfig(level=logging.INFO)
    
    filings_by_ticker = get_filings_from_blob(settings)
    
    if ticker not in filings_by_ticker:
        logger.error(f"No filings found for ticker {ticker}")
        logger.info(f"Available tickers: {', '.join(sorted(filings_by_ticker.keys())[:10])}")
        return
    
    blob_names = filings_by_ticker[ticker]
    if limit:
        blob_names = blob_names[:limit]
    
    logger.info(f"Testing chunking for {ticker} with {len(blob_names)} filing(s)")
    
    # Chunk the filings
    manifest = chunk_ticker_filings(settings, ticker, blob_names)
    
    # Display results
    print(f"\n{'='*60}")
    print(f"Chunking Results for {ticker}")
    print(f"{'='*60}")
    print(f"Filings processed: {manifest['filing_count']}")
    print(f"Parent chunks: {manifest['total_parent_chunks']}")
    print(f"Child chunks: {manifest['total_child_chunks']}")
    print(f"\nFiling details:")
    
    for filing in manifest['filings']:
        print(f"  - {filing['accession_number']}")
        print(f"    Parents: {filing['parent_chunks']}, Children: {filing['child_chunks']}")
    
    print(f"\nSample parent chunks:")
    for parent in manifest['parent_chunks'][:3]:
        print(f"  - {parent['chunk_id']}: {parent['section']}")
        print(f"    Text preview: {parent['text'][:100]}...")
    
    print(f"\nSample child chunks:")
    for child in manifest['child_chunks'][:3]:
        print(f"  - {child['chunk_id']} (seq {child['sequence']})")
        print(f"    Parent: {child['parent_id']}")
        print(f"    Text preview: {child['text'][:100]}...")
    
    # Save to blob
    print(f"\nSaving manifest to blob...")
    save_url = save_chunk_manifest_to_blob(settings, ticker, manifest)
    if save_url:
        print(f"✓ Saved to: {save_url}")
    else:
        print(f"✗ Failed to save manifest")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test chunking on a sample ticker")
    parser.add_argument("--ticker", default="MMM", help="Ticker to chunk (default: MMM)")
    parser.add_argument("--limit", type=int, help="Limit number of filings to process")
    
    args = parser.parse_args()
    
    settings = Settings.from_env()
    test_chunk_ticker(settings, args.ticker, args.limit)
