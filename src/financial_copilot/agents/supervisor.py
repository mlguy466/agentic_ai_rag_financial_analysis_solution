from __future__ import annotations

from financial_copilot.config import Settings
from financial_copilot.state import ResearchState


def supervisor_agent(state: ResearchState, settings: Settings) -> ResearchState:
    ticker = state.get("ticker", "").upper()
    missing_services = settings.missing_foundational_services()

    warnings: list[str] = []
    if missing_services:
        warnings.append(
            "Azure foundation is incomplete. Missing: " + ", ".join(missing_services)
        )

    return {
        "workflow_status": "planned",
        "planned_steps": [
            f"Validate Azure resources for {ticker}",
            f"Collect structured company metrics for {ticker}",
            f"Prepare filings retrieval context for {ticker}",
            f"Draft a research-style report for {ticker}",
        ],
        "completed_steps": ["supervisor_agent"],
        "warnings": warnings,
    }

