"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings from environment."""

    DHAN_CLIENT_ID: str = os.getenv("DHAN_CLIENT_ID", "")
    DHAN_ACCESS_TOKEN: str = os.getenv("DHAN_ACCESS_TOKEN", "")
    DHAN_SANDBOX_MODE: bool = os.getenv("DHAN_SANDBOX_MODE", "true").lower() == "true"

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./trading.db")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # paper or live (derived from DHAN_SANDBOX_MODE)
    @property
    def TRADING_MODE(self) -> str:
        return "paper" if self.DHAN_SANDBOX_MODE else "live"


settings = Settings()
