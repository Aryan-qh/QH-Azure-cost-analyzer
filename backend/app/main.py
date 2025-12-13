"""
FastAPI Application Entry Point
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from app.config import get_settings, Settings
from app.api.routes.cost_report import router as cost_report_router
from app.api.routes.anomaly_detection import router_anomaly
from app.models.responses import HealthResponse

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
        allow_origins=["*"],  # In production, specify exact origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
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
    
    # Health check endpoint
    @app.get("/api/health", response_model=HealthResponse)
    async def health_check(settings: Settings = Depends(get_settings)):
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            version=settings.api_version
        )
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "Azure Cost Analyzer API",
            "version": settings.api_version,
            "docs": "/docs"
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