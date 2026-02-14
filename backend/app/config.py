from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "ABLE"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://able:able_secret@localhost:15432/able"
    database_url_sync: str = "postgresql://able:able_secret@localhost:15432/able"

    # Redis
    redis_url: str = "redis://localhost:16379/0"

    # Security
    secret_key: str = "change-me-to-a-random-secret-key"
    encryption_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # SMTP (Email notifications)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@able-trading.com"
    smtp_use_tls: bool = True

    # DeepSeek AI (fallback when user hasn't configured LLM key)
    deepseek_api_key: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
