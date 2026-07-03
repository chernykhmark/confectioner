from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    admin_telegram_id: int
    base_price: Decimal = Decimal("2500")

    # Stage 3
    session_timeout_min: int = 30      # брошенная сессия
    session_check_interval_min: int = 5  # интервал проверки

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()