"""
Configuration Manager Service

CHANGE: NEW FILE
Purpose: Handle dynamic user configurations in memory instead of .env files

Logic:
- Store configurations by session_id in memory
- Each config contains cloud provider, credentials, and subscription list
- Provides validation and secure handling of sensitive data
- Session-based storage allows multiple users without file conflicts
"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import secrets
import re


class SubscriptionConfig(BaseModel):
    """Single subscription configuration"""
    id: str = Field(..., description="Azure subscription ID (GUID format)")
    name: str = Field(..., description="Display name for the subscription")
    
    @validator('id')
    def validate_subscription_id(cls, v):
        """Validate subscription ID is a valid GUID"""
        guid_pattern = re.compile(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        )
        if not guid_pattern.match(v):
            raise ValueError('Subscription ID must be a valid GUID format')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        """Validate subscription name"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Subscription name cannot be empty')
        if len(v) > 100:
            raise ValueError('Subscription name too long (max 100 characters)')
        return v.strip()


class UserConfiguration(BaseModel):
    """User's cloud configuration"""
    cloud_provider: str = Field(..., description="Cloud provider (azure/gcp/aws)")
    tenant_id: str = Field(..., description="Azure AD Tenant ID")
    client_id: str = Field(..., description="Azure AD Client/Application ID")
    client_secret: str = Field(..., description="Azure AD Client Secret")
    subscriptions: List[SubscriptionConfig] = Field(..., description="List of subscriptions")
    created_at: datetime = Field(default_factory=datetime.now)
    
    @validator('cloud_provider')
    def validate_provider(cls, v):
        """Only Azure is supported currently"""
        if v.lower() != 'azure':
            raise ValueError('Only Azure is currently supported')
        return v.lower()
    
    @validator('tenant_id', 'client_id')
    def validate_guid(cls, v):
        """Validate GUID format for tenant_id and client_id"""
        guid_pattern = re.compile(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        )
        if not guid_pattern.match(v):
            raise ValueError('Must be a valid GUID format')
        return v
    
    @validator('client_secret')
    def validate_secret(cls, v):
        """Validate client secret is not empty"""
        if not v or len(v.strip()) == 0:
            raise ValueError('Client secret cannot be empty')
        return v
    
    @validator('subscriptions')
    def validate_subscriptions(cls, v):
        """Validate subscription list"""
        if not v or len(v) == 0:
            raise ValueError('At least one subscription is required')
        if len(v) > 20:
            raise ValueError('Maximum 20 subscriptions allowed')
        
        # Check for duplicate subscription IDs
        ids = [sub.id for sub in v]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate subscription IDs detected')
        
        # Check for duplicate names
        names = [sub.name.lower() for sub in v]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate subscription names detected')
        
        return v


class ConfigurationManagerService:
    """
    Manage user configurations in memory.
    
    IMPORTANT SECURITY NOTES:
    - Credentials stored in memory only (not persisted to disk)
    - Session IDs are cryptographically secure random tokens
    - Sessions expire after 30 minutes of inactivity
    - Never log or print credentials
    """
    
    # Session timeout (30 minutes)
    SESSION_TIMEOUT = timedelta(minutes=30)
    
    def __init__(self):
        # In-memory storage: {session_id: (config, last_accessed)}
        self._configs: Dict[str, tuple[UserConfiguration, datetime]] = {}
    
    def create_session(self, config_data: dict) -> str:
        """
        Create a new session with configuration.
        
        Args:
            config_data: Dictionary containing configuration fields
        
        Returns:
            session_id: Secure random session identifier
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate and create configuration object
        try:
            config = UserConfiguration(**config_data)
        except Exception as e:
            raise ValueError(f"Invalid configuration: {str(e)}")
        
        # Generate secure session ID
        session_id = secrets.token_urlsafe(32)
        
        # Store with current timestamp
        self._configs[session_id] = (config, datetime.now())
        
        # Clean up expired sessions
        self._cleanup_expired_sessions()
        
        return session_id
    
    def get_config(self, session_id: str) -> Optional[UserConfiguration]:
        """
        Retrieve configuration by session ID.
        
        Args:
            session_id: Session identifier
        
        Returns:
            UserConfiguration if session exists and is valid, None otherwise
        """
        if session_id not in self._configs:
            return None
        
        config, last_accessed = self._configs[session_id]
        
        # Check if session expired
        if datetime.now() - last_accessed > self.SESSION_TIMEOUT:
            del self._configs[session_id]
            return None
        
        # Update last accessed time
        self._configs[session_id] = (config, datetime.now())
        
        return config
    
    def update_session_activity(self, session_id: str) -> bool:
        """
        Update last activity timestamp for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if session exists and was updated, False otherwise
        """
        if session_id not in self._configs:
            return False
        
        config, _ = self._configs[session_id]
        self._configs[session_id] = (config, datetime.now())
        return True
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its configuration.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if session was deleted, False if not found
        """
        if session_id in self._configs:
            del self._configs[session_id]
            return True
        return False
    
    def validate_session(self, session_id: str) -> bool:
        """
        Check if a session exists and is valid.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if session is valid, False otherwise
        """
        return self.get_config(session_id) is not None
    
    def get_session_info(self, session_id: str) -> Optional[dict]:
        """
        Get non-sensitive session information.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Dictionary with session info (no credentials), or None if invalid
        """
        config = self.get_config(session_id)
        if not config:
            return None
        
        return {
            'cloud_provider': config.cloud_provider,
            'subscription_count': len(config.subscriptions),
            'subscription_names': [sub.name for sub in config.subscriptions],
            'created_at': config.created_at.isoformat(),
            'valid': True
        }
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions from memory"""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, (_, last_accessed) in self._configs.items()
            if now - last_accessed > self.SESSION_TIMEOUT
        ]
        
        for session_id in expired_sessions:
            del self._configs[session_id]
    
    def get_active_session_count(self) -> int:
        """Get count of active sessions"""
        self._cleanup_expired_sessions()
        return len(self._configs)


# Global instance
_config_manager = ConfigurationManagerService()


def get_config_manager() -> ConfigurationManagerService:
    """Get the global configuration manager instance"""
    return _config_manager