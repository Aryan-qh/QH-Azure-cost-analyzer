# models/responses.py
"""
Response Models
"""
from pydantic import BaseModel
from typing import List, Dict, Optional, Any


class CostReportResponse(BaseModel):
    """Response model for cost report"""
    status: str
    message: str
    filename: Optional[str] = None
    download_url: Optional[str] = None


class AnomalyResult(BaseModel):
    """Individual anomaly result"""
    category: str
    average_cost: float
    current_cost: float
    percent_change: float
    is_anomaly: bool


class SubscriptionAnomalyResult(BaseModel):
    """Anomaly results for a subscription"""
    subscription: str
    target_date: str
    start_date: str
    end_date: str
    threshold: float
    results: List[AnomalyResult]
    anomalies: List[Dict]
    has_anomalies: bool


class AnomalyDetectionResponse(BaseModel):
    """Response model for anomaly detection"""
    target_date: str
    threshold: float
    subscriptions: Dict[str, SubscriptionAnomalyResult]
    summary: Dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str