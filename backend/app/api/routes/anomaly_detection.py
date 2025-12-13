# api/routes/anomaly_detection.py
"""
Anomaly Detection API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from app.config import get_settings, Settings
from app.services.azure_auth import AzureAuthService
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService
from app.services.anomaly_detector import AnomalyDetectorService
from app.models.requests import AnomalyDetectionRequest

router_anomaly = APIRouter()


@router_anomaly.post("/detect")
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    settings: Settings = Depends(get_settings)
):
    """Detect cost anomalies across subscriptions"""
    
    try:
        # Parse target date
        if request.target_date:
            target_date = datetime.strptime(request.target_date, '%Y-%m-%d')
        else:
            target_date = datetime.now() - timedelta(days=1)
        
        # Initialize services
        auth_service = AzureAuthService(settings)
        access_token = auth_service.get_access_token()
        subscriptions = auth_service.get_subscriptions()
        
        cost_data_service = CostDataService(access_token)
        cost_processor = CostProcessorService()
        anomaly_detector = AnomalyDetectorService(cost_data_service, cost_processor)
        
        # Check subscriptions
        results = anomaly_detector.check_all_subscriptions(
            subscriptions,
            target_date,
            request.threshold_percent
        )
        
        return results
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_anomaly.get("/history")
async def get_anomaly_history(
    days: int = 7,
    threshold: float = 25.0,
    settings: Settings = Depends(get_settings)
):
    """Get anomaly detection history for multiple days"""
    
    try:
        # Initialize services
        auth_service = AzureAuthService(settings)
        access_token = auth_service.get_access_token()
        subscriptions = auth_service.get_subscriptions()
        
        cost_data_service = CostDataService(access_token)
        cost_processor = CostProcessorService()
        anomaly_detector = AnomalyDetectorService(cost_data_service, cost_processor)
        
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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))