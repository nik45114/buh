"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения"""

    # Telegram Bot
    BOT_TOKEN: str
    OWNER_TELEGRAM_ID: int
    ADMIN_TELEGRAM_IDS: str = "[]"
    ADMIN_CHAT_ID: int

    # Claude API
    CLAUDE_API_KEY: str
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "accounting"
    DB_USER: str = "accounting"
    DB_PASSWORD: str

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_KEY: str

    # Company
    COMPANY_NAME: str = 'ООО "Лепта"'
    COMPANY_INN: str = "6829164121"
    TAX_SYSTEM: str = "usn_income_expense"
    TAX_RATE: float = 0.15

    # Paths
    DOCUMENTS_PATH: str = "/app/documents"
    BACKUPS_PATH: str = "/backups"
    TEMPLATES_PATH: str = "/app/templates"

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def database_url(self) -> str:
        """URL подключения к базе данных"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def admin_ids(self) -> List[int]:
        """Список ID админов"""
        try:
            return json.loads(self.ADMIN_TELEGRAM_IDS)
        except:
            return []


settings = Settings()
