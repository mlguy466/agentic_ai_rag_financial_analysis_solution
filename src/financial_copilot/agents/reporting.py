from __future__ import annotations

from financial_copilot.config import Settings
from financial_copilot.services.azure_openai import AzureOpenAIResearchWriter
from financial_copilot.state import ResearchState


def report_agent(state: ResearchState, settings: Settings) -> ResearchState:
    writer = AzureOpenAIResearchWriter(settings)
    report_markdown = writer.draft_report(state)

    return {
        "workflow_status": "completed",
        "report_markdown": report_markdown,
        "completed_steps": ["report_agent"],
    }

