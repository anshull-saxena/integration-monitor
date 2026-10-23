import os
from pydantic import BaseModel, Field


class ServiceEndpointConfig(BaseModel):
    name: str
    base_url: str
    endpoint: str
    primary_key: str
    poll_interval_seconds: int = 10
    batch_size: int = 100
    timeout_seconds: float = 5.0
    max_retries: int = 3
    backoff_factor: float = 1.5


class AppConfig(BaseModel):
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/integration_warehouse"
        )
    )
    orders_service_url: str = Field(
        default_factory=lambda: os.getenv("ORDERS_SERVICE_URL", "http://localhost:8001")
    )
    supplier_service_url: str = Field(
        default_factory=lambda: os.getenv("SUPPLIER_SERVICE_URL", "http://localhost:8002")
    )
    shipments_service_url: str = Field(
        default_factory=lambda: os.getenv("SHIPMENTS_SERVICE_URL", "http://localhost:8003")
    )
    llm_provider: str = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "mock")
    )
    llm_api_key: str = Field(
        default_factory=lambda: os.getenv("LLM_API_KEY", "")
    )
    llm_model: str = Field(
        default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini")
    )
    validation_config_path: str = Field(
        default_factory=lambda: os.getenv("VALIDATION_CONFIG_PATH", "configs/validation_rules.yaml")
    )
    slack_webhook_url: str = Field(
        default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", "")
    )


settings = AppConfig()
