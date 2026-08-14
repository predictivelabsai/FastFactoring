from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str = Field(default="", alias="DB_URL")
    database_url_prod: str = Field(default="", alias="DATABASE_URL_PROD")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_secret: str = Field(default="change-me", alias="APP_SECRET")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")
    port: int = Field(default=5055, alias="PORT")

    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="", alias="GOOGLE_REDIRECT_URI")
    google_allowed_domains: str = Field(default="", alias="GOOGLE_ALLOWED_DOMAINS")
    google_allowed_emails: str = Field(default="", alias="GOOGLE_ALLOWED_EMAILS")

    # AI — Grok via x.ai (OpenAI-compatible API). Powers the chat-based loan
    # triage and investor-reporting assistants (see utils/ai.py).
    xai_api_key: str = Field(default="", alias="XAI_API_KEY")
    xai_model: str = Field(default="grok-4.3", alias="XAI_MODEL")
    xai_base_url: str = Field(default="https://api.x.ai/v1", alias="XAI_BASE_URL")
    ch_api_key: str = Field(default="", alias="CH_API_KEY")

    # Display currency for the demo. Stored amounts are UZS-scale and converted
    # to this currency for display via utils.money (default USD).
    display_currency: str = Field(default="USD", alias="DISPLAY_CURRENCY")

    @property
    def database_url(self) -> str:
        """Prefer the dedicated production database URL when configured."""
        return self.database_url_prod or self.db_url


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
