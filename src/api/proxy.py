from fastapi import APIRouter, Request, Response, HTTPException
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
from auth.selenium_login import manual_login_and_capture_cookies, load_manual_cookies
import os
import asyncio
import time
import json

router = APIRouter()

def get_content_type(url: str) -> str:
    """Determine content type based on file extension"""
    if url.endswith('.css'):
        return 'text/css'
    elif url.endswith('.js'):
        return 'application/javascript'
    elif url.endswith('.woff') or url.endswith('.woff2'):
        return 'font/woff2'
    elif url.endswith('.ttf'):
        return 'font/ttf'
    elif url.endswith('.svg'):
        return 'image/svg+xml'
    elif url.endswith('.png'):
        return 'image/png'
    elif url.endswith('.jpg') or url.endswith('.jpeg'):
        return 'image/jpeg'
    elif url.endswith('.gif'):
        return 'image/gif'
    elif url.endswith('.ico'):
        return 'image/x-icon'
    else:
        return 'text/html'

def clean_headers(headers: dict) -> dict:
    """Clean and filter response headers"""
    filtered_headers = {}
    skip_headers = {
        "content-encoding", "transfer-encoding", "connection", 
        "content-length", "server", "x-frame-options"
    }
    
    for k, v in headers.items():
        if k.lower() in skip_headers:
            continue
        
        if isinstance(v, str):
            clean_value = v.replace('\n', ' ').replace('\r', ' ').strip()
            if clean_value and len(clean_value) < 8192:
                filtered_headers[k] = clean_value
    
    return filtered_headers

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_request(path: str, request: Request):
    """Main proxy endpoint using HTTPX only"""
    try:
        # Check session status
        session_status = await get_session_status()
        cookie_status = session_status.get("cookie_status", {})
        
        if not cookie_status.get("exists") or cookie_status.get("expired", True):
            raise HTTPException(
                status_code=401,
                detail=f"Session unavailable: {cookie_status.get('error', 'No valid cookies')}"
            )

        client = await get_authenticated_client()
        
        # Handle root path
        if path == "" or path == "/":
            path = "dashboard"
        
        target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
        
        # Add query parameters
        if request.query_params:
            query_string = str(request.query_params)
            target_url += f"?{query_string}"

        # Enhanced headers for different asset types
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Referer": "https://app.stealthwriter.ai/dashboard",
        }
        
        # Set specific Accept header based on content type
        content_type = get_content_type(target_url)
        if content_type == 'text/css':
            headers["Accept"] = "text/css,*/*;q=0.1"
            headers["Sec-Fetch-Dest"] = "style"
            headers["Sec-Fetch-Mode"] = "no-cors"
        elif content_type == 'application/javascript':
            headers["Accept"] = "*/*"
            headers["Sec-Fetch-Dest"] = "script"
            headers["Sec-Fetch-Mode"] = "no-cors"
        elif content_type.startswith('font/'):
            headers["Accept"] = "*/*"
            headers["Sec-Fetch-Dest"] = "font"
            headers["Sec-Fetch-Mode"] = "cors"
        elif content_type.startswith('image/'):
            headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            headers["Sec-Fetch-Dest"] = "image"
            headers["Sec-Fetch-Mode"] = "no-cors"
        else:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-User"] = "?1"
            headers["Upgrade-Insecure-Requests"] = "1"

        headers["Sec-Fetch-Site"] = "same-origin"

        body = await request.body()
        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )
        
        filtered_headers = clean_headers(response.headers)
        
        filtered_headers.update({
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Cache-Control": "public, max-age=3600" if content_type != 'text/html' else "no-cache"
        })
        
        if response.status_code == 200:
            asset_type = "asset" if content_type != 'text/html' else "page"
            print(f"✅ Proxy {asset_type}: {target_url}")
        else:
            print(f"⚠️ Proxy returned {response.status_code}: {target_url}")
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=filtered_headers
        )
        
    except Exception as e:
        print(f"❌ Proxy error: {str(e)}")
        return Response(
            content=f"<html><body><h1>Proxy Error</h1><p>{str(e)}</p></body></html>",
            status_code=500,
            headers={"Content-Type": "text/html"}
        )

@router.get("/manual-login")
async def manual_login_endpoint():
    """Trigger manual login process"""
    try:
        print("🚀 Starting manual login process...")
        cookies = await asyncio.get_event_loop().run_in_executor(None, manual_login_and_capture_cookies)
        if cookies:
            await force_refresh_session()
            return {
                "status": "success",
                "message": f"Manual login completed. Captured {len(cookies)} cookies.",
                "cookie_count": len(cookies)
            }
        else:
            return {"status": "failed", "message": "Manual login failed - no cookies captured"}
    except Exception as e:
        return {"status": "error", "message": f"Manual login failed: {str(e)}"}

@router.get("/session-status")
async def session_status():
    """Check current session status"""
    try:
        return await get_session_status()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/refresh-session")
async def refresh_session():
    """Force refresh session"""
    try:
        await force_refresh_session()
        return {"status": "success", "message": "Session refreshed successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Session refresh failed: {str(e)}"}

@router.post("/update-cookies")
async def update_cookies_endpoint(request: Request):
    """Update cookies via API"""
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
