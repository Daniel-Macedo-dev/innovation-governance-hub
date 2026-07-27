from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    app_timezone: str = "America/Sao_Paulo"
    database_url: str = "sqlite:///data/innovation_governance_hub.db"
    upload_dir: Path = Path("data/uploads")
    log_level: str = "INFO"
    demo_company_name: str = "Horizonte Operações Integradas"
    stale_project_days: int = 14
    budget_warning_percent: int = 80
    annual_budget_warning_percent: int = 85
    integration_api_token: str = "change-me-local"
    integration_api_host: str = "0.0.0.0"
    integration_api_port: int = 8000
    n8n_enabled: bool = False
    n8n_webhook_url: str = ""
    n8n_callback_token: str = ""
    n8n_request_timeout_seconds: int = 10
    demo_reference_date: date | None = None
    interview_guide_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
