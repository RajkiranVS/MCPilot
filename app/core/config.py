"""
MCPilot — Centralised Settings
All config loaded from .env — never hardcoded.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_name: str = "MCPilot"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Auth (BUILD-002)
    secret_key: str = "change-me-before-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Database (BUILD-007)
    database_url: str = "postgresql://postgres:password@localhost:5432/mcpilot"

    # Anthropic
    anthropic_api_key: str = ""

    # AWS (Week 3)
    aws_region: str = "us-east-1"
    aws_sagemaker_phi_endpoint: str = ""
    aws_bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"

    # ── LLM Provider ──────────────────────────────────────────────────────────
    llm_provider:  str = "ollama"
    ollama_url:    str = "http://localhost:11434"
    ollama_model:  str = "llama3.2"

    # Rate limiting (BUILD-004)
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()