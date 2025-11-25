# api/routes/cost_report.py
"""
Cost Report API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.config import get_settings, Settings
from app.services.azure_auth import AzureAuthService
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService
from app.services.document_generator import DocumentGeneratorService
from app.models.requests import CostReportRequest
from app.models.responses import CostReportResponse
import os
import time

router = APIRouter()


@router.post("/generate", response_model=CostReportResponse)
async def generate_cost_report(
    request: CostReportRequest,
    settings: Settings = Depends(get_settings)
):
    """Generate a cost report Word document"""
    
    try:
        # Initialize services
        auth_service = AzureAuthService(settings)
        access_token = auth_service.get_access_token()
        subscriptions = auth_service.get_subscriptions()
        
        cost_data_service = CostDataService(access_token)
        cost_processor = CostProcessorService()
        doc_generator = DocumentGeneratorService(settings.output_directory)
        
        # Collect data for all subscriptions
        all_data = {}
        
        for idx, sub_name in enumerate(['main', 'prod', 'dev', 'test']):
            data = doc_generator.prepare_report_data(
                subscriptions[sub_name],
                sub_name,
                request.num_days,
                cost_data_service,
                cost_processor
            )
            
            if data:
                all_data[sub_name] = data
            
            # Add delay between subscriptions to avoid rate limiting
            if idx < 3:
                time.sleep(2)
        
        # Generate document
        filename = doc_generator.generate_cost_report(all_data, request.num_days)
        
        return CostReportResponse(
            status="success",
            message=f"Cost report generated successfully for {request.num_days} days",
            filename=filename,
            download_url=f"/api/cost-report/download/{filename}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_report(filename: str, settings: Settings = Depends(get_settings)):
    """Download a generated report"""
    
    filepath = os.path.join(settings.output_directory, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )

