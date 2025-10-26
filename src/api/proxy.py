from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from httpx import AsyncClient, RequestError, HTTPStatusError, TimeoutException
from typing import Optional
import os
import sys
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.session import get_authenticated_client
from utils.helpers import structured_log, log_error, log_request

router = APIRouter()

# Headers that should NOT be forwarded from client to target
BLOCKED_REQUEST_HEADERS = {
    'host', 'connection', 'content-length', 'transfer-encoding',
    'upgrade-insecure-requests', 'sec-fetch-site', 'sec-fetch-mode',
    'sec-fetch-user', 'sec-fetch-dest', 'cookie', 'authorization',
    'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto',
    'x-real-ip', 'forwarded'
}

# Headers that should NOT be sent back to client
BLOCKED_RESPONSE_HEADERS = {
    'content-encoding', 'transfer-encoding', 'connection',
    'set-cookie', 'strict-transport-security', 'keep-alive',
    'proxy-authenticate', 'proxy-authorization', 'te', 'trailer',
    'upgrade'
}

# Content types that should be proxied as-is
BINARY_CONTENT_TYPES = {
    'image/', 'video/', 'audio/', 'application/pdf',
    'application/zip', 'application/octet-stream',
    'font/', 'application/wasm'
}

def is_binary_content(content_type: str) -> bool:
    """Check if content type is binary"""
    if not content_type:
        return False
    content_type = content_type.lower()
    return any(content_type.startswith(binary_type) for binary_type in BINARY_CONTENT_TYPES)

def prepare_request_headers(request_headers: dict, target_url: str) -> dict:
    """
    Prepare headers for proxied request
    Removes blocked headers and adds necessary ones for target site
    """
    headers = {}
    
    # Copy allowed headers
    for key, value in request_headers.items():
        if key.lower() not in BLOCKED_REQUEST_HEADERS:
            headers[key] = value
    
    # Add/override essential headers for the target site
    base_url = os.getenv("TARGET_URL", "https://app.stealthwriter.ai").rstrip("/")
    headers['Referer'] = target_url
    headers['Origin'] = base_url
    
    # Ensure Accept header exists
    if 'accept' not in {k.lower() for k in headers.keys()}:
        headers['Accept'] = '*/*'
    
    structured_log("Request headers prepared", header_count=len(headers))
    return headers

def prepare_response_headers(response_headers: dict) -> dict:
    """
    Prepare headers for response to client
    Removes blocked headers and adds CORS headers
    """
    headers = {}
    
    # Copy allowed headers
    for key, value in response_headers.items():
        if key.lower() not in BLOCKED_RESPONSE_HEADERS:
            headers[key] = value
    
    # Add CORS headers for client access
    cors_origins = os.getenv("CORS_ORIGINS", "*")
    headers['Access-Control-Allow-Origin'] = cors_origins
    headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD'
    headers['Access-Control-Allow-Headers'] = '*'
    headers['Access-Control-Allow-Credentials'] = 'true'
    headers['Access-Control-Max-Age'] = '3600'
    
    return headers

def build_target_url(path: str, query_params: dict) -> str:
    """Build the complete target URL"""
    base_url = os.getenv("TARGET_URL", "https://app.stealthwriter.ai").rstrip("/")
    
    if path:
        target_url = f"{base_url}/{path}"
    else:
        target_url = base_url
    
    # Add query parameters if present
    if query_params:
        query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])
        target_url = f"{target_url}?{query_string}"
    
    return target_url

async def read_request_body(request: Request) -> Optional[bytes]:
    """Read request body for methods that support it"""
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
            return body if body else None
        except Exception as e:
            log_error("Body Read Error", "Failed to read request body", error=str(e))
            return None
    return None

@router.options("/{path:path}")
async def handle_options(path: str):
    """
    Handle CORS preflight requests
    """
    structured_log("CORS preflight request", path=path)
    
    return Response(
        status_code=200,
        headers={
            'Access-Control-Allow-Origin': os.getenv("CORS_ORIGINS", "*"),
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Max-Age': '3600'
        }
    )

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])
async def browser_proxy(
    path: str, 
    request: Request,
    client: AsyncClient = Depends(get_authenticated_client)
):
    """
    Proxy requests through the master authenticated session
    
    This endpoint:
    1. Receives requests from clients
    2. Forwards them through the authenticated master session
    3. Returns responses back to clients
    
    All requests share the same authenticated session to bypass Cloudflare
    """
    
    # Build target URL
    target_url = build_target_url(path, dict(request.query_params))
    
    structured_log(
        "Incoming proxy request",
        method=request.method,
        path=path,
        target=target_url,
        client_ip=request.client.host if request.client else "unknown"
    )
    
    try:
        # Prepare headers
        headers = prepare_request_headers(dict(request.headers), target_url)
        
        # Read request body
        body = await read_request_body(request)
        
        if body:
            structured_log("Request body size", size_bytes=len(body))
        
        # Forward request using master authenticated session
        structured_log("Forwarding request to target", url=target_url, method=request.method)
        
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            timeout=30.0
        )
        
        # Log response
        content_type = response.headers.get('content-type', 'unknown')
        log_request(
            method=request.method,
            path=path,
            status_code=response.status_code,
            content_type=content_type,
            content_length=len(response.content)
        )
        
        # Handle redirects (log them but let httpx handle)
        if response.status_code in [301, 302, 303, 307, 308]:
            location = response.headers.get('location', '')
            structured_log(
                "Redirect response",
                status_code=response.status_code,
                location=location
            )
        
        # Check for authentication errors
        if response.status_code == 401:
            log_error(
                "Authentication Error",
                "Target site returned 401 - session may be invalid",
                status_code=401,
                url=target_url
            )
            # Session will auto-refresh on next request
        
        # Prepare response headers
        response_headers = prepare_response_headers(dict(response.headers))
        
        # Determine media type
        media_type = response.headers.get('content-type', 'application/octet-stream')
        
        # Return response to client
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=media_type
        )
        
    except TimeoutException as e:
        log_error(
            "Timeout Error",
            "Request to target timed out",
            url=target_url,
            error=str(e)
        )
        raise HTTPException(
            status_code=504,
            detail={
                "error": "Gateway Timeout",
                "message": "Request to target site timed out",
                "target": target_url
            }
        )
        
    except HTTPStatusError as e:
        log_error(
            "HTTP Status Error",
            "Target returned error status",
            status_code=e.response.status_code,
            url=target_url,
            error=str(e)
        )
        
        # Try to get error details from response
        try:
            error_detail = e.response.json()
        except:
            error_detail = e.response.text[:500] if e.response.text else str(e)
        
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "error": "Target Server Error",
                "message": f"Target site returned status {e.response.status_code}",
                "details": error_detail
            }
        )
        
    except RequestError as e:
        log_error(
            "Request Error",
            "Connection error to target site",
            url=target_url,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "Bad Gateway",
                "message": "Failed to connect to target site",
                "details": str(e)
            }
        )
        
    except Exception as e:
        log_error(
            "Unexpected Error",
            "Unexpected error during proxy request",
            url=target_url,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal Proxy Error",
                "message": "An unexpected error occurred",
                "details": str(e)
            }
        )

@router.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns service status and basic info
    """
    try:
        # Try to get the client to verify session is working
        client = await get_authenticated_client()
        session_active = client is not None
    except Exception as e:
        session_active = False
        log_error("Health Check Error", "Failed to verify session", error=str(e))
    
    health_status = {
        "status": "healthy" if session_active else "degraded",
        "service": "stealthwriter-proxy",
        "version": "1.0.0",
        "session_active": session_active,
        "target_url": os.getenv("TARGET_URL", "not-configured")
    }
    
    status_code = 200 if session_active else 503
    
    structured_log(
        "Health check",
        status=health_status["status"],
        session_active=session_active
    )
    
    return JSONResponse(
        content=health_status,
        status_code=status_code
    )

@router.get("/status")
async def status_check():
    """
    Detailed status endpoint
    Returns detailed information about the proxy service
    """
    try:
        client = await get_authenticated_client()
        session_active = client is not None
        
        # Get session info from the session manager if available
        from auth.session import _master_session_manager
        
        last_refresh = None
        if _master_session_manager._last_refresh:
            last_refresh = _master_session_manager._last_refresh.isoformat()
        
        status_info = {
            "status": "operational" if session_active else "error",
            "service": "stealthwriter-proxy",
            "version": "1.0.0",
            "session": {
                "active": session_active,
                "last_refresh": last_refresh,
                "is_refreshing": _master_session_manager._is_refreshing
            },
            "configuration": {
                "target_url": os.getenv("TARGET_URL", "not-configured"),
                "aws_region": os.getenv("AWS_REGION", "not-configured"),
                "session_timeout": os.getenv("SESSION_TIMEOUT", "3600")
            }
        }
        
    except Exception as e:
        log_error("Status Check Error", "Failed to get status", error=str(e))
        status_info = {
            "status": "error",
            "error": str(e)
        }
    
    return JSONResponse(content=status_info)

@router.post("/refresh-session")
async def force_refresh_session():
    """
    Force refresh the master session
    Useful for manual session refresh or debugging
    """
    try:
        from auth.session import _master_session_manager
        
        structured_log("Manual session refresh requested")
        
        await _master_session_manager._refresh_session()
        
        structured_log("Manual session refresh completed")
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "Session refreshed successfully"
            }
        )
        
    except Exception as e:
        log_error("Session Refresh Error", "Failed to refresh session", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Session Refresh Failed",
                "message": str(e)
            }
        )

# Root endpoint for the proxy
@router.get("/")
async def proxy_root():
    """
    Root endpoint - returns basic service info
    """
    return JSONResponse(
        content={
            "service": "StealthWriter Proxy",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "health": "/health",
                "status": "/status",
                "refresh": "/refresh-session",
                "proxy": "/{path}"
            }
        }
    )
