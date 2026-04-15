"""Настройки бота: ключи и URL из окружения (.env)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parent.parent
_BOT_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Переменные окружения для Telegram и OpenAI."""

    model_config = SettingsConfigDict(
        env_file=(_ROOT / ".env", _BOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    telegram_api_token: str
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    mcp_http_base_url: str = "http://127.0.0.1:8765"
    mcp_http_timeout: float = 60.0


settings = Settings()
