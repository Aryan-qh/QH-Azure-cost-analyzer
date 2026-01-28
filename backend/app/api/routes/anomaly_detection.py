# api/routes/anomaly_detection.py
"""
Anomaly Detection API Routes

Logic:
- Retrieve user config from session_id
- Extract credentials and subscriptions from config
- Create AzureAuthService with user's credentials
- Process user's subscription list dynamically
- Return results for all configured subscriptions
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from app.config import get_settings, Settings
from app.services.azure_auth import AzureAuthService
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService
from app.services.anomaly_detector import AnomalyDetectorService
from app.services.configuration_manager import get_config_manager, ConfigurationManagerService
from pydantic import BaseModel, Field
from typing import Optional

router_anomaly = APIRouter()


class AnomalyDetectionRequest(BaseModel):
    """Request model for anomaly detection"""
    session_id: str = Field(..., description="Session ID from configuration")
    target_date: Optional[str] = Field(None, description="Target date in YYYY-MM-DD format")
    threshold_percent: float = Field(25.0, ge=0, le=100, description="Anomaly threshold percentage")


@router_anomaly.post("/detect")
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    config_manager: ConfigurationManagerService = Depends(get_config_manager),
    settings: Settings = Depends(get_settings)
):
    """
    Detect cost anomalies across configured subscriptions.
    
    Steps:
    1. Validate session and retrieve configuration
    2. Parse target date (default to yesterday)
    3. Create authentication service with user credentials
    4. Initialize cost data and anomaly detection services
    5. Check all configured subscriptions
    6. Return aggregated results
    """
    
    try:
        # Retrieve configuration from session
        config = config_manager.get_config(request.session_id)
        
        if not config:
            raise HTTPException(
                status_code=401,
                detail="Session not found or expired. Please reconfigure your credentials."
            )
        
        # Update session activity
        config_manager.update_session_activity(request.session_id)
        
        # Parse target date
        if request.target_date:
            try:
                target_date = datetime.strptime(request.target_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD."
                )
        else:
            # Default to yesterday
            target_date = datetime.now() - timedelta(days=1)
        
        # Initialize Azure authentication with user credentials
        auth_service = AzureAuthService(
            config.tenant_id,
            config.client_id,
            config.client_secret
        )
        
        # Get access token
        try:
            access_token = auth_service.get_access_token()
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Authentication failed: {str(e)}"
            )
        
        # Initialize services
        cost_data_service = CostDataService(access_token)
        cost_processor = CostProcessorService()
        anomaly_detector = AnomalyDetectorService(cost_data_service, cost_processor)
        
        # Build subscription dictionary from user config
        # Convert from list of SubscriptionConfig objects to dict
        subscriptions = {
            sub.name: sub.id
            for sub in config.subscriptions
        }
        
        print(f"\n{'='*60}")
        print(f"Anomaly Detection Request")
        print(f"Session ID: {request.session_id[:8]}...")
        print(f"Target Date: {target_date.strftime('%Y-%m-%d')}")
        print(f"Threshold: {request.threshold_percent}%")
        print(f"Subscriptions: {len(subscriptions)}")
        print(f"{'='*60}\n")
        
        # Check all subscriptions
        results = anomaly_detector.check_all_subscriptions(
            subscriptions,
            target_date,
            request.threshold_percent
        )
        
        return results
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        print(f"ERROR in anomaly detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Anomaly detection failed: {str(e)}"
        )


@router_anomaly.get("/history")
async def get_anomaly_history(
    session_id: str,
    days: int = 7,
    threshold: float = 25.0,
    config_manager: ConfigurationManagerService = Depends(get_config_manager),
    settings: Settings = Depends(get_settings)
):
    """
    Get anomaly detection history for multiple days.
    
    Query Parameters:
    - session_id: Session identifier
    - days: Number of days to look back (default: 7)
    - threshold: Anomaly threshold percentage (default: 25.0)
    """
    
    try:
        # Retrieve configuration
        config = config_manager.get_config(session_id)
        
        if not config:
            raise HTTPException(
                status_code=401,
                detail="Session not found or expired. Please reconfigure your credentials."
            )
        
        # Update session activity
        config_manager.update_session_activity(session_id)
        
        # Initialize services
        auth_service = AzureAuthService(
            config.tenant_id,
            config.client_id,
            config.client_secret
        )
        
        access_token = auth_service.get_access_token()
        cost_data_service = CostDataService(access_token)
        cost_processor = CostProcessorService()
        anomaly_detector = AnomalyDetectorService(cost_data_service, cost_processor)
        
        # Build subscription dictionary
        subscriptions = {
            sub.name: sub.id
            for sub in config.subscriptions
        }
        
        # Check each day
        history = []
        for i in range(days, 0, -1):
            target_date = datetime.now() - timedelta(days=i)
            result = anomaly_detector.check_all_subscriptions(
                subscriptions,
                target_date,
                threshold
            )
            history.append(result)
        
        return {"history": history}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in anomaly history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve anomaly history: {str(e)}"
        )