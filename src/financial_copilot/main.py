from __future__ import annotations

import argparse

from financial_copilot.config import Settings
from financial_copilot.graph import run_research_workflow
from financial_copilot.state import ResearchState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Azure-first financial analysis copilot."
    )
    parser.add_argument("--ticker", required=True, help="Ticker symbol to analyze")
    parser.add_argument(
        "--query",
        default="Generate a research-style summary with citations.",
        help="User request passed into the workflow",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    settings = Settings.from_env()
    initial_state: ResearchState = {
        "ticker": args.ticker.upper(),
        "query": args.query,
        "workflow_status": "created",
        "completed_steps": [],
        "retrieved_evidence": [],
        "warnings": [],
    }

    final_state = run_research_workflow(initial_state, settings)

    print(final_state.get("report_markdown", "No report produced."))


if __name__ == "__main__":
    main()
