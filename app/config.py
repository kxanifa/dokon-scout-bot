from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str = "1234567890:ABCDefGhIJKlmNoPQRsTUVwxyZ-12345"
    WEBHOOK_SECRET: str = "test_webhook_secret"
    PUBLIC_BASE_URL: str = ""
    SUPERADMIN_ID: int = 1486347042

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

    def model_post_init(self, __context):
        if not self.PUBLIC_BASE_URL or "example.com" in self.PUBLIC_BASE_URL:
            import os

            render_url = os.getenv("RENDER_EXTERNAL_URL")
            if render_url:
                self.PUBLIC_BASE_URL = render_url.rstrip("/")
            else:
                render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
                if render_host:
                    self.PUBLIC_BASE_URL = f"https://{render_host}".rstrip("/")
                else:
                    self.PUBLIC_BASE_URL = "https://example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
