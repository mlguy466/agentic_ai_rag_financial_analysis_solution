from __future__ import annotations

from financial_copilot.config import Settings
from financial_copilot.services.blob_storage import BlobStorageService
from financial_copilot.services.search import SearchIndexService
from financial_copilot.state import EvidenceChunk, ResearchState


def filings_rag_agent(state: ResearchState, settings: Settings) -> ResearchState:
    ticker = state["ticker"].upper()
    blob_service = BlobStorageService(settings)
    search_service = SearchIndexService(settings)

    evidence: list[EvidenceChunk] = [
        {
            "source": f"sec://{ticker}/latest-10k",
            "snippet": "Placeholder evidence. Wire SEC ingestion and chunk indexing next.",
            "relevance": "Provides a stub filing citation for the report layer.",
        }
    ]

    filings_context = {
        "ticker": ticker,
        "blob_target": blob_service.describe_target(),
        "search_target": search_service.describe_target(),
        "search_auth_mode": search_service.describe_auth_mode(),
        "ingestion_status": "placeholder",
        "next_step": "Fetch SEC filing text, upload raw text to Blob Storage, then index chunks in Azure AI Search.",
    }

    warnings: list[str] = []
    if not settings.azure_search_endpoint:
        warnings.append("Azure AI Search is not configured yet.")
    if not settings.azure_storage_account_url:
        warnings.append("Azure Blob Storage is not configured yet.")

    return {
        "filings_context": filings_context,
        "retrieved_evidence": evidence,
        "completed_steps": ["filings_rag_agent"],
        "warnings": warnings,
    }
