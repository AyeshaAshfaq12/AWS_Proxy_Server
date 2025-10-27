from fastapi import APIRouter, Request, Response, HTTPException
from httpx import AsyncClient, RequestError
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
from auth.selenium_login import manual_login_and_capture_cookies, load_manual_cookies
import os
import asyncio
import time
import json
import mimetypes

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
            # Remove newlines and other problematic characters
            clean_value = v.replace('\n', ' ').replace('\r', ' ').strip()
            if clean_value and len(clean_value) < 8192:
                filtered_headers[k] = clean_value
    
    return filtered_headers

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def smart_proxy(path: str, request: Request):
    """
    Smart proxy that uses browser session for better compatibility
    """
    try:
        # Try browser session first
        try:
            from auth.browser_session import get_browser_session
            browser_session = await get_browser_session()
            
            # Handle root path
            if path == "" or path == "/":
                path = "dashboard"
            
            target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
            
            # Add query parameters if any
            if request.query_params:
                query_string = str(request.query_params)
                target_url += f"?{query_string}"
            
            body = await request.body()
            
            # Make request using browser
            result = await browser_session.make_request(
                method=request.method,
                url=target_url,
                headers=dict(request.headers),
                data=body if body else None
            )
            
            # Determine content type
            content_type = get_content_type(target_url)
            
            # Clean headers
            filtered_headers = clean_headers(result.get('headers', {}))
            
            # Add essential headers
            filtered_headers.update({
                "Content-Type": content_type,
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Cache-Control": "public, max-age=3600" if content_type != 'text/html' else "no-cache"
            })
            
            status_code = result['status_code']
            content = result['content']
            
            # Log successful requests
            if status_code == 200:
                asset_type = "asset" if content_type != 'text/html' else "page"
                print(f"✅ Browser proxy {asset_type}: {target_url}")
            else:
                print(f"⚠️ Browser proxy returned {status_code}: {target_url}")
            
            return Response(
                content=content,
                status_code=status_code,
                headers=filtered_headers
            )
            
        except ImportError:
            print("⚠️ Browser session not available, using HTTPX fallback")
            return await httpx_fallback(path, request)
        except Exception as e:
            print(f"⚠️ Browser session error: {e}, using HTTPX fallback")
            return await httpx_fallback(path, request)
            
    except Exception as e:
        print(f"❌ Proxy error: {str(e)}")
        return Response(
            content=f"<html><body><h1>Proxy Error</h1><p>{str(e)}</p></body></html>",
            status_code=500,
            headers={"Content-Type": "text/html"}
        )

async def httpx_fallback(path: str, request: Request):
    """HTTPX fallback proxy"""
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
        
        if path == "" or path == "/":
            path = "dashboard"
        
        target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
        
        if request.query_params:
            query_string = str(request.query_params)
            target_url += f"?{query_string}"

        # Enhanced headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "max-age=0",
            "Referer": "https://app.stealthwriter.ai/dashboard",
        }

        body = await request.body()
        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )
        
        content_type = get_content_type(target_url)
        filtered_headers = clean_headers(response.headers)
        
        filtered_headers.update({
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600" if content_type != 'text/html' else "no-cache"
        })
        
        if response.status_code == 200:
            print(f"✅ HTTPX fallback successful: {target_url}")
        else:
            print(f"⚠️ HTTPX fallback returned {response.status_code}: {target_url}")
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=filtered_headers
        )
        
    except Exception as e:
        print(f"❌ HTTPX fallback error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fallback proxy error: {str(e)}")

@router.get("/manual-login")
async def manual_login_endpoint():
    """Trigger manual login process"""
    try:
        print("🚀 Starting manual login process...")
        cookies = await asyncio.get_event_loop().run_in_executor(None, manual_login_and_capture_cookies)
        if cookies:
            await force_refresh_session()
            # Refresh browser session if available
            try:
                from auth.browser_session import refresh_browser_session
                await refresh_browser_session()
            except ImportError:
                pass
            
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
        status = await get_session_status()
        manual_cookies = load_manual_cookies()
        status["manual_cookies_available"] = bool(manual_cookies)
        if manual_cookies:
            status["manual_cookie_count"] = len(manual_cookies)
        
        # Check browser session if available
        try:
            from auth.browser_session import get_browser_session
            browser_session = await get_browser_session()
            status["browser_session_active"] = browser_session is not None
        except Exception:
            status["browser_session_active"] = False
            
        return status
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/refresh-session")
async def refresh_session():
    """Force refresh both HTTP and browser sessions"""
    try:
        await force_refresh_session()
        # Refresh browser session if available
        try:
            from auth.browser_session import refresh_browser_session
            await refresh_browser_session()
        except ImportError:
            pass
        
        return {"status": "success", "message": "Sessions refreshed successfully"}
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
        # Refresh browser session if available
        try:
            from auth.browser_session import refresh_browser_session
            await refresh_browser_session()
        except ImportError:
            pass
        
        return {
            "status": "success",
            "message": f"Updated {len(body['cookies'])} cookies and refreshed sessions",
            "cookie_count": len(body["cookies"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update cookies: {str(e)}")
