from __future__ import annotations

from financial_copilot.config import Settings
from financial_copilot.state import ResearchState


def metrics_analysis_agent(state: ResearchState, settings: Settings) -> ResearchState:
    del settings

    metrics = state.get("financial_data", {}).get("metrics", {})
    analysis: dict[str, str] = {}

    try:
        revenue = metrics.get("revenue")
        earnings_growth = metrics.get("earnings_growth")
        revenue_growth = metrics.get("revenue_growth")
        profit_margin = metrics.get("profit_margins")
        roe = metrics.get("roe")
        pe = metrics.get("trailing_pe")

        # Simple heuristics
        growth_note = ""
        if revenue_growth is not None:
            growth_note = (
                f"Revenue growth (YoY) is {round(revenue_growth*100,2)}%" if isinstance(revenue_growth, float) else f"Revenue growth: {revenue_growth}"
            )
        elif earnings_growth is not None:
            growth_note = (
                f"Earnings growth (YoY) is {round(earnings_growth*100,2)}%" if isinstance(earnings_growth, float) else f"Earnings growth: {earnings_growth}"
            )
        else:
            growth_note = "Growth information is limited."

        profitability = ""
        if profit_margin is not None:
            profitability = f"Profit margin ~{round(float(profit_margin)*100,2)}%" if isinstance(profit_margin, (float, int)) else f"Profit margin: {profit_margin}"
        elif roe is not None:
            profitability = f"ROE: {roe}"
        else:
            profitability = "Profitability metrics are limited."

        valuation = ""
        if pe is not None:
            valuation = f"Trailing P/E is {pe}."
        else:
            valuation = "Valuation metrics are limited."

        analysis["growth"] = growth_note
        analysis["profitability"] = profitability
        analysis["valuation"] = valuation

    except Exception as exc:  # pragma: no cover - defensive
        analysis["error"] = f"Analysis failed: {exc}"

    return {
        "analysis": analysis,
        "completed_steps": ["metrics_analysis_agent"],
    }
