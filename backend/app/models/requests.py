# models/requests.py
"""
Request Models
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class CostReportRequest(BaseModel):
    """Request model for cost report generation"""
    num_days: int = Field(ge=1, le=90, description="Number of days to look back")


class AnomalyDetectionRequest(BaseModel):
    """Request model for anomaly detection"""
    target_date: Optional[str] = Field(None, description="Target date in YYYY-MM-DD format")
    threshold_percent: float = Field(25.0, ge=0, le=100, description="Anomaly threshold percentage")
    subscriptions: Optional[list[str]] = Field(None, description="List of subscriptions to check")


