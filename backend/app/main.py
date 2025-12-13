"""
FastAPI Application Entry Point

CHANGES:
1. ADDED: Configuration management endpoints
   - POST /api/config/save - Save user configuration
   - POST /api/config/test - Test credentials without saving
   - GET /api/config/validate - Check if session is valid
   - DELETE /api/config/clear - Clear configuration

2. ADDED: Import and use of ConfigurationManagerService

Logic:
- Configuration endpoints handle user credentials and subscriptions
- Test endpoint validates Azure credentials before saving
- Session-based configuration storage
- Enhanced error handling for configuration issues
"""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
from app.config import get_settings, Settings
from app.api.routes.cost_report import router as cost_report_router
from app.api.routes.anomaly_detection import router_anomaly
from app.models.responses import HealthResponse
from app.services.configuration_manager import get_config_manager, ConfigurationManagerService
from app.services.azure_auth import AzureAuthService
from pydantic import BaseModel, Field
from typing import Optional, List


# Configuration Request Models
class SubscriptionInput(BaseModel):
    """Subscription input model"""
    id: str = Field(..., description="Azure Subscription ID")
    name: str = Field(..., description="Display name for subscription")


class ConfigurationInput(BaseModel):
    """Configuration input model"""
    cloud_provider: str = Field(..., description="Cloud provider (azure/gcp/aws)")
    tenant_id: str = Field(..., description="Azure AD Tenant ID")
    client_id: str = Field(..., description="Azure AD Client ID")
    client_secret: str = Field(..., description="Azure AD Client Secret")
    subscriptions: List[SubscriptionInput] = Field(..., description="List of subscriptions")


class TestConnectionInput(BaseModel):
    """Test connection input model"""
    tenant_id: str
    client_id: str
    client_secret: str


class SessionRequest(BaseModel):
    """Session validation request"""
    session_id: str


# Initialize FastAPI app
def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="Azure Cost Analyzer - Monitor and analyze Azure costs with anomaly detection"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include existing routers
    app.include_router(
        cost_report_router,
        prefix="/api/cost-report",
        tags=["Cost Reports"]
    )
    
    app.include_router(
        router_anomaly,
        prefix="/api/anomaly",
        tags=["Anomaly Detection"]
    )
    
    # Configuration Endpoints
    
    @app.post("/api/config/save")
    async def save_configuration(
        config: ConfigurationInput,
        config_manager: ConfigurationManagerService = Depends(get_config_manager)
    ):
        """
        Save user configuration and create session.
        
        Steps:
        1. Validate configuration format
        2. Test Azure credentials
        3. Create session with configuration
        4. Return session ID
        """
        try:
            # Convert input to dict
            config_dict = config.dict()
            
            # Convert subscription inputs to proper format
            config_dict['subscriptions'] = [
                {'id': sub.id, 'name': sub.name}
                for sub in config.subscriptions
            ]
            
            # Test credentials before saving
            try:
                auth_service = AzureAuthService(
                    config.tenant_id,
                    config.client_id,
                    config.client_secret
                )
                auth_service.get_access_token()
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={
                        'status': 'error',
                        'message': f'Invalid credentials: {str(e)}'
                    }
                )
            
            # Create session
            session_id = config_manager.create_session(config_dict)
            
            return {
                'status': 'success',
                'message': 'Configuration saved successfully',
                'session_id': session_id,
                'subscription_count': len(config.subscriptions)
            }
            
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'Failed to save configuration: {str(e)}')
    
    @app.post("/api/config/test")
    async def test_connection(config: TestConnectionInput):
        """
        Test Azure credentials without saving configuration.
        
        Returns:
        - success: True if credentials are valid
        - message: Description of result
        """
        try:
            auth_service = AzureAuthService(
                config.tenant_id,
                config.client_id,
                config.client_secret
            )
            
            result = auth_service.test_connection()
            
            if result['success']:
                return {
                    'success': True,
                    'message': 'Connection successful! Credentials are valid.'
                }
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        'success': False,
                        'message': result['message']
                    }
                )
                
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={
                    'success': False,
                    'message': f'Connection failed: {str(e)}'
                }
            )
    
    @app.get("/api/config/validate")
    async def validate_session(
        session_id: str,
        config_manager: ConfigurationManagerService = Depends(get_config_manager)
    ):
        """
        Validate if a session ID is valid and active.
        
        Returns non-sensitive session information.
        """
        session_info = config_manager.get_session_info(session_id)
        
        if not session_info:
            return JSONResponse(
                status_code=404,
                content={
                    'valid': False,
                    'message': 'Session not found or expired'
                }
            )
        
        return session_info
    
    @app.delete("/api/config/clear")
    async def clear_configuration(
        request: SessionRequest,
        config_manager: ConfigurationManagerService = Depends(get_config_manager)
    ):
        """
        Clear a configuration session.
        
        Returns:
        - status: success or error
        - message: Description of result
        """
        deleted = config_manager.delete_session(request.session_id)
        
        if deleted:
            return {
                'status': 'success',
                'message': 'Configuration cleared successfully'
            }
        else:
            return JSONResponse(
                status_code=404,
                content={
                    'status': 'error',
                    'message': 'Session not found'
                }
            )
    
    @app.get("/api/config/stats")
    async def get_config_stats(
        config_manager: ConfigurationManagerService = Depends(get_config_manager)
    ):
        """
        Get statistics about active configurations (for monitoring).
        """
        return {
            'active_sessions': config_manager.get_active_session_count()
        }
    
    # Health check endpoint
    @app.get("/api/health", response_model=HealthResponse)
    async def health_check(settings: Settings = Depends(get_settings)):
        """Health check endpoint"""
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            version=settings.api_version
        )
    
    # Root endpoint
    @app.get("/")
    async def root(settings: Settings = Depends(get_settings)):
        """Root endpoint with API information"""
        return {
            "message": "Azure Cost Analyzer API",
            "version": settings.api_version,
            "docs": "/docs",
            "endpoints": {
                "health": "/api/health",
                "configuration": "/api/config/*",
                "anomaly_detection": "/api/anomaly/*",
                "cost_reports": "/api/cost-report/*"
            }
        }
    
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )