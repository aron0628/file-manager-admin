from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "app_db"
    DB_USER: str = "app_user"
    DB_PASSWORD: str = "password"

    UPLOAD_DIR: str = "uploads"
    PARSER_SERVER_URL: str = "http://localhost:9997"
    MAX_UPLOAD_SIZE_MB: int = 100
    ALLOWED_MIME_TYPES: list[str] = ["application/pdf"]
    PARSE_RESULT_DIR: str = "parse_results"
    PARSE_POLL_INTERVAL_SECONDS: int = 10
    PARSE_MAX_CONCURRENT_CHECKS: int = 20


settings = Settings()
