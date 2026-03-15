from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str = ""

    # Anthropic (Claude)
    anthropic_api_key: str

    # Nutritionix
    nutritionix_app_id: str = ""
    nutritionix_api_key: str = ""

    # YouTube
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
    secret_key: str = "change_me"

    # Defaults
    default_daily_water_ml: int = 3000
    default_calorie_deficit: int = 500

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
