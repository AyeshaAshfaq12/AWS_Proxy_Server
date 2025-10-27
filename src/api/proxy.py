from fastapi import APIRouter, Request, Depends, Response, HTTPException
from httpx import AsyncClient, RequestError
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
from auth.selenium_login import manual_login_and_capture_cookies, load_manual_cookies
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
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies_data, f, indent=2)
        
        # Force refresh the session
        await force_refresh_session()
        
        return {
            "status": "success",
            "message": f"Updated {len(body['cookies'])} cookies and refreshed session",
            "cookie_count": len(body["cookies"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update cookies: {str(e)}")

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

    # Enhanced headers with more browser-like behavior
    headers = {
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
        "Referer": "https://app.stealthwriter.ai/",
        # Add additional headers from the original request if they're safe
        "Origin": request.headers.get("origin", "https://app.stealthwriter.ai"),
    }

    # Copy safe headers from original request
    safe_headers = ["accept", "accept-language", "cache-control", "pragma"]
    for header in safe_headers:
        if header in request.headers:
            headers[header.title()] = request.headers[header]

    body = await request.body()

    try:
        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )
        
        # Check if we got a Cloudflare challenge
        if response.status_code == 403 or "challenge-platform" in str(response.content):
            return Response(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Proxy Error - Cloudflare Challenge</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; }}
                        .error {{ background: #ffebee; padding: 20px; border-radius: 8px; border-left: 4px solid #f44336; }}
                        .info {{ background: #e3f2fd; padding: 20px; border-radius: 8px; border-left: 4px solid #2196f3; margin-top: 20px; }}
                        .code {{ background: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace; }}
                    </style>
                </head>
                <body>
                    <div class="error">
                        <h2>🛡️ Cloudflare Challenge Detected</h2>
                        <p>The target website (StealthWriter.ai) is showing a Cloudflare challenge page instead of the dashboard content.</p>
                        <p><strong>This means your cookies may have expired or the IP is being blocked.</strong></p>
                    </div>
                    
                    <div class="info">
                        <h3>💡 Solutions:</h3>
                        <ol>
                            <li><strong>Refresh your cookies:</strong> 
                                <div class="code">GET /manual-login</div>
                                <p>This will open a browser for you to manually log in and capture fresh cookies.</p>
                            </li>
                            <li><strong>Check session status:</strong>
                                <div class="code">GET /session-status</div>
                                <p>Verify if your current session is valid.</p>
                            </li>
                            <li><strong>Update cookies manually:</strong>
                                <p>Export fresh cookies from a working browser session and update your manual_cookies.json file.</p>
                            </li>
                        </ol>
                    </div>
                    
                    <p><strong>Current Status:</strong> Cloudflare challenge detected on {target_url}</p>
                </body>
                </html>
                """,
                status_code=403,
                headers={"Content-Type": "text/html"}
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
