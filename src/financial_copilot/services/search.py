from __future__ import annotations

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential
except ImportError:  # pragma: no cover - optional until dependencies are installed
    AzureKeyCredential = None
    DefaultAzureCredential = None

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
