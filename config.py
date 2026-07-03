from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    admin_telegram_id: int
    base_price: Decimal = Decimal("2500")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()