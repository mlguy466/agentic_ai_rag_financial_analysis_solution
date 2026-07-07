from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict


class EvidenceChunk(TypedDict):
    source: str
    snippet: str
    relevance: str


class ResearchState(TypedDict, total=False):
    ticker: str
    query: str
    workflow_status: Literal["created", "planned", "running", "completed"]
    execution_mode: Literal["langgraph", "sequential"]
    planned_steps: list[str]
    completed_steps: Annotated[list[str], add]
    financial_data: dict[str, Any]
    filings_context: dict[str, Any]
    retrieved_evidence: Annotated[list[EvidenceChunk], add]
    report_markdown: str
    warnings: Annotated[list[str], add]
    analysis: dict[str, Any]
    risk_assessment: dict[str, Any]

