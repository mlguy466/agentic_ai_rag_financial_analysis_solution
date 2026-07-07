from __future__ import annotations

from pathlib import Path

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

    def list_blob_names(self, prefix: str = "") -> list[str]:
        """List blob names in the configured container under the given prefix."""
        client = self.build_client()
        container_client = client.get_container_client(
            self.settings.azure_storage_container
        )
        if not container_client.exists():
            return []
        return [blob.name for blob in container_client.list_blobs(name_starts_with=prefix)]

    def upload_blob(self, blob_name: str, data: bytes) -> str:
        """Upload raw bytes to a blob in the configured container."""
        client = self.build_client()
        container_client = client.get_container_client(
            self.settings.azure_storage_container
        )
        if not container_client.exists():
            container_client.create_container()
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(data, overwrite=True)
        return blob_client.url

    def upload_text_blob(self, blob_name: str, text: str) -> str:
        """Upload a UTF-8 text payload as a blob."""
        return self.upload_blob(blob_name, text.encode("utf-8"))

    def upload_file_blob(self, blob_name: str, file_path: Path) -> str:
        """Upload a file from disk to the configured container."""
        client = self.build_client()
        container_client = client.get_container_client(
            self.settings.azure_storage_container
        )
        if not container_client.exists():
            container_client.create_container()
        blob_client = container_client.get_blob_client(blob_name)
        with file_path.open("rb") as fh:
            blob_client.upload_blob(fh, overwrite=True)
        return blob_client.url
