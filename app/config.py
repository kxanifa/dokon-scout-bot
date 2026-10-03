from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str = "1234567890:ABCDefGhIJKlmNoPQRsTUVwxyZ-12345"
    WEBHOOK_SECRET: str = "test_webhook_secret"
    PUBLIC_BASE_URL: str = ""
    SUPERADMIN_ID: int = 1486347042
    SUPERADMIN_IDS: list[int] = [1486347042, 851362900, 544460229]

    def is_superadmin(self, user_id: int | None) -> bool:
        if not user_id:
            return False
        return user_id == self.SUPERADMIN_ID or user_id in self.SUPERADMIN_IDS

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

    @field_validator("ADMIN_GROUP_ID", mode="before")
    @classmethod
    def parse_admin_group_id(cls, v: Any) -> int | None:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return int(v)

    @field_validator("SUPERADMIN_IDS", mode="before")
    @classmethod
    def parse_superadmin_ids(cls, v: Any) -> list[int]:
        defaults = [1486347042, 851362900, 544460229]
        if v is None or v == "":
            return defaults
        if isinstance(v, list):
            res = [int(x) for x in v]
            for d in defaults:
                if d not in res:
                    res.append(d)
            return res
        if isinstance(v, str):
            res = [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
            for d in defaults:
                if d not in res:
                    res.append(d)
            return res
        return defaults

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def parse_redis_url(cls, v: Any) -> str | None:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return str(v)

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
