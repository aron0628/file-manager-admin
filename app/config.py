from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://app_user:password@localhost:5432/app_db"
    PARSER_SERVER_URL: str = "http://localhost:9997"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_MIME_TYPES: list[str] = ["application/pdf"]
    PARSE_POLL_INTERVAL_SECONDS: int = 10
    PARSE_MAX_CONCURRENT_CHECKS: int = 20


settings = Settings()
