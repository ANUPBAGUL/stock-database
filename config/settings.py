import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Multibagger Intelligence System"
    ENV: str = "development"
    
    # Database Settings (Defaults to SQLite for local development, supports PostgreSQL)
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/multibagger.db"
    
    # Data Storage Paths
    RAW_DATA_DIR: Path = BASE_DIR / "data" / "raw"
    PARQUET_DATA_DIR: Path = BASE_DIR / "data" / "parquet"
    
    # Data Source: Yahoo Finance (primary, free, no auth)
    YFINANCE_RATE_LIMIT_SECONDS: float = float(os.getenv("YFINANCE_RATE_LIMIT_SECONDS", "2.0"))
    
    # Unit Convention: all financial values stored in this unit
    UNIT_CONVENTION: str = os.getenv("UNIT_CONVENTION", "CRORES")
    
    # Third-Party APIs (optional)
    UPSTOX_API_KEY: str = os.getenv("UPSTOX_API_KEY", "")
    UPSTOX_API_SECRET: str = os.getenv("UPSTOX_API_SECRET", "")
    TRENDLYNE_API_KEY: str = os.getenv("TRENDLYNE_API_KEY", "")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure directories exist
settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.PARQUET_DATA_DIR.mkdir(parents=True, exist_ok=True)
