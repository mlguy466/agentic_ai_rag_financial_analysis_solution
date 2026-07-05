# Azure-First Financial Analysis Copilot

This repository contains an Azure-first financial research copilot built to learn `LangGraph` and core Azure services directly.

The current implementation is a `working smoke-test architecture` for one ticker at a time:

- `Supervisor Agent`
- `Financial Data Agent`
- `Filings RAG Agent`
- `Report Agent`

The current flow is:
- fetch live market/company data with `yfinance`
- build a seed research document
- upload it to `Azure Blob Storage`
- index and retrieve it from `Azure AI Search`
- generate a report with `Azure OpenAI` or fall back to a deterministic report if generation fails

## Azure Services in Scope

- `Azure OpenAI` for reasoning and report generation
- `Azure Blob Storage` for research artifacts and future filing storage
- `Azure AI Search` for indexing and retrieval
- `Azure Key Vault` for secrets and future secret management
- `Azure Container Apps` for deployment later

## Solution Architecture

```text
User CLI Request
    |
    v
LangGraph Workflow
    |
    +--> Supervisor Agent
    |       Plans the run and tracks workflow state
    |
    +--> Financial Data Agent
    |       Pulls live company data from yfinance
    |
    +--> Filings RAG Agent
    |       Builds a seed document from company data
    |       Uploads it to Azure Blob Storage
    |       Indexes it into Azure AI Search
    |       Retrieves evidence back from Search
    |
    +--> Report Agent
            Uses Azure OpenAI to write the report
            Falls back to a deterministic markdown report if needed
```

### Current RAG Design

- `Index type`: plain Azure AI Search text index
- `Search mode`: keyword/full-text search
- `Chunking now`: no real chunking yet
- `Current indexed unit`: one generated seed document per ticker

This is intentional for the current smoke-test phase. The next planned upgrade is:
- real SEC filing ingestion
- chunked documents
- richer metadata per chunk
- optional vector or hybrid retrieval

## Project Layout

```text
azure_services_validator.py
src/financial_copilot/
  agents/
  services/
  tools/
  config.py
  graph.py
  main.py
  state.py
```

## Local Setup

1. Create a virtual environment.
2. Activate the virtual environment.
3. Install the package in editable mode.
4. Copy `.env.example` to `.env`.
5. Sign in to Azure CLI for local keyless auth.
6. Fill in your Azure resource values.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
az login
cp .env.example .env
```

For this project, the virtual environment now exists at:

```bash
/Users/ashishsingh/Documents/my_projects/agentic_ai_rag_financial_analysis_solution/.venv
```

Activate it with:

```bash
source /Users/ashishsingh/Documents/my_projects/agentic_ai_rag_financial_analysis_solution/.venv/bin/activate
```

## Authentication Notes

`Azure AI Search` prefers `DefaultAzureCredential` for local development. In practice, that means you can:

```bash
az login
```

and run the app without setting `AZURE_SEARCH_API_KEY`.

Keep `AZURE_SEARCH_API_KEY` empty unless you intentionally want key-based authentication as a fallback.

For `Azure OpenAI`, the project is designed to support:
- `DefaultAzureCredential` / Entra ID
- `AZURE_OPENAI_API_KEY` as an optional fallback

If keyless Azure OpenAI still fails in your environment, using `AZURE_OPENAI_API_KEY` is the fastest way to continue testing while we keep improving the keyless path.

## Current State

What works today:
- LangGraph orchestration across 4 agents
- live company data with `yfinance`
- Azure Blob Storage connectivity
- Azure AI Search connectivity and document indexing
- Azure Key Vault connectivity

What is still a smoke-test implementation:
- the RAG agent uses a generated seed document instead of real SEC filings
- the search index is keyword-based, not vector-based
- report generation falls back gracefully if Azure OpenAI fails

## Validation

Validate environment variables only:

```bash
python3 azure_services_validator.py --validate-only
```

Validate Azure service connectivity:

```bash
python3 azure_services_validator.py --skip-openai
python3 azure_services_validator.py
```

## Run

```bash
financial-copilot --ticker AAPL
```

Or:

```bash
python -m financial_copilot.main --ticker AAPL
```

Recommended local smoke test:

```bash
source .venv/bin/activate
python3 azure_services_validator.py --skip-openai
PYTHONPATH=src python3 -m financial_copilot.main --ticker AAPL
```

## Cost-Safe Notes

- Start with a single resource group for the project.
- Set Azure budget alerts before provisioning more services.
- Keep the first AI Search index tiny.
- Run Container Apps only after the local Azure-connected workflow works.

## Recommended Next Steps

1. Replace the seed-document RAG path with real SEC filing ingestion.
2. Add chunking and per-chunk metadata in Azure AI Search.
3. Add vector or hybrid retrieval.
4. Harden Azure OpenAI keyless auth and deployment validation.
5. Deploy the app to Azure Container Apps.
