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

    # AI Model config (admin-configurable, future: admin dashboard)
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    daily_report_model: str = "gpt-4o"  # "gpt-4o" | "deepseek-chat" | "claude-sonnet"

    # Schedule config (KST 기준, 사용자 조정 가능)
    schedule_briefing_hour: int = 6       # 아침 브리핑 시각 (기본: 06:30)
    schedule_briefing_minute: int = 30
    schedule_agent_open_hour: int = 8     # 장 시작 에이전트 (NXT 프리마켓 08:00)
    schedule_agent_open_minute: int = 0
    schedule_agent_midday_hour: int = 12  # 점심 점검 (12:30)
    schedule_agent_midday_minute: int = 30
    schedule_price_interval_minutes: int = 1  # 포지션 가격 업데이트 간격 (분)
    schedule_price_start_hour: int = 8    # 가격 업데이트 시작 시각
    schedule_price_end_hour: int = 16     # 가격 업데이트 종료 시각
    schedule_recipe_interval_minutes: int = 5   # 레시피 모니터링 간격 (분)
    schedule_recipe_start_hour: int = 8         # 레시피 모니터링 시작 시각
    schedule_recipe_end_hour: int = 16          # 레시피 모니터링 종료 시각
    schedule_condition_interval_minutes: int = 10  # 조건검색 폴링 간격 (분)
    schedule_condition_start_hour: int = 9      # 조건검색 시작 시각
    schedule_condition_end_hour: int = 15       # 조건검색 종료 시각
    schedule_factor_interval_minutes: int = 30  # 팩터 수집 간격 (분)
    schedule_factor_start_hour: int = 9         # 팩터 수집 시작 시각
    schedule_factor_end_hour: int = 16          # 팩터 수집 종료 시각

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
