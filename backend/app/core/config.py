"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Duet API"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/v1"
    allowed_hosts: list[str] = ["*"]

    # Security
    secret_key: str = Field(default="change-me-in-production", repr=False)
    access_token_ttl_minutes: int = 60 * 24 * 7  # 7 days
    refresh_token_ttl_days: int = 30
    algorithm: str = "HS256"
    password_min_length: int = 8
    bcrypt_rounds: int = 12

    # Database
    database_url: str = "mysql+pymysql://duet:duet@localhost:3306/duet"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate limiting
    rate_limit_default_per_minute: int = 120
    rate_limit_auth_per_minute: int = 10
    rate_limit_ws_per_minute: int = 600

    # Media / object storage
    media_storage_backend: str = "local"  # local | s3
    media_local_path: str = "media"
    media_max_upload_bytes: int = 100 * 1024 * 1024  # 100 MiB
    media_s3_bucket: str = "duet-media"
    media_s3_region: str = "us-east-1"
    media_presign_ttl_seconds: int = 3600

    # APNs
    apns_enabled: bool = False
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_bundle_id: str = "com.duet.app"
    apns_key_path: str = ""

    # Streaks
    streak_timezone: str = "UTC"
    streak_grace_seconds: int = 0
    streak_freezes_enabled: bool = True
    streak_milestones: list[int] = [7, 30, 100, 365, 500, 1000]

    # Websocket
    ws_presence_ttl_seconds: int = 30
    ws_typing_ttl_seconds: int = 15
    ws_max_payload_bytes: int = 64 * 1024

    # Pagination
    default_page_size: int = 30
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()