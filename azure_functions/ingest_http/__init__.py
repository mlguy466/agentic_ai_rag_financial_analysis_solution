from __future__ import annotations

import csv
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import List

import azure.functions as func

# Zip deploy layout: wwwroot/{ingest_http,src,data,...} — package root is one level up.
ROOT_DIR = Path(__file__).resolve().parents[1]
LIB_DIR = ROOT_DIR / ".python_packages" / "lib" / "site-packages"
for path_entry in (LIB_DIR, ROOT_DIR / "src"):
    if path_entry.exists() and str(path_entry) not in sys.path:
        sys.path.insert(0, str(path_entry))

from financial_copilot.config import Settings
from financial_copilot.services.blob_storage import BlobStorageService
from financial_copilot.ingest.fortune_ingest import ingest_fortune

logger = logging.getLogger(__name__)


def _build_resume_csv(csv_path: Path, existing: set, batch_size: int) -> Path | None:
    """Create a temporary CSV with up to `batch_size` companies not in `existing`.

    Returns path to the temporary CSV or None if nothing to process.
    """
    if not csv_path.exists():
        logger.warning("Fortune CSV not found at %s", csv_path)
        return None

    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8")
    writer = csv.writer(tmp)
    writer.writerow(["rank", "ticker", "company", "fortune_url"])

    written = 0
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if written >= batch_size:
                break
            ticker = (row.get("ticker") or "").strip()
            if not ticker or ticker in existing:
                continue
            writer.writerow([row.get("rank", ""), ticker, row.get("company", ""), row.get("fortune_url", "")])
            written += 1

    tmp.close()
    if written == 0:
        os.unlink(tmp.name)
        return None
    return Path(tmp.name)


def _existing_tickers_from_blob(settings: Settings) -> set:
    if not settings.azure_storage_account_url:
        return set()
    try:
        svc = BlobStorageService(settings)
        blobs = svc.list_blob_names(prefix="filings/")
        tickers = set()
        for b in blobs:
            parts = b.split("/")
            if len(parts) >= 2:
                tickers.add(parts[1])
        return tickers
    except Exception as e:
        logger.warning("Failed to list existing blobs: %s", e)
        return set()


def main(req: func.HttpRequest) -> func.HttpResponse:  # pragma: no cover - Azure entry
    """HTTP-triggered Azure Function to run a batched ingestion job.

    Query/JSON params:
      - batch_size: number of companies to ingest in this invocation (default 10)

    The function builds a temporary resume CSV with up to `batch_size` tickers
    that are not already present under `filings/<ticker>/...` in the configured
    Azure container, then calls the existing `ingest_fortune` function to
    perform the download + upload. This keeps the work batched and resumable.
    """
    try:
        settings = Settings.from_env()
    except Exception as e:
        return func.HttpResponse(json.dumps({"error": "Failed to load settings", "detail": str(e)}), status_code=500)

    try:
        body = req.get_json() if req.get_body() else {}
    except Exception:
        body = {}

    batch_size = None
    qs_batch = req.params.get("batch_size") if req.params else None
    if qs_batch:
        try:
            batch_size = int(qs_batch)
        except Exception:
            batch_size = None

    if not batch_size:
        batch_size = int(body.get("batch_size", 10)) if isinstance(body, dict) else 10

    # Find remaining tickers
    existing = _existing_tickers_from_blob(settings)

    # Build resume CSV from repository data/fortune_500.csv
    # Locate the CSV by walking parent directories so this works both locally and in zipped deployments.
    _p = Path(__file__).resolve()
    fortune_csv = None
    for parent in _p.parents:
        candidate = parent / "data" / "fortune_500.csv"
        if candidate.exists():
            fortune_csv = candidate
            break
    if fortune_csv is None:
        fortune_csv = Path(__file__).resolve().parents[3] / "data" / "fortune_500.csv"

    resume_csv = _build_resume_csv(fortune_csv, existing, batch_size)
    if not resume_csv:
        return func.HttpResponse(json.dumps({"status": "no_remaining", "message": "No remaining tickers to ingest"}), mimetype="application/json", status_code=200)

    # Call ingest logic
    try:
        saved = ingest_fortune(resume_csv)
        # Clean up tmp file
        try:
            resume_csv.unlink()
        except Exception:
            pass

        result = {
            "status": "ok",
            "batch_size": batch_size,
            "processed_saved_files": [str(p) for p in saved],
        }
        return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200)
    except Exception as e:
        return func.HttpResponse(json.dumps({"status": "error", "detail": str(e)}), mimetype="application/json", status_code=500)
