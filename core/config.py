"""Core configuration using Pydantic settings."""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Database Configuration
    database_url: str = Field(alias="DATABASE_URL")
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="etl_db", alias="DB_NAME")
    db_user: str = Field(default="postgres", alias="DB_USER")
    db_password: str = Field(default="postgres", alias="DB_PASSWORD")
    
    # API Keys (securely loaded from environment)
    api_key_source_1: str = Field(alias="API_KEY_SOURCE_1")
    api_key_source_2: Optional[str] = Field(default=None, alias="API_KEY_SOURCE_2")
    
    # API URLs
    api_url_source_1: str = Field(alias="API_URL_SOURCE_1")
    api_url_source_2: Optional[str] = Field(default=None, alias="API_URL_SOURCE_2")
    rss_feed_url: str = Field(alias="RSS_FEED_URL")
    
    # CSV Configuration
    csv_source_path: str = Field(default="./data/sample_data.csv", alias="CSV_SOURCE_PATH")
    
    # Application Settings
    app_name: str = Field(default="ETL Backend Service", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # API Server Configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    
    # ETL Settings
    etl_batch_size: int = Field(default=1000, alias="ETL_BATCH_SIZE")
    etl_rate_limit_calls: int = Field(default=100, alias="ETL_RATE_LIMIT_CALLS")
    etl_rate_limit_period: int = Field(default=60, alias="ETL_RATE_LIMIT_PERIOD")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
