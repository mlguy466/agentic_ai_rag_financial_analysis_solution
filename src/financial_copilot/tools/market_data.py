from __future__ import annotations

from typing import Any


def get_company_snapshot(ticker: str) -> tuple[dict[str, Any], list[str]]:
    """Return a placeholder market data payload until a live provider is wired in."""
    normalized_ticker = ticker.upper().strip()
    snapshot = {
        "ticker": normalized_ticker,
        "data_status": "placeholder",
        "metrics_requested": [
            "revenue",
            "ebitda",
            "net_income",
            "eps",
            "cash_flow",
            "debt_to_equity",
            "pe_ratio",
            "roe",
        ],
        "next_provider": "yfinance or Financial Modeling Prep",
    }
    warnings = [
        f"Live financial data is not connected yet for {normalized_ticker}.",
        "Replace the placeholder market data tool before relying on valuation output.",
    ]
    return snapshot, warnings

