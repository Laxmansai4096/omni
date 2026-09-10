import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
load_dotenv(override=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "Multimodal AI Document Intelligence Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    @property
    def AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT(self) -> str:
        return os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")

    @property
    def AZURE_DOCUMENT_INTELLIGENCE_KEY(self) -> str:
        return os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")

    @property
    def AZURE_TRANSLATOR_KEY(self) -> str:
        return os.getenv("AZURE_TRANSLATOR_KEY", "")

    @property
    def AZURE_TRANSLATOR_ENDPOINT(self) -> str:
        return os.getenv("AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com/")

    @property
    def AZURE_TRANSLATOR_REGION(self) -> str:
        return os.getenv("AZURE_TRANSLATOR_REGION", "eastus")

    @property
    def AZURE_OPENAI_ENDPOINT(self) -> str:
        return os.getenv("AZURE_OPENAI_ENDPOINT", "")

    @property
    def AZURE_OPENAI_KEY(self) -> str:
        return os.getenv("AZURE_OPENAI_KEY", "")

    @property
    def AZURE_OPENAI_DEPLOYMENT_NAME(self) -> str:
        return os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5-mini")

    @property
    def AZURE_STORAGE_CONNECTION_STRING(self) -> str:
        return os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")

    @property
    def AZURE_STORAGE_CONTAINER_NAME(self) -> str:
        return os.getenv("AZURE_STORAGE_CONTAINER_NAME", "raw-documents")

    @property
    def AZURE_SERVICE_BUS_CONNECTION_STRING(self) -> str:
        return os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING", "")

    @property
    def AZURE_SERVICE_BUS_QUEUE_NAME(self) -> str:
        return os.getenv("AZURE_SERVICE_BUS_QUEUE_NAME", "ai-jobs-queue")

    @property
    def AZURE_SERVICE_BUS_RESULTS_QUEUE(self) -> str:
        return os.getenv("AZURE_SERVICE_BUS_RESULTS_QUEUE", "ai-results-queue")

    @property
    def ENABLE_ASYNC_WORKER(self) -> bool:
        return os.getenv("ENABLE_ASYNC_WORKER", "true").lower() == "true"

    @property
    def APPLICATIONINSIGHTS_CONNECTION_STRING(self) -> str:
        return os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")

    @property
    def OTEL_SERVICE_NAME(self) -> str:
        return os.getenv("OTEL_SERVICE_NAME", "omnidoc-fde-platform")

    @property
    def MAX_CONCURRENT_USERS(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_USERS", "10"))

    @property
    def MAX_FILE_SIZE_MB(self) -> int:
        return int(os.getenv("MAX_FILE_SIZE_MB", "20"))

    @property
    def DEMO_MODE(self) -> bool:
        return os.getenv("DEMO_MODE", "false").lower() == "true"

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

settings = Settings()
