"""
Azure Authentication Service
"""
import requests
from typing import Optional
from app.config import Settings


class AzureAuthService:
    """Handle Azure AD authentication"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._access_token: Optional[str] = None
    
    def get_access_token(self) -> str:
        """Get or refresh Azure AD access token"""
        if self._access_token:
            return self._access_token
        
        auth_url = f'https://login.microsoftonline.com/{self.settings.azure_tenant_id}/oauth2/token'
        auth_data = {
            'grant_type': 'client_credentials',
            'client_id': self.settings.azure_client_id,
            'client_secret': self.settings.azure_client_secret,
            'resource': 'https://management.azure.com/'
        }
        
        try:
            response = requests.post(auth_url, data=auth_data, timeout=30)
            response.raise_for_status()
            self._access_token = response.json()['access_token']
            return self._access_token
        except Exception as e:
            raise Exception(f"Failed to authenticate with Azure AD: {str(e)}")
    
    def get_subscriptions(self) -> dict:
        """Get all configured subscriptions"""
        return {
            'main': self.settings.subscription_main,
            'prod': self.settings.subscription_prod,
            'dev': self.settings.subscription_dev,
            'test': self.settings.subscription_test
        }