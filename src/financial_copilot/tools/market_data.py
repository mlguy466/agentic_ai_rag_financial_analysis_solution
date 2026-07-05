from __future__ import annotations

from typing import Any


def get_company_snapshot(ticker: str) -> tuple[dict[str, Any], list[str]]:
    normalized_ticker = ticker.upper().strip()
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - depends on environment
        return (
            {
                "ticker": normalized_ticker,
                "data_status": "error",
                "error": "yfinance is not installed",
            },
            [f"Unable to import yfinance: {exc}"],
        )

    warnings: list[str] = []
    stock = yf.Ticker(normalized_ticker)

    try:
        info = stock.info or {}
    except Exception as exc:  # pragma: no cover - depends on network/provider
        return (
            {
                "ticker": normalized_ticker,
                "data_status": "error",
                "error": str(exc),
            },
            [f"Failed to fetch market data for {normalized_ticker}: {exc}"],
        )

    try:
        history = stock.history(period="1mo", interval="1d")
    except Exception:  # pragma: no cover - depends on network/provider
        history = None
        warnings.append("Unable to fetch recent price history.")

    price_change_pct: float | None = None
    if history is not None and not history.empty:
        start_close = float(history["Close"].iloc[0])
        end_close = float(history["Close"].iloc[-1])
        if start_close:
            price_change_pct = round(((end_close - start_close) / start_close) * 100, 2)

    metrics = {
        "company_name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_book": info.get("priceToBook"),
        "revenue": info.get("totalRevenue"),
        "ebitda": info.get("ebitda"),
        "net_income": info.get("netIncomeToCommon"),
        "eps": info.get("trailingEps"),
        "free_cashflow": info.get("freeCashflow"),
        "operating_cashflow": info.get("operatingCashflow"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "gross_margins": info.get("grossMargins"),
        "operating_margins": info.get("operatingMargins"),
        "profit_margins": info.get("profitMargins"),
        "beta": info.get("beta"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "one_month_price_change_pct": price_change_pct,
    }

    missing_core_metrics = [
        key
        for key in ("current_price", "market_cap", "revenue", "eps")
        if metrics.get(key) is None
    ]
    if missing_core_metrics:
        warnings.append(
            "Some core financial metrics are missing from yfinance: "
            + ", ".join(missing_core_metrics)
        )

    snapshot = {
        "ticker": normalized_ticker,
        "data_status": "live",
        "source": "yfinance",
        "metrics": metrics,
        "business_summary": info.get("longBusinessSummary"),
    }
    return snapshot, warnings
