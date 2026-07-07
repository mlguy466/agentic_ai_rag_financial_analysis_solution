from __future__ import annotations

import json

from financial_copilot.config import Settings
from financial_copilot.services.blob_storage import BlobStorageService
from financial_copilot.services.search import SearchIndexService
from financial_copilot.state import EvidenceChunk, ResearchState


def _build_seed_content(state: ResearchState) -> str:
    financial_data = state.get("financial_data", {})
    metrics = financial_data.get("metrics", {})
    summary_lines = [
        f"Ticker: {state['ticker'].upper()}",
        f"Company: {metrics.get('company_name')}",
        f"Sector: {metrics.get('sector')}",
        f"Current price: {metrics.get('current_price')}",
        f"Market cap: {metrics.get('market_cap')}",
        f"Revenue: {metrics.get('revenue')}",
        f"EPS: {metrics.get('eps')}",
        f"Trailing PE: {metrics.get('trailing_pe')}",
        f"Debt to equity: {metrics.get('debt_to_equity')}",
        f"ROE: {metrics.get('roe')}",
        "",
        "Business Summary:",
        financial_data.get("business_summary") or "No business summary returned.",
        "",
        "Structured JSON:",
        json.dumps(financial_data, default=str),
    ]
    return "\n".join(summary_lines)


def filings_rag_agent(state: ResearchState, settings: Settings) -> ResearchState:
    ticker = state["ticker"].upper()
    blob_service = BlobStorageService(settings)
    search_service = SearchIndexService(settings)
    warnings: list[str] = []
    evidence: list[EvidenceChunk] = []
    ingestion_status = "unconfigured"

    seed_content = _build_seed_content(state)
    blob_target = blob_service.describe_target()
    search_target = search_service.describe_target()

    if settings.azure_storage_account_url and settings.azure_search_endpoint:
        try:
            # Ensure container exists
            blob_service.ensure_container()

            # Chunk the seed content to improve retrieval granularity
            chunk_size = 800
            chunks: list[str] = [
                seed_content[i : i + chunk_size]
                for i in range(0, len(seed_content), chunk_size)
            ]

            # Upload each chunk as its own blob and index as separate document
            search_service.ensure_index()
            documents: list[dict] = []
            blob_urls: list[str] = []
            for idx, chunk in enumerate(chunks):
                blob_name = f"{ticker.lower()}-research-seed-{idx}.txt"
                blob_url = blob_service.upload_text_blob(blob_name=blob_name, text=chunk)
                blob_urls.append(blob_url)
                documents.append(
                    {
                        "id": f"{ticker.lower()}-research-seed-{idx}",
                        "ticker": ticker,
                        "source": blob_url,
                        "content": chunk,
                    }
                )

            search_service.upload_documents(documents)

            # Search retrieves top-k chunks
            search_results = search_service.search(state.get("query", ticker), top=3)
            evidence = [
                {
                    "source": item.get("source", f"search://{ticker}"),
                    "snippet": str(item.get("content", ""))[:200],
                    "relevance": "Retrieved from Azure AI Search over uploaded seed chunks.",
                }
                for item in search_results
            ]

            blob_target = ",".join(blob_urls) if blob_urls else blob_target
            ingestion_status = "uploaded_and_indexed"
            if not evidence:
                warnings.append(
                    "Azure AI Search was reachable, but no evidence was returned for the current query."
                )
        except Exception as exc:
            ingestion_status = "error"
            warnings.append(f"Live Blob/Search path failed: {exc}")
    else:
        if not settings.azure_search_endpoint:
            warnings.append("Azure AI Search is not configured yet.")
        if not settings.azure_storage_account_url:
            warnings.append("Azure Blob Storage is not configured yet.")

    if not evidence:
        evidence = [
            {
                "source": f"seed://{ticker}/market-data",
                "snippet": seed_content[:300],
                "relevance": "Local fallback evidence built from live yfinance metrics.",
            }
        ]
        if ingestion_status == "unconfigured":
            ingestion_status = "local_fallback"

    filings_context = {
        "ticker": ticker,
        "blob_target": blob_target,
        "search_target": search_target,
        "search_auth_mode": search_service.describe_auth_mode(),
        "ingestion_status": ingestion_status,
        "next_step": "Replace the seed document path with real SEC filing ingestion and chunking.",
    }

    return {
        "filings_context": filings_context,
        "retrieved_evidence": evidence,
        "completed_steps": ["filings_rag_agent"],
        "warnings": warnings,
    }
