from fastapi import APIRouter, Request, Depends, Response, HTTPException
from httpx import AsyncClient, RequestError
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
from auth.selenium_login import manual_login_and_capture_cookies, load_manual_cookies, save_manual_cookies_direct
from utils.helpers import filter_headers
import os
import asyncio
import json

router = APIRouter()

@router.post("/set-cookies-direct")
async def set_cookies_direct(request: Request):
    """
    Endpoint to set cookies directly from manual input
    Expects JSON with cookies dict: {"cookie_name": "cookie_value", ...}
    """
    try:
        cookies_data = await request.json()
        
        if not isinstance(cookies_data, dict):
            return {
                "status": "error", 
                "message": "Invalid format. Expected JSON object with cookie names and values"
            }
        
        print(f"🍪 Received {len(cookies_data)} cookies to set directly")
        
        # Save the cookies
        success = save_manual_cookies_direct(cookies_data)
        
        if success:
            # Force refresh the session to use new cookies
            await force_refresh_session()
            
            return {
                "status": "success",
                "message": f"Successfully set {len(cookies_data)} cookies and refreshed session",
                "cookie_names": list(cookies_data.keys())
            }
        else:
            return {
                "status": "error",
                "message": "Failed to save cookies"
            }
            
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Failed to set cookies: {str(e)}"
        }

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
async def browser_proxy(path: str, request: Request, client: AsyncClient = Depends(get_authenticated_client)):
    # Build the target URL
    target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
    if path == "":
        target_url = os.getenv("TARGET_URL")  # root path

    # Prepare headers and body
    headers = filter_headers(dict(request.headers))
    body = await request.body()

    try:
        # Forward the request to the target site
        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )

        # Stream the response back to the browser
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() not in ["content-encoding", "transfer-encoding", "connection"]}
        )
    except RequestError as e:
        raise HTTPException(status_code=502, detail=f"Proxy Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")