from fastapi import APIRouter, Request, Depends, Response, HTTPException
from httpx import AsyncClient, RequestError
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
from auth.selenium_login import manual_login_and_capture_cookies, load_manual_cookies
from utils.helpers import filter_headers
import os
import asyncio

router = APIRouter()

@router.get("/manual-login")
async def manual_login_endpoint():
    """
    Endpoint to trigger manual login process
    """
    try:
        print("🚀 Starting manual login process...")
        
        # Run manual login in executor to avoid blocking
        cookies = await asyncio.get_event_loop().run_in_executor(
            None, 
            manual_login_and_capture_cookies
        )
        
        if cookies:
            # Force refresh the session to use new cookies
            await force_refresh_session()
            
            return {
                "status": "success",
                "message": f"Manual login completed successfully. Captured {len(cookies)} cookies.",
                "cookie_count": len(cookies)
            }
        else:
            return {
                "status": "failed",
                "message": "Manual login failed - no cookies captured"
            }
            
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Manual login failed: {str(e)}"
        }

@router.get("/session-status")
async def session_status():
    """
    Check current session status
    """
    try:
        status = await get_session_status()
        
        # Also check for manual cookies
        manual_cookies = load_manual_cookies()
        status["manual_cookies_available"] = bool(manual_cookies)
        if manual_cookies:
            status["manual_cookie_count"] = len(manual_cookies)
            
        return status
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/refresh-session")
async def refresh_session():
    """
    Force refresh the session
    """
    try:
        await force_refresh_session()
        return {"status": "success", "message": "Session refreshed successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Session refresh failed: {str(e)}"}

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def browser_proxy(path: str, request: Request):
    from auth.session import get_session_status, get_authenticated_client
    # Check session status before proxying
    session_status = await get_session_status()
    cookie_status = session_status.get("cookie_status", {})
    if not cookie_status.get("exists") or cookie_status.get("expired", True) or not cookie_status.get("cookies"):
        raise HTTPException(
            status_code=401,
            detail=f"Proxy session unavailable: {cookie_status.get('error', 'No valid manual cookies available')}"
        )

    client = await get_authenticated_client()
    
    # Fix: Default to dashboard if accessing root
    if path == "" or path == "/":
        path = "dashboard"
    
    target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path

    # Fix: Use original request headers and add Cloudflare-friendly headers
    headers = dict(request.headers)
    
    # Remove problematic headers
    headers.pop('host', None)
    headers.pop('x-forwarded-for', None)
    headers.pop('x-real-ip', None)
    
    # Add Cloudflare bypass headers
    headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://app.stealthwriter.ai/"
    })

    body = await request.body()

    try:
        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )
        
        # Filter response headers to avoid conflicts
        filtered_headers = {}
        for k, v in response.headers.items():
            if k.lower() not in ["content-encoding", "transfer-encoding", "connection", "content-length", "server"]:
                filtered_headers[k] = v
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=filtered_headers
        )
    except RequestError as e:
        raise HTTPException(status_code=502, detail=f"Proxy Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")
