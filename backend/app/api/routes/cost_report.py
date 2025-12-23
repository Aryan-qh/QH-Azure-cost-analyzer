# api/routes/cost_report.py
"""
Cost Report API Routes

Logic:
- Retrieve user config from session_id
- Extract credentials and subscriptions
- Generate report for all configured subscriptions
- Use subscription names from config in report
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.config import get_settings, Settings
from app.services.azure_auth import AzureAuthService
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService
from app.services.document_generator import DocumentGeneratorService
from app.services.configuration_manager import get_config_manager, ConfigurationManagerService
from app.models.responses import CostReportResponse
from pydantic import BaseModel, Field
import os
import time

router = APIRouter()


class CostReportRequest(BaseModel):
    """Request model for cost report generation"""
    session_id: str = Field(..., description="Session ID from configuration")
    num_days: int = Field(ge=1, le=90, description="Number of days to look back")


@router.post("/generate", response_model=CostReportResponse)
async def generate_cost_report(
    request: CostReportRequest,
    config_manager: ConfigurationManagerService = Depends(get_config_manager),
    settings: Settings = Depends(get_settings)
):
    """
    Generate a cost report Word document for configured subscriptions.
    
    Steps:
    1. Validate session and retrieve configuration
    2. Create authentication service with user credentials
    3. Fetch cost data for all configured subscriptions
    4. Generate Word document with tables and charts
    5. Return download URL
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
        
        # Initialize services
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
        
        cost_data_service = CostDataService(access_token)
        cost_processor = CostProcessorService()
        doc_generator = DocumentGeneratorService(settings.output_directory)
        
        print(f"\n{'='*60}")
        print(f"Cost Report Generation")
        print(f"Session ID: {request.session_id[:8]}...")
        print(f"Number of Days: {request.num_days}")
        print(f"Subscriptions: {len(config.subscriptions)}")
        print(f"{'='*60}\n")
        
        # Collect data for all configured subscriptions
        all_data = {}
        
        for idx, subscription in enumerate(config.subscriptions):
            print(f"Processing subscription {idx + 1}/{len(config.subscriptions)}: {subscription.name}")
            
            try:
                data = doc_generator.prepare_report_data(
                    subscription.id,
                    subscription.name,
                    request.num_days,
                    cost_data_service,
                    cost_processor
                )
                
                if data:
                    all_data[subscription.name] = data
                    print(f"  ✓ Data collected for {subscription.name}")
                else:
                    print(f"  ⚠ No data available for {subscription.name}")
            
            except Exception as e:
                print(f"  ✗ Error processing {subscription.name}: {str(e)}")
                # Continue with other subscriptions even if one fails
                continue
            
            # Add delay between subscriptions to avoid rate limiting
            # Skip delay after last subscription
            if idx < len(config.subscriptions) - 1:
                time.sleep(2)
        
        if not all_data:
            raise HTTPException(
                status_code=404,
                detail="No cost data available for any configured subscription"
            )
        
        # Generate document with dynamic subscription list
        filename = doc_generator.generate_cost_report(all_data, request.num_days)
        
        print(f"\n✓ Report generated: {filename}\n")
        
        return CostReportResponse(
            status="success",
            message=f"Cost report generated successfully for {request.num_days} days across {len(all_data)} subscription(s)",
            filename=filename,
            download_url=f"/api/cost-report/download/{filename}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        print(f"ERROR in cost report generation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate cost report: {str(e)}"
        )


@router.get("/download/{filename}")
async def download_report(
    filename: str,
    settings: Settings = Depends(get_settings)
):
    """
    Download a generated report.
    
    Security Note:
    - Validates filename to prevent directory traversal
    - Only serves files from configured output directory
    """
    
    # Prevent directory traversal
    if '/' in filename or '\\' in filename or '..' in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )
    
    filepath = os.path.join(settings.output_directory, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=404,
            detail="File not found. Report may have been deleted or expired."
        )
    
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )