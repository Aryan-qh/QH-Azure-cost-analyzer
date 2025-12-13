"""
Azure Authentication Service

CHANGES:
1. REMOVED: Dependency on Settings class for credentials
   - Previously read from config.py/env file
   
2. ADDED: Constructor parameters for credentials
   - tenant_id, client_id, client_secret now passed as arguments
   
3. REMOVED: get_subscriptions() method
   - Subscriptions now come from user configuration, not hardcoded

Logic:
- Accept credentials as constructor parameters
- Generate access token using provided credentials
- No longer stores or manages subscription list
- Each instance is tied to specific user credentials
"""
import requests
from typing import Optional


class AzureAuthService:
    """
    Handle Azure AD authentication with user-provided credentials.
    
    SECURITY NOTE:
    - Never log or print credentials
    - Access tokens cached per instance
    - Credentials stored in memory only during object lifetime
    """
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        """
        Initialize Azure authentication service.
        
        Args:
            tenant_id: Azure AD Tenant ID (GUID)
            client_id: Azure AD Application/Client ID (GUID)
            client_secret: Azure AD Client Secret
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None
    
    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Get or refresh Azure AD access token.
        
        Args:
            force_refresh: If True, force token refresh even if cached
        
        Returns:
            Valid Azure access token
        
        Raises:
            Exception: If authentication fails
        """
        # Return cached token if available and not forcing refresh
        if self._access_token and not force_refresh:
            return self._access_token
        
        # Azure AD token endpoint
        auth_url = f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/token'
        
        # Request body for client credentials flow
        auth_data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'resource': 'https://management.azure.com/'
        }
        
        try:
            response = requests.post(auth_url, data=auth_data, timeout=30)
            response.raise_for_status()
            
            # Extract and cache access token
            self._access_token = response.json()['access_token']
            return self._access_token
            
        except requests.exceptions.HTTPError as e:
            # Handle specific authentication errors
            if e.response.status_code == 400:
                error_data = e.response.json()
                error_desc = error_data.get('error_description', 'Invalid credentials')
                raise Exception(f"Authentication failed: {error_desc}")
            elif e.response.status_code == 401:
                raise Exception("Authentication failed: Invalid client credentials")
            else:
                raise Exception(f"Authentication failed: HTTP {e.response.status_code}")
                
        except requests.exceptions.Timeout:
            raise Exception("Authentication failed: Request timed out")
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Authentication failed: {str(e)}")
        
        except KeyError:
            raise Exception("Authentication failed: Invalid response format")
    
    def test_connection(self) -> dict:
        """
        Test if credentials are valid by attempting to get access token.
        
        Returns:
            Dictionary with success status and message
        """
        try:
            self.get_access_token(force_refresh=True)
            return {
                'success': True,
                'message': 'Successfully authenticated with Azure'
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
    
    def clear_cached_token(self):
        """Clear cached access token (useful for logout or testing)"""
        self._access_token = None