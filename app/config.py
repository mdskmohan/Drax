from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str = ""

    # ── LLM Provider ──────────────────────────────────────────────────────────
    # Set LLM_PROVIDER to: claude | openai | deepseek
    llm_provider: str = "claude"
    llm_main_model: str = ""   # leave blank to use provider default
    llm_fast_model: str = ""   # leave blank to use provider default

    # API keys — only the one matching your provider is required
    anthropic_api_key: str = ""   # provider=claude
    openai_api_key: str = ""      # provider=openai
    deepseek_api_key: str = ""    # provider=deepseek

    # Nutritionix (optional — accurate calorie/macro data)
    nutritionix_app_id: str = ""
    nutritionix_api_key: str = ""

    # YouTube Data API (optional — exercise tutorial videos)
    youtube_api_key: str = ""

    # Database
    database_url: str
    database_sync_url: str = ""

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    secret_key: str = "change_me_in_production"

    # Defaults
    default_daily_water_ml: int = 3000
    default_calorie_deficit: int = 500

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_async_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
