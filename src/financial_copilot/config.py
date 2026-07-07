from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional until dependencies are installed
    load_dotenv = None


@dataclass(slots=True)
class Settings:
    azure_subscription_id: str | None = None
    azure_resource_group: str | None = None
    azure_location: str = "eastus"
    azure_openai_endpoint: str | None = None
    azure_openai_model: str = "gpt-4o-mini"
    azure_openai_api_key: str | None = None
    azure_openai_max_completion_tokens: int = 1200
    azure_search_endpoint: str | None = None
    azure_search_index_name: str = "financial-filings"
    azure_search_api_key: str | None = None
    azure_storage_account_url: str | None = None
    azure_storage_container: str = "filings"
    azure_blob_only_ingestion: bool = False
    azure_key_vault_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        if load_dotenv is not None:
            load_dotenv()

        return cls(
            azure_subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
            azure_resource_group=os.getenv("AZURE_RESOURCE_GROUP"),
            azure_location=os.getenv("AZURE_LOCATION", "eastus"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_model=os.getenv("AZURE_OPENAI_MODEL", "gpt-4o-mini"),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_max_completion_tokens=int(
                os.getenv("AZURE_OPENAI_MAX_COMPLETION_TOKENS", "1200")
            ),
            azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            azure_search_index_name=os.getenv(
                "AZURE_SEARCH_INDEX_NAME", "financial-filings"
            ),
            azure_search_api_key=os.getenv("AZURE_SEARCH_API_KEY"),
            azure_storage_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL"),
            azure_storage_container=os.getenv("AZURE_STORAGE_CONTAINER", "filings"),
            azure_blob_only_ingestion=os.getenv("AZURE_BLOB_ONLY_INGESTION", "false").lower() in ("1", "true", "yes"),
            azure_key_vault_url=os.getenv("AZURE_KEY_VAULT_URL"),
        )

    def missing_foundational_services(self) -> list[str]:
        missing: list[str] = []
        if not self.azure_openai_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.azure_search_endpoint:
            missing.append("AZURE_SEARCH_ENDPOINT")
        if not self.azure_storage_account_url:
            missing.append("AZURE_STORAGE_ACCOUNT_URL")
        return missing

    def azure_ready_summary(self) -> dict[str, bool]:
        return {
            "openai": bool(self.azure_openai_endpoint),
            "search": bool(self.azure_search_endpoint),
            "storage": bool(self.azure_storage_account_url),
            "key_vault": bool(self.azure_key_vault_url),
        }

    def search_auth_mode(self) -> str:
        if self.azure_search_api_key:
            return "api_key"
        return "default_azure_credential"
