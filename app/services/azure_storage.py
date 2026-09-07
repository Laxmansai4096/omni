"""
Azure Blob Storage Service
Enterprise Forward Deployed Engineering (FDE) document and artifact lifecycle management.
"""

import os
import io
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
from app.config import settings
from app.services.telemetry import trace_span

logger = logging.getLogger("azure_storage")
logger.setLevel(logging.INFO)

class AzureBlobStorageService:
    def __init__(self):
        self._service_client: Optional[BlobServiceClient] = None
        self._container_name = settings.AZURE_STORAGE_CONTAINER_NAME
        self._initialized = False
        self._init_client()

    def _init_client(self):
        conn_str = settings.AZURE_STORAGE_CONNECTION_STRING
        if not conn_str:
            logger.warning("[AzureStorage] AZURE_STORAGE_CONNECTION_STRING not configured. Using local fallback.")
            return

        try:
            self._service_client = BlobServiceClient.from_connection_string(conn_str)
            # Ensure container exists
            container_client = self._service_client.get_container_client(self._container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"[AzureStorage] Created container: {self._container_name}")
            self._initialized = True
            logger.info("[AzureStorage] Successfully connected to Azure Blob Storage.")
        except Exception as e:
            logger.error(f"[AzureStorage] Initialization error: {e}")
            self._service_client = None

    @property
    def is_configured(self) -> bool:
        return self._initialized and (self._service_client is not None)

    def upload_document(self, file_bytes: bytes, filename: str, doc_id: str) -> Tuple[str, str]:
        """
        Uploads document bytes to Azure Blob Storage.
        Returns: (blob_name, blob_url_or_sas)
        """
        extension = os.path.splitext(filename)[1].lower() or ".bin"
        blob_name = f"{doc_id}/{filename}"

        with trace_span("azure.blob.upload", {"doc_id": doc_id, "file_name": filename, "bytes": len(file_bytes)}):
            if self.is_configured:
                try:
                    blob_client = self._service_client.get_blob_client(
                        container=self._container_name,
                        blob=blob_name
                    )
                    content_type = "application/pdf" if extension == ".pdf" else "image/png"
                    blob_client.upload_blob(file_bytes, overwrite=True)
                    logger.info(f"[AzureStorage] Uploaded {blob_name} ({len(file_bytes)} bytes)")
                    
                    sas_url = self.generate_sas_url(blob_name)
                    return blob_name, sas_url or blob_client.url
                except Exception as e:
                    logger.error(f"[AzureStorage] Upload error: {e}")
            
            # Local fallback
            fallback_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
            os.makedirs(fallback_dir, exist_ok=True)
            local_path = os.path.join(fallback_dir, f"{doc_id}_{filename}")
            with open(local_path, "wb") as f:
                f.write(file_bytes)
            return blob_name, f"/static/uploads/{doc_id}_{filename}"

    def download_document(self, blob_name: str) -> Optional[bytes]:
        """Downloads document bytes from Azure Blob Storage."""
        with trace_span("azure.blob.download", {"blob_name": blob_name}):
            if self.is_configured:
                try:
                    blob_client = self._service_client.get_blob_client(
                        container=self._container_name,
                        blob=blob_name
                    )
                    return blob_client.download_blob().readall()
                except Exception as e:
                    logger.error(f"[AzureStorage] Download error for {blob_name}: {e}")
            
            # Local fallback check
            filename = os.path.basename(blob_name)
            doc_id = os.path.dirname(blob_name)
            fallback_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "static", "uploads", f"{doc_id}_{filename}"
            )
            if os.path.exists(fallback_path):
                with open(fallback_path, "rb") as f:
                    return f.read()
            return None

    def generate_sas_url(self, blob_name: str, expiry_hours: int = 4) -> Optional[str]:
        """Generates a secure SAS URL with read permissions for UI rendering."""
        if not self.is_configured:
            return None

        try:
            account_name = self._service_client.account_name
            # Extract key from connection string
            account_key = None
            for part in settings.AZURE_STORAGE_CONNECTION_STRING.split(";"):
                if part.startswith("AccountKey="):
                    account_key = part.split("AccountKey=")[1]
                    break

            if not account_key:
                return None

            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=self._container_name,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
            )
            return f"https://{account_name}.blob.core.windows.net/{self._container_name}/{blob_name}?{sas_token}"
        except Exception as e:
            logger.warning(f"[AzureStorage] Failed to generate SAS URL: {e}")
            return None

# Singleton storage service
storage_service = AzureBlobStorageService()
