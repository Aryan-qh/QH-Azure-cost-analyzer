"""
Configuration management for Azure Cost Analyzer
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Azure AD Configuration
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    
    # Subscription Configuration
    subscription_main: str
    subscription_prod: str
    subscription_dev: str
    subscription_test: str
    
    # API Configuration
    api_title: str = "Azure Cost Analyzer API"
    api_version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # CORS Configuration
    cors_origins: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Output Configuration
    output_directory: str = "outputs"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()