from __future__ import annotations

import json

try:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional until dependencies are installed
    OpenAI = None
    DefaultAzureCredential = None
    get_bearer_token_provider = None

from financial_copilot.config import Settings
from financial_copilot.state import ResearchState


class AzureOpenAIResearchWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def draft_report(self, state: ResearchState) -> str:
        if self.settings.azure_openai_endpoint:
            try:
                return self._draft_with_azure_openai(state)
            except Exception as exc:
                return self._fallback_report(
                    state,
                    note=(
                        "Azure OpenAI call failed, so a deterministic fallback report was used. "
                        f"Error: {type(exc).__name__}: {exc}"
                    ),
                )

        return self._fallback_report(
            state,
            note="Azure OpenAI is not configured, so a deterministic fallback report was used.",
        )

    def _build_client(self):
        if OpenAI is None:
            raise RuntimeError(
                "OpenAI/Azure Identity dependencies are unavailable. Install project dependencies first."
            )

        endpoint = self.settings.azure_openai_endpoint
        base_url = f"{endpoint.rstrip('/')}/openai/v1/"
        if self.settings.azure_openai_api_key:
            return OpenAI(
                api_key=self.settings.azure_openai_api_key,
                base_url=base_url,
            )

        if DefaultAzureCredential is None or get_bearer_token_provider is None:
            raise RuntimeError("Azure Identity support is unavailable.")

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default"
        )
        return OpenAI(
            api_key=token_provider,
            base_url=base_url,
        )

    def _build_compact_payload(self, state: ResearchState) -> dict:
        """Build a compact payload by filtering nulls and truncating content."""
        financial_data = state.get("financial_data", {})
        metrics = financial_data.get("metrics", {})
        
        # Filter out null/None metric values to reduce token count
        filtered_metrics = {k: v for k, v in metrics.items() if v is not None}
        
        # Keep only top 3 essential metrics for evidence
        evidence = state.get("retrieved_evidence", [])
        compact_evidence = [
            {
                "source": item.get("source", "unknown"),
                "snippet": item.get("snippet", "")[:150],  # Truncate to 150 chars
                "relevance": item.get("relevance", "")[:50],  # Truncate relevance
            }
            for item in evidence[:3]
        ]
        
        # Minimal filings context
        filings_context = state.get("filings_context", {})
        compact_filings = {
            "ingestion_status": filings_context.get("ingestion_status"),
            "search_auth_mode": filings_context.get("search_auth_mode"),
        }
        
        return {
            "ticker": state.get("ticker"),
            "query": state.get("query", ""),
            "metrics": filtered_metrics,
            "business_summary": (financial_data.get("business_summary", "") or "")[:200],
            "evidence": compact_evidence,
            "ingestion_status": compact_filings.get("ingestion_status"),
        }

    def _draft_with_azure_openai(self, state: ResearchState) -> str:
        client = self._build_client()
        payload = self._build_compact_payload(state)

        response = client.chat.completions.create(
            model=self.settings.azure_openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a financial research assistant. Write a concise markdown report "
                        "with: Overview, Key Metrics, Evidence Summary, and Brief Recommendation. "
                        "Use only the provided facts. Keep it brief and factual."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate a research report for {payload['ticker']}:\n\n"
                        f"Metrics: {json.dumps(payload['metrics'], default=str)}\n\n"
                        f"Business: {payload['business_summary']}\n\n"
                        f"Evidence:\n"
                        + "\n".join(
                            f"- {e['snippet']}"
                            for e in payload['evidence']
                        )
                    ),
                },
            ],
            max_completion_tokens=self.settings.azure_openai_max_completion_tokens,
        )
        text = self._extract_response_text(response)
        if text:
            return text

        finish_reason = None
        if getattr(response, "choices", None):
            finish_reason = getattr(response.choices[0], "finish_reason", None)
        usage = getattr(response, "usage", None)
        usage_text = f"{usage}" if usage is not None else "unknown"

        return self._fallback_report(
            state,
            note=(
                "Azure OpenAI returned an empty response, so a deterministic fallback report was used. "
                f"finish_reason={finish_reason}, usage={usage_text}. "
                "Try increasing AZURE_OPENAI_MAX_COMPLETION_TOKENS if this keeps happening."
            ),
        )

    def _extract_response_text(self, response) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""

        message = getattr(choices[0], "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                text_value = getattr(item, "text", None)
                if isinstance(text_value, str):
                    parts.append(text_value)
                    continue
                if isinstance(item, dict):
                    dict_text = item.get("text")
                    if isinstance(dict_text, str):
                        parts.append(dict_text)
            return "\n".join(part.strip() for part in parts if part and part.strip())
        return ""

    def _fallback_report(self, state: ResearchState, *, note: str) -> str:
        ticker = state["ticker"].upper()
        financial_data = state.get("financial_data", {})
        filings_context = state.get("filings_context", {})
        evidence = state.get("retrieved_evidence", [])
        warnings = state.get("warnings", [])
        metrics = financial_data.get("metrics", {})

        report_lines = [
            f"# {ticker} Research Draft",
            "",
            "## Workflow Mode",
            f"- Execution mode: {state.get('execution_mode', 'sequential')}",
            f"- Azure OpenAI configured: {'yes' if self.settings.azure_openai_endpoint else 'no'}",
            "",
            "## Financial Data",
            f"- Data status: {financial_data.get('data_status', 'missing')}",
            f"- Company: {metrics.get('company_name') or 'unknown'}",
            f"- Current price: {metrics.get('current_price')}",
            f"- Market cap: {metrics.get('market_cap')}",
            f"- Revenue: {metrics.get('revenue')}",
            f"- EPS: {metrics.get('eps')}",
            f"- 1M price change (%): {metrics.get('one_month_price_change_pct')}",
            "",
            "## Filings RAG",
            f"- Blob target: {filings_context.get('blob_target', 'missing')}",
            f"- Search target: {filings_context.get('search_target', 'missing')}",
            f"- Ingestion status: {filings_context.get('ingestion_status', 'missing')}",
            "",
            "## Evidence",
        ]

        if evidence:
            for item in evidence:
                report_lines.append(
                    f"- {item['source']}: {item['snippet']} ({item['relevance']})"
                )
        else:
            report_lines.append("- No evidence retrieved yet.")

        report_lines.extend(
            [
                "",
                "## Recommendation Stub",
                "- Use this report as a smoke-test artifact until richer SEC ingestion is added.",
                f"- Note: {note}",
            ]
        )

        if warnings:
            report_lines.extend(["", "## Warnings"])
            report_lines.extend(f"- {warning}" for warning in warnings)

        return "\n".join(report_lines)
