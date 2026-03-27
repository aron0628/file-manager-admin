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
    PARSE_RESULT_DIR: str = "parse_results"

    # Auth
    SECRET_KEY: str = "dev-secret-key-change-in-production"


settings = Settings()
