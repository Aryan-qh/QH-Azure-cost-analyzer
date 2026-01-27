# api/routes/cost_report.py
"""
Cost Report API Routes

CHANGE: Now generates BOTH Word summary and Excel details
- Word document: Simple email-friendly summary with totals only
- Excel spreadsheet: Detailed breakdown by resource + anomalies
- Returns both file URLs to user

Logic:
- Retrieve user config from session_id
- Extract credentials and subscriptions
- Generate cost data for all configured subscriptions
- Run anomaly detection for each day in the period
- Generate TWO files:
  1. Word doc with subscription totals (email-friendly)
  2. Excel workbook with detailed breakdown and anomalies
- Use subscription names from config in both reports
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.config import get_settings, Settings
from app.services.azure_auth import AzureAuthService
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService
from app.services.document_generator import DocumentGeneratorService
from app.services.excel_generator import ExcelGeneratorService  # NEW IMPORT
from app.services.anomaly_detector import AnomalyDetectorService
from app.services.configuration_manager import get_config_manager, ConfigurationManagerService
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import os
import time
import subprocess

router = APIRouter()


class CostReportRequest(BaseModel):
    """Request model for cost report generation"""
    session_id: str = Field(..., description="Session ID from configuration")
    num_days: int = Field(ge=1, le=90, description="Number of days to look back")
    anomaly_threshold: float = Field(25.0, ge=0, le=100, description="Anomaly detection threshold percentage")


class CostReportGenerationResponse(BaseModel):
    """Response model for cost report with both Word and Excel files"""
    status: str
    message: str
    word_file: str
    excel_file: str
    word_download_url: str
    excel_download_url: str
    subscription_count: int
    total_anomalies: int


@router.post("/generate", response_model=CostReportGenerationResponse)
async def generate_cost_report(
    request: CostReportRequest,
    config_manager: ConfigurationManagerService = Depends(get_config_manager),
    settings: Settings = Depends(get_settings)
):
    """
    Generate cost reports: Word summary + Excel details.
    
    CHANGE: Now generates TWO files instead of one
    1. Word document: Simple email-friendly summary with subscription totals
    2. Excel workbook: Detailed breakdown by service + anomaly detection results
    
    Steps:
    1. Validate session and retrieve configuration
    2. Create authentication service with user credentials
    3. Fetch cost data for all configured subscriptions
    4. Run anomaly detection for each day in the period
    5. Generate Word summary (totals only)
    6. Generate Excel details (resource breakdown + anomalies)
    7. Return URLs for both files
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
        excel_generator = ExcelGeneratorService(settings.output_directory)  # NEW
        
        # Initialize anomaly detector
        anomaly_detector = AnomalyDetectorService(cost_data_service, cost_processor)
        
        print(f"\n{'='*60}")
        print(f"Cost Report Generation: Word Summary + Excel Details")
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
        
        # Step 2: Collect anomaly data for each day in the period
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
        
        # Step 3: Generate Word document (summary only)
        print(f"\n{'='*60}")
        print(f"Generating Word Summary Document")
        print(f"{'='*60}\n")
        
        word_filename = doc_generator.generate_cost_report(
            all_data, 
            request.num_days
        )
        
        print(f"✓ Word summary generated: {word_filename}\n")
        
        # Step 4: Generate Excel workbook (detailed breakdown + anomalies)
        print(f"{'='*60}")
        print(f"Generating Excel Details Workbook")
        print(f"{'='*60}\n")
        
        excel_filename = excel_generator.generate_detailed_report(
            all_data,
            request.num_days,
            anomaly_data=anomaly_data
        )
        
        print(f"✓ Excel details generated: {excel_filename}\n")
        
        # Recalculate Excel formulas (if recalc script exists)
        excel_filepath = os.path.join(settings.output_directory, excel_filename)
        if os.path.exists('scripts/recalc.py'):
            print(f"{'='*60}")
            print(f"Recalculating Excel Formulas")
            print(f"{'='*60}\n")
            
            try:
                result = subprocess.run(
                    ['python', 'scripts/recalc.py', excel_filepath, '30'],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    print(f"✓ Excel formulas recalculated successfully\n")
                else:
                    print(f"⚠ Warning: Formula recalculation had issues\n")
                    print(f"  stdout: {result.stdout}")
                    print(f"  stderr: {result.stderr}\n")
            except Exception as e:
                print(f"⚠ Warning: Could not recalculate formulas: {e}\n")
        else:
            print("⚠ Recalc script not found, skipping formula recalculation\n")
        
        # Count total anomalies across all days
        total_anomalies = sum(
            result.get('summary', {}).get('subscriptions_with_anomalies', 0)
            for result in anomaly_data
        )
        
        return CostReportGenerationResponse(
            status="success",
            message=f"Reports generated successfully for {request.num_days} days across {len(all_data)} subscription(s)",
            word_file=word_filename,
            excel_file=excel_filename,
            word_download_url=f"/api/cost-report/download/{word_filename}",
            excel_download_url=f"/api/cost-report/download/{excel_filename}",
            subscription_count=len(all_data),
            total_anomalies=total_anomalies
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        print(f"ERROR in cost report generation: {str(e)}")
        import traceback
        traceback.print_exc()
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
    Download a generated report (Word or Excel).
    
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
    
    # Determine media type based on extension
    if filename.endswith('.xlsx'):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith('.docx'):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename
    )