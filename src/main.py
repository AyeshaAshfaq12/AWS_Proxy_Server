from dotenv import load_dotenv
import os
import sys

# Load environment variables first
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from api.proxy import router
from auth.session import close_master_session
from utils.helpers import structured_log, log_error
from aws.integration import validate_aws_configuration

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle
    Handles startup and shutdown events
    """
    # Startup
    structured_log("=" * 60)
    structured_log("Starting StealthWriter Proxy Server")
    structured_log("=" * 60)
    
    try:
        # Log configuration
        structured_log(
            "Configuration loaded",
            target_url=os.getenv("TARGET_URL"),
            aws_region=os.getenv("AWS_REGION"),
            port=os.getenv("PORT", "8000"),
            cors_origins=os.getenv("CORS_ORIGINS", "*")
        )
        
        # Validate AWS configuration
        try:
            validate_aws_configuration()
            structured_log("AWS configuration validated")
        except Exception as e:
            log_error("AWS Configuration Error", str(e))
            structured_log("Warning: AWS validation failed, but continuing startup")
        
        structured_log("Proxy server ready to accept connections")
        structured_log("Master session will be created on first request")
        
    except Exception as e:
        log_error("Startup Error", "Failed to initialize application", error=str(e))
        raise
    
    yield
    
    # Shutdown
    structured_log("=" * 60)
    structured_log("Shutting down StealthWriter Proxy Server")
    structured_log("=" * 60)
    
    try:
        await close_master_session()
        structured_log("Master session closed successfully")
    except Exception as e:
        log_error("Shutdown Error", "Error closing master session", error=str(e))
    
    structured_log("Shutdown complete")

# Create FastAPI app with lifecycle management
app = FastAPI(
    title="StealthWriter Proxy Server",
    description="Authenticated proxy server with master session for StealthWriter.ai",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
cors_origins = os.getenv("CORS_ORIGINS", "*")
if cors_origins == "*":
    origins = ["*"]
else:
    origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    log_error(
        "Unhandled Exception",
        "An unhandled exception occurred",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "path": request.url.path
        }
    )

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    structured_log(
        "Incoming request",
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown"
    )
    
    response = await call_next(request)
    
    structured_log(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code
    )
    
    return response

# Include proxy router (handles all proxy routes)
app.include_router(router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "StealthWriter Proxy",
        "version": "1.0.0",
        "status": "running",
        "description": "Authenticated proxy server for StealthWriter.ai",
        "endpoints": {
            "health": "/health",
            "status": "/status",
            "refresh_session": "/refresh-session",
            "docs": "/docs",
            "proxy": "/{path}"
        },
        "documentation": {
            "interactive": "/docs",
            "redoc": "/redoc"
        }
    }

# Additional health endpoint at root level
@app.get("/healthz")
async def healthz():
    """Kubernetes-style health check"""
    return {"status": "ok"}

# Readiness probe
@app.get("/ready")
async def readiness():
    """Readiness probe - checks if service can handle requests"""
    try:
        from auth.session import get_authenticated_client
        # Try to get client without actually creating session
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "error": str(e)}
        )

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    structured_log(
        "Starting server",
        host=host,
        port=port,
        log_level=log_level
    )
    
    # Run the server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
        reload=False  # Set to True for development
    )
