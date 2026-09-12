"""
Central application configuration.
All values are read from environment variables (with defaults for local dev).
Use a .env file locally — see .env.example.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — SQLite by default so unit tests run without Docker
    DATABASE_URL: str = "sqlite:///./dev.db"

    # JWT auth
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # Currency symbol for display (purely cosmetic; one currency per upload)
    CURRENCY_SYMBOL: str = "₹"
    ENVIRONMENT: str = "development"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
    ANALYSIS_ASYNC_THRESHOLD_ROWS: int = 2_000
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    MIN_PASSWORD_LENGTH: int = 12
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.ENVIRONMENT.lower() == "production" and len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters in production")
        if not self.SECRET_KEY:
            # Local-only fallback; production is rejected above.
            self.SECRET_KEY = "local-development-only-secret-key"
        if bool(self.GOOGLE_CLIENT_ID) != bool(self.GOOGLE_CLIENT_SECRET):
            raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured together")
        return self

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
