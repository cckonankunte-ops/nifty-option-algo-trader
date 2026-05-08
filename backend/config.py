"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings from environment."""

    FYERS_APP_ID: str = os.getenv("FYERS_APP_ID", "")
    FYERS_SECRET_KEY: str = os.getenv("FYERS_SECRET_KEY", "")
    FYERS_REDIRECT_URI: str = os.getenv("FYERS_REDIRECT_URI", "")
    FYERS_ACCESS_TOKEN: str = os.getenv("FYERS_ACCESS_TOKEN", "")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./trading.db")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # paper or live
    TRADING_MODE: str = os.getenv("TRADING_MODE", "paper")


settings = Settings()
