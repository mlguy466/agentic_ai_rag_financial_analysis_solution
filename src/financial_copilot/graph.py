from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from financial_copilot.agents.filings_rag import filings_rag_agent
from financial_copilot.agents.financial_data import financial_data_agent
from financial_copilot.agents.metrics_analysis import metrics_analysis_agent
from financial_copilot.agents.risk_assessment import risk_assessment_agent
from financial_copilot.agents.reporting import report_agent
from financial_copilot.agents.supervisor import supervisor_agent
from financial_copilot.config import Settings
from financial_copilot.state import ResearchState

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - allows the scaffold to run before install
    END = "__end__"
    START = "__start__"
    StateGraph = None


AgentNode = Callable[[ResearchState, Settings], ResearchState]


def _merge_state(base: ResearchState, update: ResearchState) -> ResearchState:
    merged: dict[str, Any] = deepcopy(base)

    for key, value in update.items():
        existing = merged.get(key)
        if isinstance(existing, list) and isinstance(value, list):
            merged[key] = [*existing, *value]
        else:
            merged[key] = value

    return merged  # type: ignore[return-value]


def run_sequential_workflow(
    initial_state: ResearchState, settings: Settings
) -> ResearchState:
    state = deepcopy(initial_state)
    state["execution_mode"] = "sequential"

    nodes: list[AgentNode] = [
        supervisor_agent,
        financial_data_agent,
        filings_rag_agent,
        metrics_analysis_agent,
        risk_assessment_agent,
        report_agent,
    ]

    for node in nodes:
        state = _merge_state(state, node(state, settings))

    return state


def build_research_graph(settings: Settings):
    if StateGraph is None:
        return None

    graph = StateGraph(ResearchState)
    graph.add_node("supervisor_node", lambda state: supervisor_agent(state, settings))
    graph.add_node(
        "financial_data_node", lambda state: financial_data_agent(state, settings)
    )
    graph.add_node(
        "filings_rag_node", lambda state: filings_rag_agent(state, settings)
    )
    graph.add_node(
        "metrics_node", lambda state: metrics_analysis_agent(state, settings)
    )
    graph.add_node(
        "risk_node", lambda state: risk_assessment_agent(state, settings)
    )
    graph.add_node("report_node", lambda state: report_agent(state, settings))

    graph.add_edge(START, "supervisor_node")
    graph.add_edge("supervisor_node", "financial_data_node")
    graph.add_edge("financial_data_node", "filings_rag_node")
    graph.add_edge("filings_rag_node", "metrics_node")
    graph.add_edge("metrics_node", "risk_node")
    graph.add_edge("risk_node", "report_node")
    graph.add_edge("report_node", END)

    return graph.compile()


def run_research_workflow(initial_state: ResearchState, settings: Settings) -> ResearchState:
    workflow = build_research_graph(settings)
    if workflow is None:
        return run_sequential_workflow(initial_state, settings)

    state = deepcopy(initial_state)
    state["execution_mode"] = "langgraph"
    return workflow.invoke(state)
