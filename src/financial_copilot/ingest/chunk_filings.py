"""Orchestrator for chunking SEC filings from Azure Blob Storage.

This module coordinates the end-to-end chunking pipeline:
1. Reads 10-K filings from Azure Blob under filings/<ticker>/...
2. Parses and chunks using parent-child strategy
3. Stores chunks metadata and prepares for embedding/indexing
4. Tracks chunking progress and handles resumption

Usage (from repository root):

    source .venv/bin/activate
    PYTHONPATH=src python3 src/financial_copilot/ingest/chunk_filings.py

This will process all unprocessed filings in the container and store
chunk metadata in a JSON manifest under chunked/<ticker>/manifest.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from financial_copilot.config import Settings
from financial_copilot.ingest.chunking import chunk_filing
from financial_copilot.services.blob_storage import BlobStorageService

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
CHUNKS_DIR = DATA_DIR / "chunks"


def ensure_dirs() -> None:
    """Create local data directories for chunk metadata."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)


def get_filings_from_blob(settings: Settings) -> dict[str, list[str]]:
    """List all filings in blob storage and group by ticker.
    
    Returns a dict mapping ticker -> list of blob names under filings/<ticker>/...
    """
    if not settings.azure_storage_account_url:
        return {}
    
    blob_service = BlobStorageService(settings)
    all_blobs = blob_service.list_blob_names(prefix="filings/")
    
    filings_by_ticker: dict[str, list[str]] = {}
    
    for blob_name in all_blobs:
        parts = blob_name.split("/")
        if len(parts) < 2:
            continue
        
        ticker = parts[1]
        # Skip the ticker folder itself, only include actual files
        if len(parts) > 2:
            if ticker not in filings_by_ticker:
                filings_by_ticker[ticker] = []
            filings_by_ticker[ticker].append(blob_name)
    
    return filings_by_ticker


def read_filing_from_blob(settings: Settings, blob_name: str) -> Optional[str]:
    """Download and read a filing from blob storage."""
    if not settings.azure_storage_account_url:
        return None
    
    try:
        blob_service = BlobStorageService(settings)
        client = blob_service.build_client()
        container_client = client.get_container_client(settings.azure_storage_container)
        blob_client = container_client.get_blob_client(blob_name)
        download_stream = blob_client.download_blob()
        return download_stream.readall().decode("utf-8")
    except Exception as exc:
        logger.warning("Failed to read blob %s: %s", blob_name, exc)
        return None


def get_chunked_tickers(settings: Settings) -> set[str]:
    """Return set of tickers already chunked and stored in blob."""
    if not settings.azure_storage_account_url:
        return set()
    
    try:
        blob_service = BlobStorageService(settings)
        chunk_blobs = blob_service.list_blob_names(prefix="chunked/")
        
        tickers = set()
        for blob_name in chunk_blobs:
            parts = blob_name.split("/")
            if len(parts) >= 2 and parts[-1] == "manifest.json":
                tickers.add(parts[1])
        return tickers
    except Exception:
        return set()


def save_chunk_manifest_to_blob(
    settings: Settings,
    ticker: str,
    chunks_data: dict,
) -> Optional[str]:
    """Save chunk manifest (metadata) to blob for later reference.
    
    Stores under chunked/<ticker>/manifest.json
    """
    if not settings.azure_storage_account_url:
        return None
    
    try:
        blob_service = BlobStorageService(settings)
        blob_service.ensure_container()
        
        manifest_json = json.dumps(chunks_data, indent=2)
        blob_name = f"chunked/{ticker}/manifest.json"
        
        return blob_service.upload_text_blob(blob_name, manifest_json)
    except Exception as exc:
        logger.warning("Failed to save chunk manifest for %s: %s", ticker, exc)
        return None


def chunk_ticker_filings(
    settings: Settings,
    ticker: str,
    blob_names: list[str],
) -> dict:
    """Chunk all filings for a given ticker.
    
    Returns a manifest dict with chunking stats and metadata.
    """
    logger.info("Chunking %d filing(s) for %s", len(blob_names), ticker)
    
    all_parent_chunks = []
    all_child_chunks = []
    filing_metadata = []
    
    for blob_name in blob_names:
        filing_text = read_filing_from_blob(settings, blob_name)
        if not filing_text:
            logger.warning("Skipping %s (failed to read)", blob_name)
            continue
        
        # Extract accession number from blob name (e.g., 0000051143-24-001234.txt)
        filename = blob_name.split("/")[-1]
        accession_number = filename.replace(".txt", "")
        
        try:
            parent_chunks, child_chunks = chunk_filing(
                ticker=ticker,
                filing_text=filing_text,
                metadata={
                    "accession_number": accession_number,
                    "blob_name": blob_name,
                },
            )
            
            all_parent_chunks.extend(parent_chunks)
            all_child_chunks.extend(child_chunks)
            
            filing_metadata.append({
                "accession_number": accession_number,
                "blob_name": blob_name,
                "parent_chunks": len(parent_chunks),
                "child_chunks": len(child_chunks),
            })
            
            logger.info(
                "Chunked %s: %d parents, %d children",
                accession_number,
                len(parent_chunks),
                len(child_chunks),
            )
        except Exception as exc:
            logger.warning("Failed to chunk %s: %s", blob_name, exc)
            continue
    
    # Convert to JSON-serializable format
    from financial_copilot.ingest.chunking import chunks_to_json
    
    manifest = {
        "ticker": ticker,
        "filing_count": len(filing_metadata),
        "total_parent_chunks": len(all_parent_chunks),
        "total_child_chunks": len(all_child_chunks),
        "filings": filing_metadata,
        "parent_chunks": chunks_to_json(all_parent_chunks),
        "child_chunks": chunks_to_json(all_child_chunks),
    }
    
    return manifest


def chunk_all_filings(resume: bool = True) -> None:
    """Main orchestrator: chunk all filings in blob storage.
    
    Args:
        resume: If True, skip tickers already chunked. If False, process all.
    """
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    
    if not settings.azure_storage_account_url:
        logger.error("AZURE_STORAGE_ACCOUNT_URL not configured")
        return
    
    ensure_dirs()
    
    # Get all filings grouped by ticker
    filings_by_ticker = get_filings_from_blob(settings)
    logger.info("Found filings for %d tickers", len(filings_by_ticker))
    
    # Get already-chunked tickers
    chunked_tickers = get_chunked_tickers(settings) if resume else set()
    logger.info("Found %d already-chunked tickers (resume=%s)", len(chunked_tickers), resume)
    
    # Process each ticker
    processed = 0
    failed = 0
    
    for ticker in sorted(filings_by_ticker.keys()):
        if ticker in chunked_tickers:
            logger.info("Skipping %s (already chunked)", ticker)
            continue
        
        blob_names = filings_by_ticker[ticker]
        
        try:
            manifest = chunk_ticker_filings(settings, ticker, blob_names)
            
            # Save manifest to blob
            save_url = save_chunk_manifest_to_blob(settings, ticker, manifest)
            
            if save_url:
                logger.info(
                    "Saved chunk manifest for %s (%d parents, %d children)",
                    ticker,
                    manifest["total_parent_chunks"],
                    manifest["total_child_chunks"],
                )
                processed += 1
            else:
                logger.error("Failed to save chunk manifest for %s", ticker)
                failed += 1
        except Exception as exc:
            logger.error("Failed to chunk %s: %s", ticker, exc)
            failed += 1
    
    logger.info(
        "Chunking complete: processed=%d, failed=%d, skipped=%d",
        processed,
        failed,
        len(chunked_tickers),
    )


if __name__ == "__main__":
    chunk_all_filings(resume=True)
