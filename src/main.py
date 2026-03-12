"""Main FastAPI application entry point"""

import logging
import os
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from src.config import get_config
from src.api.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware
)
from src.api.exceptions import APIException
from src.api.models import ErrorResponse
from src.utils.logging_config import init_logging, get_logger
from src.utils.metrics import get_metrics_collector

# Initialize structured logging
init_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Google Drive Excel RAG System")
    config = get_config()
    
    # Validate configuration
    errors = config.validate()
    if errors:
        logger.warning(f"Configuration validation warnings: {errors}")
    
    logger.info(f"Environment: {config.env}")
    logger.info(f"Vector Store: {config.vector_store.provider}")
    logger.info(f"Embedding Provider: {config.embedding.provider}")
    logger.info(f"LLM Provider: {config.llm.provider}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Google Drive Excel RAG System")


# Create FastAPI application
app = FastAPI(
    title="Google Drive Excel RAG System",
    description="Retrieval-Augmented Generation system for querying Excel files in Google Drive",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
config = get_config()

# Use explicit development origins instead of wildcard for security
DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Vite default
    "http://127.0.0.1:5173",
]
allowed_origins = DEV_ORIGINS if config.env == "development" else config.api.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, default_requests_per_minute=60)


# Exception handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Handle custom API exceptions"""
    from src.api.middleware import get_correlation_id
    
    logger.error(
        f"API exception: {exc.message}",
        extra={
            'correlation_id': get_correlation_id(),
            'status_code': exc.status_code,
            'details': exc.details
        },
        exc_info=True
    )
    
    error_response = ErrorResponse(
            error=exc.__class__.__name__,
            message=exc.message,
            details=exc.details,
            correlation_id=get_correlation_id(),
            timestamp=datetime.utcnow()
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(mode='json')
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    from src.api.middleware import get_correlation_id
    
    logger.warning(
        f"Validation error: {exc}",
        extra={'correlation_id': get_correlation_id()}
    )
    
    error_response = ErrorResponse(
            error="ValidationError",
            message="Request validation failed",
            details={"errors": exc.errors()},
            correlation_id=get_correlation_id(),
            timestamp=datetime.utcnow()
        )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(mode='json')
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    from src.api.middleware import get_correlation_id
    
    logger.error(
        f"Unhandled exception: {exc}",
        extra={'correlation_id': get_correlation_id()},
        exc_info=True
    )
    
    config = get_config()
    error_response = ErrorResponse(
            error="InternalServerError",
            message=str(exc) if config.env == "development" else "An internal error occurred",
            correlation_id=get_correlation_id(),
            timestamp=datetime.utcnow()
        )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(mode='json')
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint with component status"""
    from src.api.dependencies import get_auth_service, get_app_config
    
    config = get_app_config()
    
    # Check component health
    components = {
        "authentication": "unknown",
        "vector_store": config.vector_store.provider,
        "embedding_service": config.embedding.provider,
        "llm_service": config.llm.provider,
        "cache_service": config.cache.backend
    }
    
    # Check if authenticated
    try:
        auth_service = get_auth_service()
        components["authentication"] = "authenticated" if auth_service.is_authenticated() else "not_authenticated"
    except:
        components["authentication"] = "error"
    
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": config.env,
        "components": components
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Google Drive Excel RAG System",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


# Include API routers with versioning
from src.api.auth import router as auth_router
from src.api.web_auth import router as web_auth_router
from src.api.files import router as files_router
from src.api.gdrive_config import router as gdrive_config_router
from src.api.chat import router as chat_router
from src.api.indexing import router as indexing_router
from src.api.query import router as query_router
from src.api.metrics import router as metrics_router

# Excel Query Pipeline routes (Requirements 13.1-13.6, 14.1-14.6)
from src.api.routes import (
    batch_router,
    chunks_router,
    export_router,
    intelligence_router,
    query_router as pipeline_query_router,
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Google Drive Authentication"])
app.include_router(web_auth_router, prefix="/api/auth", tags=["Web Authentication"])
app.include_router(files_router, prefix="/api/files", tags=["File Management"])
app.include_router(gdrive_config_router, prefix="/api/config/gdrive", tags=["Google Drive Configuration"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat Sessions"])
app.include_router(indexing_router, prefix="/api/v1/index", tags=["Indexing"])
app.include_router(query_router, prefix="/api/v1/query", tags=["Query"])
app.include_router(metrics_router, prefix="/api/v1", tags=["Metrics"])

# Excel Query Pipeline routes (already have /api/v1 prefix defined)
app.include_router(chunks_router)  # Chunk visibility endpoints
app.include_router(pipeline_query_router)  # Query pipeline endpoints
app.include_router(batch_router)  # Batch and template endpoints
app.include_router(export_router)  # Export and webhook endpoints
app.include_router(intelligence_router)  # Intelligence feature endpoints


# ============================================================================
# Static File Serving for Frontend
# ============================================================================

# Path to frontend build directory
FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend" / "dist"

# Mount static files if build directory exists
if FRONTEND_BUILD_DIR.exists():
    logger.info(f"Serving frontend from: {FRONTEND_BUILD_DIR}")
    
    # Mount static assets (JS, CSS, images, etc.)
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_BUILD_DIR / "assets"),
        name="static"
    )
    
    # Catch-all route for client-side routing (must be last)
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """
        Serve frontend application for all non-API routes
        
        This enables client-side routing in React.
        """
        # Don't serve frontend for API routes
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": "Not Found", "message": f"API endpoint not found: /{full_path}"}
            )
        
        # Serve index.html for all other routes
        index_file = FRONTEND_BUILD_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        else:
            return JSONResponse(
                status_code=404,
                content={"error": "Not Found", "message": "Frontend not built"}
            )
else:
    logger.warning(f"Frontend build directory not found: {FRONTEND_BUILD_DIR}")
    logger.warning("Frontend will not be served. Build the frontend first with: cd frontend && npm run build")


if __name__ == "__main__":
    import uvicorn
    config = get_config()
    uvicorn.run(
        "src.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.env == "development"
    )
