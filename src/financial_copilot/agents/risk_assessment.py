from __future__ import annotations

from financial_copilot.config import Settings
from financial_copilot.state import ResearchState


def risk_assessment_agent(state: ResearchState, settings: Settings) -> ResearchState:
    del settings

    metrics = state.get("financial_data", {}).get("metrics", {})
    evidence = state.get("retrieved_evidence", [])
    risks: dict[str, str] = {}

    try:
        debt_to_equity = metrics.get("debt_to_equity")
        current_ratio = metrics.get("current_ratio")
        beta = metrics.get("beta")
        revenue_growth = metrics.get("revenue_growth")

        if debt_to_equity is not None and isinstance(debt_to_equity, (int, float)):
            if debt_to_equity > 100:
                risks["leverage"] = "High debt-to-equity ratio suggests financial leverage risk."
        if current_ratio is not None and isinstance(current_ratio, (int, float)):
            if current_ratio < 1:
                risks["liquidity"] = "Low current ratio indicates potential short-term liquidity pressure."
        if beta is not None:
            if isinstance(beta, (int, float)) and beta > 1.5:
                risks["volatility"] = "High beta suggests above-market volatility risk."
        if revenue_growth is not None and isinstance(revenue_growth, (int, float)) and revenue_growth < 0:
            risks["growth"] = "Negative revenue growth year-over-year indicates potential demand issues."

        # Evidence-based risk hints
        if evidence:
            first = evidence[0]
            snippet = first.get("snippet", "").lower()
            if "lawsuit" in snippet or "litigation" in snippet:
                risks["legal"] = "Mention of litigation in evidence may pose legal risk."

    except Exception as exc:  # pragma: no cover - defensive
        risks["error"] = f"Risk assessment failed: {exc}"

    return {"risk_assessment": risks, "completed_steps": ["risk_assessment_agent"]}
