from __future__ import annotations

try:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient
except ImportError:  # pragma: no cover - optional until dependencies are installed
    DefaultAzureCredential = None
    BlobServiceClient = None

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

    def build_client(self):
        if not self.settings.azure_storage_account_url:
            raise RuntimeError("AZURE_STORAGE_ACCOUNT_URL is not configured.")
        if BlobServiceClient is None or DefaultAzureCredential is None:
            raise RuntimeError(
                "Azure Blob dependencies are unavailable. Install project dependencies first."
            )
        return BlobServiceClient(
            account_url=self.settings.azure_storage_account_url,
            credential=DefaultAzureCredential(),
        )

    def ensure_container(self) -> str:
        client = self.build_client()
        container_client = client.get_container_client(
            self.settings.azure_storage_container
        )
        if not container_client.exists():
            container_client.create_container()
        return container_client.url

    def upload_text_blob(self, blob_name: str, text: str) -> str:
        client = self.build_client()
        container_client = client.get_container_client(
            self.settings.azure_storage_container
        )
        if not container_client.exists():
            container_client.create_container()
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(text.encode("utf-8"), overwrite=True)
        return blob_client.url
