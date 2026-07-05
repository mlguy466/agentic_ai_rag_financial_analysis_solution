# Azure-First Financial Analysis Copilot

This repository scaffolds a 4-agent financial research copilot built to learn `LangGraph` and core Azure services directly:

- `Supervisor Agent`
- `Financial Data Agent`
- `Filings RAG Agent`
- `Report Agent`

The first version is intentionally small: one ticker in, one research-style report out.

## Azure Services in Scope

- `Azure OpenAI` for reasoning and report generation
- `Azure Blob Storage` for raw filings and generated artifacts
- `Azure AI Search` for chunk indexing and retrieval
- `Azure Key Vault` for secrets later
- `Azure Container Apps` for deployment later

## Project Layout

```text
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

## Run

```bash
financial-copilot --ticker AAPL
```

Or:

```bash
python -m financial_copilot.main --ticker AAPL
```

## Cost-Safe Notes

- Start with a single resource group for the project.
- Set Azure budget alerts before provisioning more services.
- Keep the first AI Search index tiny.
- Run Container Apps only after the local Azure-connected workflow works.

## Recommended Next Steps

1. Provision Azure budget alerts, Blob Storage, Azure OpenAI, and Azure AI Search.
2. Replace placeholder tools with real market data and SEC ingestion.
3. Add Key Vault and managed identity.
4. Deploy the app to Azure Container Apps.
