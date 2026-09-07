import os
from functools import lru_cache
from typing import List, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application settings
    app_name: str = Field(default="kirana-ai-agent", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # LLM Provider settings
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3:1.7b", alias="OLLAMA_MODEL")
    ollama_timeout: int = Field(default=60, alias="OLLAMA_TIMEOUT")

    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="qwen/qwen-2.5-72b-instruct", alias="OPENROUTER_MODEL")
    openrouter_timeout: int = Field(default=60, alias="OPENROUTER_TIMEOUT")

    # Database settings
    database_url: str = Field(default="sqlite:///./data/kirana.db", alias="DATABASE_URL")
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")
    db_pool_pre_ping: bool = Field(default=True, alias="DB_POOL_PRE_PING")

    # Telegram settings
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_mode: str = Field(default="polling", alias="TELEGRAM_MODE")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")
    public_base_url: str = Field(default="", alias="PUBLIC_BASE_URL")

    # Server settings (for future API use)
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Agent settings
    agent_max_iterations: int = Field(default=15, alias="AGENT_MAX_ITERATIONS")

    # Timezone setting
    timezone: str = Field(default="Asia/Kolkata", alias="TIMEZONE")

    # Document storage settings
    document_storage: str = Field(default="local", alias="DOCUMENT_STORAGE")
    local_document_dir: str = Field(default="generated", alias="LOCAL_DOCUMENT_DIR")

    # CORS settings
    cors_origins: Union[List[str], str] = Field(default=["http://localhost:3000"], alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def parse_log_level(cls, v: str) -> str:
        from app.logging_config import validate_log_level
        return validate_log_level(v)

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        env = self.app_env.lower().strip()
        allowed_envs = ["development", "test", "staging", "production"]
        if env not in allowed_envs:
            raise ValueError(f"Invalid APP_ENV '{self.app_env}'. Allowed: {allowed_envs}")

        # Telegram mode checks
        mode = self.telegram_mode.lower().strip()
        allowed_modes = ["polling", "webhook"]
        if mode not in allowed_modes:
            raise ValueError(f"Invalid TELEGRAM_MODE '{self.telegram_mode}'. Allowed: {allowed_modes}")

        if mode == "webhook":
            if not self.telegram_webhook_secret.strip():
                raise ValueError("TELEGRAM_WEBHOOK_SECRET is required when TELEGRAM_MODE=webhook.")
            if not self.public_base_url.strip():
                raise ValueError("PUBLIC_BASE_URL is required when TELEGRAM_MODE=webhook.")
            if not self.public_base_url.lower().startswith("https://"):
                raise ValueError("PUBLIC_BASE_URL must start with 'https://' when TELEGRAM_MODE=webhook.")

        # Production strictness checks
        if env == "production":
            if self.debug:
                raise ValueError("DEBUG must be False in production environment.")
            if self.log_level == "DEBUG":
                raise ValueError("LOG_LEVEL cannot be DEBUG in production environment.")
            if self.llm_provider.lower().strip() == "openrouter" and not self.openrouter_api_key.strip():
                raise ValueError("OPENROUTER_API_KEY is required in production when LLM_PROVIDER=openrouter.")

        return self

    def __repr__(self) -> str:
        data = self.model_dump()
        if data.get("openrouter_api_key"):
            data["openrouter_api_key"] = "***MASKED***"
        if data.get("telegram_bot_token"):
            data["telegram_bot_token"] = "***MASKED***"
        if data.get("telegram_webhook_secret"):
            data["telegram_webhook_secret"] = "***MASKED***"
        return f"Settings({data})"



@lru_cache()
def get_settings() -> Settings:
    return Settings()

