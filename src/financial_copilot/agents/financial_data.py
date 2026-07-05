from __future__ import annotations

from financial_copilot.config import Settings
from financial_copilot.state import ResearchState
from financial_copilot.tools.market_data import get_company_snapshot


def financial_data_agent(state: ResearchState, settings: Settings) -> ResearchState:
    del settings  # Financial provider wiring comes next.

    ticker = state["ticker"]
    snapshot, warnings = get_company_snapshot(ticker)

    return {
        "workflow_status": "running",
        "financial_data": snapshot,
        "completed_steps": ["financial_data_agent"],
        "warnings": warnings,
    }

