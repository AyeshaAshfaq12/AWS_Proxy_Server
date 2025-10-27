from fastapi import APIRouter, Request, Response, HTTPException
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
from auth.selenium_login import manual_login_and_capture_cookies, load_manual_cookies
import os
import asyncio
import time
import json

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
        "content-length", "server", "x-frame-options", "cf-ray"
    }
    
    for k, v in headers.items():
        if k.lower() in skip_headers:
            continue
        
        if isinstance(v, str):
            clean_value = v.replace('\n', ' ').replace('\r', ' ').strip()
            if clean_value and len(clean_value) < 8192:
                filtered_headers[k] = clean_value
    
    return filtered_headers

def handle_403_response(target_url: str) -> Response:
    """Handle Cloudflare 403 responses with helpful error page"""
    error_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Session Refresh Required</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f8fafc; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .error {{ background: #ffebee; padding: 20px; border-radius: 8px; border-left: 4px solid #f44336; margin: 15px 0; }}
            .solution {{ background: #e8f5e8; padding: 20px; border-radius: 8px; border-left: 4px solid #4caf50; margin: 15px 0; }}
            .code {{ background: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace; margin: 10px 0; }}
            button {{ background: #007bff; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-size: 16px; margin: 10px 5px; }}
            button:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ Cloudflare Protection Detected</h1>
            
            <div class="error">
                <h3>❌ Access Blocked</h3>
                <p><strong>Cloudflare is blocking access to the StealthWriter dashboard.</strong></p>
                <p>The manual cookies may need to be refreshed or may be detected as automated.</p>
                <p><strong>Target URL:</strong> {target_url}</p>
            </div>
            
            <div class="solution">
                <h3>🔧 Solution: Get Fresh Session</h3>
                <p><strong>Manual steps to get working cookies:</strong></p>
                <ol>
                    <li>Open a fresh browser window/incognito mode</li>
                    <li>Go to StealthWriter.ai and log in normally</li>
                    <li>Stay on the dashboard page for 1-2 minutes</li>
                    <li>Export cookies using a browser extension (Cookie Editor, etc.)</li>
                    <li>Update your manual_cookies.json file</li>
                    <li>Restart this proxy server</li>
                </ol>
                
                <p><strong>Try automated login (if display available):</strong></p>
                <div class="code">
                    <button onclick="getCookies()">🍪 Automated Login</button>
                    <button onclick="refreshSession()">🔄 Refresh Session</button>
                </div>
            </div>
            
            <div id="result" style="margin-top: 20px;"></div>
        </div>
        
        <script>
            async function getCookies() {{
                const result = document.getElementById('result');
                result.innerHTML = '<p>🔄 Starting automated login...</p>';
                
                try {{
                    const response = await fetch('/manual-login');
                    const data = await response.json();
                    
                    if (data.status === 'success') {{
                        result.innerHTML = '<div class="solution"><p>✅ Fresh cookies captured! Please restart the server.</p></div>';
                    }} else {{
                        result.innerHTML = '<div class="error"><p>❌ Login failed: ' + data.message + '</p></div>';
                    }}
                }} catch (e) {{
                    result.innerHTML = '<div class="error"><p>❌ Error: ' + e.message + '</p></div>';
                }}
            }}
            
            async function refreshSession() {{
                const result = document.getElementById('result');
                result.innerHTML = '<p>🔄 Refreshing session...</p>';
                
                try {{
                    const response = await fetch('/refresh-session', {{ method: 'POST' }});
                    const data = await response.json();
                    
                    if (data.status === 'success') {{
                        result.innerHTML = '<div class="solution"><p>✅ Session refreshed! Try again.</p></div>';
                    }} else {{
                        result.innerHTML = '<div class="error"><p>❌ Refresh failed: ' + data.message + '</p></div>';
                    }}
                }} catch (e) {{
                    result.innerHTML = '<div class="error"><p>❌ Error: ' + e.message + '</p></div>';
                }}
            }}
        </script>
    </body>
    </html>
    """
    return Response(content=error_html, status_code=403, headers={"Content-Type": "text/html"})

def fetch_html_with_selenium(url: str, cookies: list) -> str:
    """Use Selenium to fetch HTML content with real browser and cookies"""
    options = Options()
    # Do NOT use headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    driver = webdriver.Chrome(options=options)
    driver.get("https://app.stealthwriter.ai/")
    for cookie in cookies:
        # Selenium expects cookie dict keys: name, value, domain, path, secure, httpOnly, expiry
        cookie_dict = {k: v for k, v in cookie.items() if k in ["name", "value", "domain", "path", "secure", "httpOnly", "expiry"]}
        driver.add_cookie(cookie_dict)
    driver.get(url)
    try:
        # Wait up to 30 seconds for dashboard sidebar to appear
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-slot="sidebar-wrapper"]'))
        )
    except Exception:
        time.sleep(10)  # fallback wait
    html = driver.page_source
    driver.quit()
    return html

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_request(path: str, request: Request):
    """Main proxy endpoint - simplified approach"""
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

        # Simple headers for better compatibility
        content_type = get_content_type(target_url)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://app.stealthwriter.ai/dashboard",
            "Origin": "https://app.stealthwriter.ai",
            "Sec-Fetch-Site": "same-origin",
            "DNT": "1"
        }
        
        # Set Accept header based on content type
        if content_type == 'text/css':
            headers["Accept"] = "text/css,*/*;q=0.1"
        elif content_type == 'application/javascript':
            headers["Accept"] = "*/*"
        elif content_type.startswith('image/'):
            headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        else:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"

        body = await request.body()

        # Robust: Use Selenium for HTML pages, HTTPX for assets
        if content_type == "text/html":
            try:
                cookies = cookie_status.get("cookies", [])
                html = fetch_html_with_selenium(target_url, cookies)
                return Response(
                    content=html,
                    status_code=200,
                    headers={
                        "Content-Type": "text/html",
                        "Access-Control-Allow-Origin": "*",
                        "Cache-Control": "no-cache"
                    }
                )
            except Exception as e:
                print(f"❌ Selenium fetch failed: {str(e)}")
                return handle_403_response(target_url)
        else:
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
