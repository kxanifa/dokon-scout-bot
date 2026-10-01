from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str = "1234567890:ABCDefGhIJKlmNoPQRsTUVwxyZ-12345"
    WEBHOOK_SECRET: str = "test_webhook_secret"
    PUBLIC_BASE_URL: str = "https://example.com"
    SUPERADMIN_ID: int = 0

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    SPREADSHEET_ID: str = ""
    DRIVE_ROOT_FOLDER_ID: str = ""

    ADMIN_GROUP_ID: int | None = None
    TZ: str = "Asia/Tashkent"
    NOMINATIM_USER_AGENT: str = "DokonScoutBot/1.0 (info@dokonscout.uz)"
    REDIS_URL: str | None = None
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
