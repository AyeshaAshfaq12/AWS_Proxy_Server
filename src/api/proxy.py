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

# Fallback function when browser session is not available
async def fallback_httpx_proxy(path: str, request: Request):
    """
    Fallback httpx-based proxy when Playwright is not available
    """
    try:
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
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "Referer": "https://app.stealthwriter.ai/",
        }

        # Copy safe headers from original request
        safe_headers = ["accept", "accept-language", "cache-control", "pragma"]
        for header in safe_headers:
            if header in request.headers:
                headers[header.title()] = request.headers[header]

        body = await request.body()

        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )
        
        # Check if we got a Cloudflare challenge or success
        content = response.content.decode('utf-8', errors='ignore')
        
        if response.status_code == 200:
            print(f"✅ HTTPX proxy successful: {target_url}")
        elif response.status_code == 403 or "challenge-platform" in content:
            print(f"⚠️ Cloudflare challenge detected: {target_url}")
            # Return a helpful error page
            return Response(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Cloudflare Challenge Detected</title>
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
                        <p><strong>Your cookies may have expired or need refreshing.</strong></p>
                    </div>
                    
                    <div class="info">
                        <h3>💡 Solutions:</h3>
                        <ol>
                            <li><strong>Get fresh cookies from your browser:</strong>
                                <p>1. Open StealthWriter.ai in your browser</p>
                                <p>2. Log in successfully</p>
                                <p>3. Export cookies and update manual_cookies.json</p>
                            </li>
                            <li><strong>Check session status:</strong>
                                <div class="code">GET /session-status</div>
                            </li>
                            <li><strong>Update cookies via API:</strong>
                                <div class="code">POST /update-cookies</div>
                            </li>
                        </ol>
                    </div>
                    
                    <p><strong>Current Status:</strong> {response.status_code} - Cloudflare challenge on {target_url}</p>
                </body>
                </html>
                """,
                status_code=403,
                headers={"Content-Type": "text/html"}
            )
        else:
            print(f"⚠️ HTTPX proxy returned {response.status_code}: {target_url}")
        
        # Filter response headers to avoid conflicts
        filtered_headers = {}
        for k, v in response.headers.items():
            if k.lower() not in ["content-encoding", "transfer-encoding", "connection", "content-length", "server"]:
                if isinstance(v, str):
                    clean_value = v.replace('\n', ' ').replace('\r', ' ').strip()
                    if clean_value and len(clean_value) < 8192:
                        filtered_headers[k] = clean_value
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=filtered_headers
        )
        
    except RequestError as e:
        raise HTTPException(status_code=502, detail=f"Proxy Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def browser_proxy(path: str, request: Request):
    """
    Smart proxy that tries browser session first, falls back to httpx
    """
    try:
        # Try to import and use browser session
        try:
            from auth.browser_session import get_browser_session
            browser_session = await get_browser_session()
            
            # Fix: Default to dashboard if accessing root
            if path == "" or path == "/":
                path = "dashboard"
            
            target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
            body = await request.body()
            
            # Make request using browser
            result = await browser_session.make_request(
                method=request.method,
                url=target_url,
                headers=dict(request.headers),
                data=body if body else None
            )
            
            print(f"✅ Browser proxy successful: {target_url}")
            
            # Filter response headers
            filtered_headers = {}
            for k, v in result.get('headers', {}).items():
                if k.lower() not in ["content-encoding", "transfer-encoding", "connection", "content-length", "server"]:
                    if isinstance(v, str):
                        clean_value = v.replace('\n', ' ').replace('\r', ' ').strip()
                        if clean_value and len(clean_value) < 8192:
                            filtered_headers[k] = clean_value
            
            filtered_headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Content-Type": "text/html; charset=utf-8"
            })
            
            return Response(
                content=result['content'],
                status_code=result['status_code'],
                headers=filtered_headers
            )
            
        except ImportError:
            print("⚠️ Browser session not available, using HTTPX fallback")
            return await fallback_httpx_proxy(path, request)
        except Exception as e:
            print(f"⚠️ Browser session failed: {e}, using HTTPX fallback")
            return await fallback_httpx_proxy(path, request)
            
    except Exception as e:
        print(f"❌ Proxy error: {str(e)}")
        return Response(
            content=f"<html><body><h1>Proxy Error</h1><p>{str(e)}</p></body></html>",
            status_code=500,
            headers={"Content-Type": "text/html"}
        )

# Keep the other endpoints unchanged
@router.get("/manual-login")
async def manual_login_endpoint():
    try:
        print("🚀 Starting manual login process...")
        cookies = await asyncio.get_event_loop().run_in_executor(None, manual_login_and_capture_cookies)
        if cookies:
            await force_refresh_session()
            return {
                "status": "success",
                "message": f"Manual login completed successfully. Captured {len(cookies)} cookies.",
                "cookie_count": len(cookies)
            }
        else:
            return {"status": "failed", "message": "Manual login failed - no cookies captured"}
    except Exception as e:
        return {"status": "error", "message": f"Manual login failed: {str(e)}"}

@router.get("/session-status")
async def session_status():
    try:
        status = await get_session_status()
        manual_cookies = load_manual_cookies()
        status["manual_cookies_available"] = bool(manual_cookies)
        if manual_cookies:
            status["manual_cookie_count"] = len(manual_cookies)
        return status
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/refresh-session")
async def refresh_session():
    try:
        await force_refresh_session()
        return {"status": "success", "message": "Session refreshed successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Session refresh failed: {str(e)}"}

@router.post("/update-cookies")
async def update_cookies_endpoint(request: Request):
    try:
        body = await request.json()
        if "cookies" not in body:
            raise HTTPException(status_code=400, detail="Missing 'cookies' in request body")
        
        cookies_data = {
            "timestamp": time.time(),
            "url": "https://app.stealthwriter.ai/dashboard",
            "cookies": body["cookies"]
        }
        
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        COOKIES_FILE_PATH = os.path.join(PROJECT_ROOT, "manual_cookies.json")
        
        with open(COOKIES_FILE_PATH, "w") as f:
            json.dump(cookies_data, f, indent=2)
        
        await force_refresh_session()
        
        return {
            "status": "success",
            "message": f"Updated {len(body['cookies'])} cookies and refreshed session",
            "cookie_count": len(body["cookies"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update cookies: {str(e)}")
