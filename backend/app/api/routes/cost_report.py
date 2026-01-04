# api/routes/cost_report.py
"""
Cost Report API Routes

CHANGE: Added anomaly detection to cost reports
- Now collects anomaly data for each day in the report period
- Passes anomaly results to document generator
- Uses same threshold as anomaly detection endpoint (25% by default)

Logic:
- Retrieve user config from session_id
- Extract credentials and subscriptions
- Generate cost data for all configured subscriptions
- Run anomaly detection for each day in the period
- Generate report with both cost tables and anomaly summary
- Use subscription names from config in report
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.config import get_settings, Settings
from app.services.azure_auth import AzureAuthService
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService
from app.services.document_generator import DocumentGeneratorService
from app.services.anomaly_detector import AnomalyDetectorService
from app.services.configuration_manager import get_config_manager, ConfigurationManagerService
from app.models.responses import CostReportResponse
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import os
import time

router = APIRouter()


class CostReportRequest(BaseModel):
    """Request model for cost report generation"""
    session_id: str = Field(..., description="Session ID from configuration")
    num_days: int = Field(ge=1, le=90, description="Number of days to look back")
    anomaly_threshold: float = Field(25.0, ge=0, le=100, description="Anomaly detection threshold percentage")


@router.post("/generate", response_model=CostReportResponse)
async def generate_cost_report(
    request: CostReportRequest,
    config_manager: ConfigurationManagerService = Depends(get_config_manager),
    settings: Settings = Depends(get_settings)
):
    """
    Generate a cost report Word document for configured subscriptions.
    
    NEW: Now includes anomaly detection results at the bottom of the report
    
    Steps:
    1. Validate session and retrieve configuration
    2. Create authentication service with user credentials
    3. Fetch cost data for all configured subscriptions
    4. Run anomaly detection for each day in the period (NEW)
    5. Generate Word document with cost tables and anomaly summary (UPDATED)
    6. Return download URL
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
        
        # NEW: Initialize anomaly detector
        anomaly_detector = AnomalyDetectorService(cost_data_service, cost_processor)
        
        print(f"\n{'='*60}")
        print(f"Cost Report Generation with Anomaly Detection")
        print(f"Session ID: {request.session_id[:8]}...")
        print(f"Number of Days: {request.num_days}")
        print(f"Anomaly Threshold: {request.anomaly_threshold}%")
        print(f"Subscriptions: {len(config.subscriptions)}")
        print(f"{'='*60}\n")
        
        # Step 1: Collect cost data for all configured subscriptions
        all_data = {}
        
        for idx, subscription in enumerate(config.subscriptions):
            print(f"Processing cost data {idx + 1}/{len(config.subscriptions)}: {subscription.name}")
            
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
                    print(f"  ✓ Cost data collected for {subscription.name}")
                else:
                    print(f"  ⚠ No cost data available for {subscription.name}")
            
            except Exception as e:
                print(f"  ✗ Error processing {subscription.name}: {str(e)}")
                # Continue with other subscriptions even if one fails
                continue
            
            # Add delay between subscriptions to avoid rate limiting
            if idx < len(config.subscriptions) - 1:
                time.sleep(2)
        
        if not all_data:
            raise HTTPException(
                status_code=404,
                detail="No cost data available for any configured subscription"
            )
        
        # Step 2: NEW - Collect anomaly data for each day in the period
        print(f"\n{'='*60}")
        print(f"Running Anomaly Detection")
        print(f"{'='*60}\n")
        
        # Build subscription dictionary for anomaly detection
        subscriptions = {
            sub.name: sub.id
            for sub in config.subscriptions
        }
        
        anomaly_data = []
        
        # Check each day in the report period
        # Start from num_days ago to yesterday
        for day_offset in range(request.num_days, 0, -1):
            target_date = datetime.now() - timedelta(days=day_offset)
            
            print(f"Checking anomalies for {target_date.strftime('%Y-%m-%d')}...")
            
            try:
                result = anomaly_detector.check_all_subscriptions(
                    subscriptions,
                    target_date,
                    request.anomaly_threshold
                )
                
                # Add date to result for easier processing
                result['date'] = target_date.strftime('%Y-%m-%d')
                result['day_name'] = target_date.strftime('%A')
                
                anomaly_data.append(result)
                
                # Count anomalies found
                anomaly_count = sum(
                    1 for sub_result in result.get('subscriptions', {}).values()
                    if sub_result and sub_result.get('has_anomalies', False)
                )
                
                if anomaly_count > 0:
                    print(f"  ✓ Found anomalies in {anomaly_count} subscription(s)")
                else:
                    print(f"  ✓ No anomalies detected")
            
            except Exception as e:
                print(f"  ⚠ Error checking anomalies: {str(e)}")
                # Continue with other days even if one fails
                continue
            
            # Small delay between days to avoid rate limiting
            if day_offset > 1:
                time.sleep(1)
        
        print(f"\n{'='*60}")
        print(f"Generating Report Document")
        print(f"{'='*60}\n")
        
        # Step 3: Generate document with cost data AND anomaly data
        filename = doc_generator.generate_cost_report(
            all_data, 
            request.num_days,
            anomaly_data=anomaly_data  # NEW: Pass anomaly data to generator
        )
        
        print(f"\n✓ Report generated: {filename}\n")
        
        # Count total anomalies across all days
        total_anomalies = sum(
            result.get('summary', {}).get('subscriptions_with_anomalies', 0)
            for result in anomaly_data
        )
        
        return CostReportResponse(
            status="success",
            message=f"Cost report generated successfully for {request.num_days} days across {len(all_data)} subscription(s). {total_anomalies} anomaly days detected.",
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