from __future__ import annotations

from financial_copilot.config import Settings
from financial_copilot.state import ResearchState


class AzureOpenAIResearchWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def draft_report(self, state: ResearchState) -> str:
        """Return a deterministic draft until the live Azure OpenAI call is wired."""
        ticker = state["ticker"].upper()
        financial_data = state.get("financial_data", {})
        filings_context = state.get("filings_context", {})
        evidence = state.get("retrieved_evidence", [])
        warnings = state.get("warnings", [])

        report_lines = [
            f"# {ticker} Research Draft",
            "",
            "## Workflow Mode",
            f"- Execution mode: {state.get('execution_mode', 'sequential')}",
            f"- Azure OpenAI configured: {'yes' if self.settings.azure_openai_endpoint else 'no'}",
            "",
            "## Financial Data",
            f"- Data status: {financial_data.get('data_status', 'missing')}",
            f"- Metrics requested: {', '.join(financial_data.get('metrics_requested', [])) or 'none'}",
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
                "- Recommendation pending live financial data and real filings retrieval.",
                "- Next implementation step: wire Azure OpenAI Responses API for final narrative generation.",
            ]
        )

        if warnings:
            report_lines.extend(["", "## Warnings"])
            report_lines.extend(f"- {warning}" for warning in warnings)

        return "\n".join(report_lines)

