from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List

try:
    from sec_edgar_downloader import Downloader as SecDownloader
    from sec_edgar_downloader._orchestrator import (
        DownloadMetadata,
        aggregate_filings_to_download,
        download_filing,
    )
    from sec_edgar_downloader._utils import validate_and_convert_ticker_or_cik
except Exception:  # pragma: no cover - optional
    SecDownloader = None
    DownloadMetadata = None
    aggregate_filings_to_download = None
    download_filing = None
    validate_and_convert_ticker_or_cik = None

from financial_copilot.config import Settings
from financial_copilot.services.blob_storage import BlobStorageService
from financial_copilot.tools.market_data import get_company_snapshot

logger = logging.getLogger(__name__)

# Use repository root `data/` directory
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
FILINGS_DIR = DATA_DIR / "filings"


def ensure_dirs(blob_only: bool = False) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not blob_only:
        FILINGS_DIR.mkdir(parents=True, exist_ok=True)


def read_fortune_list(path: Path) -> List[dict]:
    out = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            company_name = row.get("company") or row.get("name") or ""
            out.append({"ticker": row["ticker"].strip(), "company": company_name.strip()})
    return out


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upload_folder_to_blob(settings: Settings, ticker: str, source_dir: Path) -> list[str]:
    """Upload all files under source_dir to the configured Azure Blob container.

    Files are stored under the `filings/<ticker>/...` prefix inside the same
    container that the application already uses.
    """
    if not settings.azure_storage_account_url:
        return []

    blob_service = BlobStorageService(settings)
    blob_service.ensure_container()

    uploaded_urls: list[str] = []
    for file_path in sorted(source_dir.rglob("*")):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(source_dir).as_posix()
        blob_name = f"filings/{ticker}/{relative_path}"
        try:
            uploaded_urls.append(blob_service.upload_file_blob(blob_name, file_path))
        except Exception as exc:
            logger.warning(
                "Failed to upload %s to Azure Blob container: %s",
                file_path,
                exc,
            )
    return uploaded_urls


def _upload_seed_to_blob(settings: Settings, ticker: str, seed_text: str) -> str | None:
    """Upload a generated fallback seed directly to the Azure Blob container."""
    if not settings.azure_storage_account_url:
        return None

    blob_service = BlobStorageService(settings)
    blob_service.ensure_container()
    blob_name = f"filings/{ticker}/{ticker}-seed.txt"
    try:
        return blob_service.upload_text_blob(blob_name, seed_text)
    except Exception as exc:
        logger.warning("Failed to upload seed blob for %s: %s", ticker, exc)
        return None


def _download_and_upload_filings(settings: Settings, ticker: str, company_name: str) -> list[str]:
    """Download SEC filings in-memory and upload them directly into Azure Blob."""
    if (
        not settings.azure_storage_account_url
        or SecDownloader is None
        or aggregate_filings_to_download is None
        or download_filing is None
        or validate_and_convert_ticker_or_cik is None
    ):
        return []

    try:
        dl = SecDownloader(
            company_name=company_name,
            email_address="dev@example.com",
        )
        cik = validate_and_convert_ticker_or_cik(ticker, dl.ticker_to_cik_mapping)
    except Exception as exc:
        logger.warning(
            "Skipping direct SEC blob upload for %s because ticker lookup failed: %s",
            ticker,
            exc,
        )
        return []

    metadata = DownloadMetadata(
        download_folder=Path("."),
        form="10-K",
        cik=cik,
        ticker=ticker,
    )

    to_download = aggregate_filings_to_download(metadata, dl.user_agent)
    if not to_download:
        return []

    blob_service = BlobStorageService(settings)
    blob_service.ensure_container()
    uploaded_urls: list[str] = []

    for td in to_download:
        try:
            contents = download_filing(td.raw_filing_uri, dl.user_agent)
            blob_name = f"filings/{ticker}/{td.accession_number}.txt"
            uploaded_urls.append(blob_service.upload_blob(blob_name, contents))
        except Exception as exc:
            logger.warning(
                "Failed to download or upload filing %s for %s: %s",
                td.accession_number,
                ticker,
                exc,
            )
            continue

    return uploaded_urls


def build_seed_from_snapshot(ticker: str) -> str:
    snapshot, warnings = get_company_snapshot(ticker)
    metrics = snapshot.get("metrics", {})
    lines = [f"Ticker: {ticker}", f"Company: {metrics.get('company_name')}", "", "Business Summary:", snapshot.get("business_summary") or "No summary.", "", "Structured JSON:", str(snapshot)]
    return "\n".join(lines)


def ingest_fortune(csv_path: Path) -> List[Path]:
    settings = Settings.from_env()
    ensure_dirs(blob_only=settings.azure_blob_only_ingestion)
    companies = read_fortune_list(csv_path)
    saved_files: List[Path] = []

    for item in companies:
        ticker = item["ticker"]
        company_name = item.get("company") or ticker or "Unknown Company"
        identifier = ticker or company_name
        logger.info("Processing %s (%s)", company_name, identifier)

        uploaded_files: list[str] = []
        if settings.azure_storage_account_url:
            uploaded_files = _download_and_upload_filings(
                settings, ticker, company_name
            )

        if uploaded_files:
            logger.info(
                "Uploaded %d filings for %s into Azure Blob container.",
                len(uploaded_files),
                identifier,
            )
            continue

        # If direct blob upload did not run or no filings were found, create a
        # fallback seed. In blob-only mode we only upload the seed text.
        if ticker:
            seed = build_seed_from_snapshot(ticker)
        else:
            seed = (
                f"Company: {company_name}\n"
                "Ticker: N/A\n"
                "No ticker was available for this Fortune 500 entry.\n"
                "SEC filings could not be downloaded automatically."
            )

        if settings.azure_blob_only_ingestion:
            seed_blob = _upload_seed_to_blob(settings, ticker or company_name, seed)
            if seed_blob:
                logger.info(
                    "Uploaded fallback seed for %s into Azure Blob container.",
                    identifier,
                )
        else:
            out_dir = FILINGS_DIR / (ticker or company_name.replace(" ", "_").replace("/", "_"))
            out_dir.mkdir(parents=True, exist_ok=True)
            seed_filename = f"{ticker or company_name.replace(' ', '_').replace('/', '_')}-seed.txt"
            seed_path = out_dir / seed_filename
            save_text(seed_path, seed)
            saved_files.append(seed_path)
            logger.info("Wrote fallback seed for %s to %s", identifier, seed_path)
            if settings.azure_storage_account_url:
                seed_blob = _upload_seed_to_blob(settings, ticker or company_name, seed)
                if seed_blob:
                    logger.info(
                        "Uploaded fallback seed for %s into Azure Blob container.",
                        identifier,
                    )

    return saved_files


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    csv_path = DATA_DIR / "fortune_500.csv"
    if not csv_path.exists():
        logger.error("Fortune 500 CSV not found at %s", csv_path)
        raise SystemExit(1)

    files = ingest_fortune(csv_path)
    for f in files:
        print(f"SAVED: {f}")
