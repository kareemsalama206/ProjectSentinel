from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ProjectSentinel"
    database_url: str = "sqlite:///./projectsentinel.db"
    cors_origins: list[str] = ["http://localhost:5176", "http://localhost:5173"]
    max_upload_size_bytes: int = 25 * 1024 * 1024
    max_extracted_files: int = 2_000
    max_extracted_size_bytes: int = 80 * 1024 * 1024
    max_scan_file_size_bytes: int = 1 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PROJECTSENTINEL_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
