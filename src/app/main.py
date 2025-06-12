"""
Main FastAPI application for PolyglotPO - AI-Powered PO File Translation Tool.
Entry point for the web application.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from loguru import logger

from .config import settings
from .models.api_models import ErrorResponse


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting PolyglotPO - AI-Powered PO File Translation Tool")
    logger.info(f"Version: {settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Ensure storage directories exist
    settings._setup_directories()
    
    # TODO: Initialize background tasks for file cleanup
    
    yield
    
    # Shutdown
    logger.info("Shutting down PolyglotPO")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    Professional translation service for PO (Portable Object) files using DeepSeek AI.
    Perfect for localizing Drupal, WordPress, and other CMS applications.
    
    ## Features
    - Batch Translation: Process large PO files efficiently
    - Context-Aware: Preserves msgctxt and plural forms  
    - Real-time Progress: Live translation status updates
    - Format Preservation: Maintains original PO file structure
    - Multi-Language Support: Support for 50+ world languages
    
    ## Quick Start
    1. Upload your PO file via `/api/v1/upload`
    2. Create translation job using `/api/v1/translate`
    3. Monitor progress via `/api/v1/jobs/{job_id}`
    4. Download results from `/api/v1/download/{job_id}`
    """,
    docs_url="/docs",  # Always enable Swagger UI
    redoc_url="/redoc",  # Always enable ReDoc
    contact={
        "name": "PolyglotPO Support",
        "email": "support@polyglotpo.com",
    },
    license_info={
        "name": "Internal Use Only",
    },
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Internal tool, can be permissive
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.allowed_hosts != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )

# Configure static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Configure templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured response."""
    error_response = ErrorResponse(
        error=exc.detail,
        error_code=f"HTTP_{exc.status_code}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_response.dict())
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle value errors."""
    logger.error(f"ValueError in {request.url}: {str(exc)}")
    error_response = ErrorResponse(
        error=str(exc),
        error_code="VALIDATION_ERROR"
    )
    return JSONResponse(
        status_code=400,
        content=jsonable_encoder(error_response.dict())
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error(f"Unhandled exception in {request.url}: {str(exc)}", exc_info=True)
    error_response = ErrorResponse(
        error="Internal server error" if not settings.debug else str(exc),
        error_code="INTERNAL_ERROR"
    )
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(error_response.dict())
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from .models.api_models import HealthCheckResponse
    
    return HealthCheckResponse(
        version=settings.app_version,
        database_status="ok",  # No database in MVP
        storage_status="ok" if settings.storage_dir.exists() else "error",
        api_status="ok"  # TODO: Check DeepSeek API connectivity
    )


# Root endpoint - serve main HTML page
@app.get("/")
async def root(request: Request):
    """Serve the main application page."""
    from .config import SUPPORTED_LANGUAGES
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request,
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "supported_languages": SUPPORTED_LANGUAGES,
            "max_file_size": settings.file_config.max_file_size
        }
    )


# API root endpoint
@app.get("/api", tags=["API Info"])
async def api_root():
    """API root endpoint with overview and links."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "AI-Powered PO File Translation Tool",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "endpoints": {
            "upload": "/api/v1/upload",
            "translate": "/api/v1/translate",
            "jobs": "/api/v1/jobs",
            "download": "/api/v1/download",
            "languages": "/api/v1/languages/supported"
        },
        "health_check": "/health"
    }

@app.get("/api/v1", tags=["API Info"])
async def api_v1_root():
    """API v1 root endpoint."""
    return {
        "version": "v1", 
        "status": "active",
        "endpoints": [
            "GET /api/v1/languages/supported - Get supported languages",
            "POST /api/v1/upload - Upload PO file",
            "POST /api/v1/translate - Create translation job", 
            "GET /api/v1/translate/{job_id} - Get job status",
            "GET /api/v1/jobs - List all jobs",
            "GET /api/v1/download/{job_id} - Download translated file"
        ]
    }

# Import and register API routes
from .api import upload
from .api import translation
from .api import jobs  
from .api import download
from .api import languages

# Register API routes
app.include_router(
    upload.router, 
    prefix="/api/v1", 
    tags=["File Upload"]
)
app.include_router(
    translation.router, 
    prefix="/api/v1", 
    tags=["Translation Jobs"]
)
app.include_router(
    jobs.router, 
    prefix="/api/v1", 
    tags=["Job Management"]
)
app.include_router(
    download.router, 
    prefix="/api/v1", 
    tags=["Download Results"]
)
app.include_router(
    languages.router, 
    prefix="/api/v1", 
    tags=["Languages"]
)

# HTML page routes
@app.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request):
    """Serve the jobs management page."""
    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "app_name": settings.app_name,
        "app_version": settings.app_version
    })


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail_page(request: Request, job_id: str):
    """Serve the job detail page."""
    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "job_id": job_id
    })


# Development server entry point
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    ) 