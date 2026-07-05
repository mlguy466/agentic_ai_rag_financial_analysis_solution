from __future__ import annotations

from financial_copilot.config import Settings


class BlobStorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe_target(self) -> str:
        if not self.settings.azure_storage_account_url:
            return "unconfigured://blob-storage"

        return (
            f"{self.settings.azure_storage_account_url}/"
            f"{self.settings.azure_storage_container}"
        )

