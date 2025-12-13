"""
Configuration management for Azure Cost Analyzer

CHANGES:
1. REMOVED: azure_tenant_id, azure_client_id, azure_client_secret
   - These are now provided dynamically by users through the UI
   
2. REMOVED: subscription_main, subscription_prod, subscription_dev, subscription_test
   - Users now define their own subscription list with custom names
   
3. KEPT: Application-level settings (API config, CORS, output directory)
   - These are deployment-specific, not user-specific

Logic:
- Configuration is now split into two layers:
  1. Application config (this file): Server settings, loaded from .env
  2. User config (configuration_manager.py): Credentials and subscriptions, provided via UI
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application-level settings (deployment configuration).
    
    User-specific settings (credentials, subscriptions) are now handled
    by the ConfigurationManagerService and provided through the UI.
    """
    
    # API Configuration
    api_title: str = "Azure Cost Analyzer API"
    api_version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # CORS Configuration
    # In production, specify exact origins instead of "*"
    cors_origins: list = ["http://localhost:3000", "http://localhost:8000", "*"]
    
    # Output Configuration
    # Directory where generated reports are saved
    output_directory: str = "outputs"
    
    # Session Configuration
    # Maximum session duration in minutes (default: 30 minutes)
    session_timeout_minutes: int = 30
    
    # Rate Limiting
    # Maximum requests per minute for config endpoints
    config_endpoint_rate_limit: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to avoid re-reading .env file on every request.
    """
    return Settings()