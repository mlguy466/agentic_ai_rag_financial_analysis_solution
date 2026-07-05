from __future__ import annotations

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex,
        SearchFieldDataType,
        SearchableField,
        SimpleField,
    )
except ImportError:  # pragma: no cover - optional until dependencies are installed
    AzureKeyCredential = None
    DefaultAzureCredential = None
    SearchClient = None
    SearchIndexClient = None
    SearchFieldDataType = None
    SearchIndex = None
    SearchableField = None
    SimpleField = None

from financial_copilot.config import Settings


class SearchIndexService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe_target(self) -> str:
        if not self.settings.azure_search_endpoint:
            return "unconfigured://azure-search"

        return (
            f"{self.settings.azure_search_endpoint}/"
            f"indexes/{self.settings.azure_search_index_name}"
        )

    def describe_auth_mode(self) -> str:
        return self.settings.search_auth_mode()

    def build_credential(self):
        """Prefer Entra ID; use an API key only when one is explicitly configured."""
        if self.settings.azure_search_api_key:
            if AzureKeyCredential is None:
                raise RuntimeError(
                    "azure-core is unavailable. Install project dependencies first."
                )
            return AzureKeyCredential(self.settings.azure_search_api_key)

        if DefaultAzureCredential is None:
            raise RuntimeError(
                "azure-identity is unavailable. Install project dependencies first."
            )
        return DefaultAzureCredential()

    def build_index_client(self):
        if not self.settings.azure_search_endpoint:
            raise RuntimeError("AZURE_SEARCH_ENDPOINT is not configured.")
        if SearchIndexClient is None:
            raise RuntimeError(
                "Azure AI Search dependencies are unavailable. Install project dependencies first."
            )
        return SearchIndexClient(
            endpoint=self.settings.azure_search_endpoint,
            credential=self.build_credential(),
        )

    def build_search_client(self):
        if not self.settings.azure_search_endpoint:
            raise RuntimeError("AZURE_SEARCH_ENDPOINT is not configured.")
        if SearchClient is None:
            raise RuntimeError(
                "Azure AI Search dependencies are unavailable. Install project dependencies first."
            )
        return SearchClient(
            endpoint=self.settings.azure_search_endpoint,
            index_name=self.settings.azure_search_index_name,
            credential=self.build_credential(),
        )

    def ensure_index(self) -> str:
        index_client = self.build_index_client()
        index_name = self.settings.azure_search_index_name

        try:
            index_client.get_index(index_name)
        except Exception:
            if SearchIndex is None or SearchFieldDataType is None:
                raise RuntimeError("Azure AI Search models are unavailable.")

            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(
                    name="ticker", type=SearchFieldDataType.String, filterable=True
                ),
                SearchableField(name="source", type=SearchFieldDataType.String),
                SearchableField(name="content", type=SearchFieldDataType.String),
            ]
            index = SearchIndex(name=index_name, fields=fields)
            index_client.create_index(index)

        return index_name

    def upload_documents(self, documents: list[dict]) -> dict:
        client = self.build_search_client()
        return client.upload_documents(documents=documents)

    def search(self, query: str, top: int = 3) -> list[dict]:
        client = self.build_search_client()
        results = client.search(search_text=query, top=top)
        return [dict(item) for item in results]
