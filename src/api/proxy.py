from fastapi import APIRouter, Request, Depends, Response, HTTPException
from httpx import AsyncClient, RequestError
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
from auth.selenium_login import manual_login_and_capture_cookies, load_manual_cookies
from auth.browser_session import get_browser_session, refresh_browser_session
from utils.helpers import filter_headers
import os
import asyncio
import time
import json

router = APIRouter()

COOKIES_FILE = "manual_cookies.json"

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
            # Force refresh both sessions
            await force_refresh_session()
            await refresh_browser_session()
            
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
        
        # Check browser session
        try:
            browser_session = await get_browser_session()
            status["browser_session_active"] = browser_session is not None
        except Exception:
            status["browser_session_active"] = False
            
        return status
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/refresh-session")
async def refresh_session():
    """
    Force refresh both HTTP and browser sessions
    """
    try:
        await force_refresh_session()
        await refresh_browser_session()
        return {"status": "success", "message": "Both sessions refreshed successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Session refresh failed: {str(e)}"}

@router.post("/update-cookies")
async def update_cookies_endpoint(request: Request):
    """
    Endpoint to update cookies with fresh ones from request body
    """
    try:
        body = await request.json()
        if "cookies" not in body:
            raise HTTPException(status_code=400, detail="Missing 'cookies' in request body")
        
        cookies_data = {
            "timestamp": time.time(),
            "url": "https://app.stealthwriter.ai/dashboard",
            "cookies": body["cookies"]
        }
        
        # Save to file
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        COOKIES_FILE_PATH = os.path.join(PROJECT_ROOT, "manual_cookies.json")
        
        with open(COOKIES_FILE_PATH, "w") as f:
            json.dump(cookies_data, f, indent=2)
        
        # Force refresh both sessions
        await force_refresh_session()
        await refresh_browser_session()
        
        return {
            "status": "success",
            "message": f"Updated {len(body['cookies'])} cookies and refreshed both sessions",
            "cookie_count": len(body["cookies"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update cookies: {str(e)}")

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def browser_proxy(path: str, request: Request):
    """
    Browser-based proxy using Playwright to bypass Cloudflare
    """
    try:
        # Get browser session
        browser_session = await get_browser_session()
        
        # Fix: Default to dashboard if accessing root
        if path == "" or path == "/":
            path = "dashboard"
        
        target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
        
        # Get request body
        body = await request.body()
        
        # Make request using browser
        result = await browser_session.make_request(
            method=request.method,
            url=target_url,
            headers=dict(request.headers),
            data=body if body else None
        )
        
        # Check if we got a successful response
        if result['status_code'] == 200:
            print(f"✅ Browser proxy successful: {target_url}")
        else:
            print(f"⚠️ Browser proxy returned {result['status_code']}: {target_url}")
        
        # Filter response headers
        filtered_headers = {}
        for k, v in result.get('headers', {}).items():
            if k.lower() not in ["content-encoding", "transfer-encoding", "connection", "content-length", "server"]:
                filtered_headers[k] = v
        
        # Add CORS headers for browser compatibility
        filtered_headers.update({
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        })
        
        return Response(
            content=result['content'],
            status_code=result['status_code'],
            headers=filtered_headers,
            media_type="text/html"
        )
        
    except Exception as e:
        print(f"❌ Browser proxy error: {str(e)}")
        
        # Fallback error page
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Browser Proxy Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .error {{ background: #ffebee; padding: 20px; border-radius: 8px; border-left: 4px solid #f44336; }}
                .info {{ background: #e3f2fd; padding: 20px; border-radius: 8px; border-left: 4px solid #2196f3; margin-top: 20px; }}
                .code {{ background: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>🔧 Browser Proxy Error</h2>
                <p>The browser-based proxy encountered an error while trying to access the target website.</p>
                <p><strong>Error:</strong> {str(e)}</p>
            </div>
            
            <div class="info">
                <h3>💡 Solutions:</h3>
                <ol>
                    <li><strong>Refresh your session:</strong> 
                        <div class="code">POST /refresh-session</div>
                    </li>
                    <li><strong>Update cookies:</strong>
                        <div class="code">POST /update-cookies</div>
                    </li>
                    <li><strong>Check session status:</strong>
                        <div class="code">GET /session-status</div>
                    </li>
                </ol>
            </div>
        </body>
        </html>
        """
        
        return Response(
            content=error_html,
            status_code=500,
            headers={"Content-Type": "text/html"}
        )
