from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str = Field(default="", alias="DB_URL")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_secret: str = Field(default="change-me", alias="APP_SECRET")
    port: int = Field(default=5055, alias="PORT")

    # AI — Grok via x.ai (OpenAI-compatible API). Powers the chat-based loan
    # triage and investor-reporting assistants (see utils/ai.py).
    xai_api_key: str = Field(default="", alias="XAI_API_KEY")
    xai_model: str = Field(default="grok-4.3", alias="XAI_MODEL")
    xai_base_url: str = Field(default="https://api.x.ai/v1", alias="XAI_BASE_URL")
    ch_api_key: str = Field(default="", alias="CH_API_KEY")

    # Display currency for the demo. Stored amounts are UZS-scale and converted
    # to this currency for display via utils.money (default USD).
    display_currency: str = Field(default="USD", alias="DISPLAY_CURRENCY")


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
