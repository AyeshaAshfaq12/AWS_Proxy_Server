from dotenv import load_dotenv
import os

# Load environment variables first
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from api.proxy import router
from auth.selenium_login import load_manual_cookies
from auth.browser_session import _browser_session
import json
import atexit

app = FastAPI(
    title="StealthWriter.ai Proxy Server",
    description="Browser-based proxy server for StealthWriter.ai with Cloudflare bypass",
    version="1.0.0"
)

app.include_router(router)

# Cleanup browser session on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    global _browser_session
    if _browser_session:
        await _browser_session.close()

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root endpoint with status and instructions
    """
    cookie_status = load_manual_cookies()
    if hasattr(cookie_status, 'get'):
        # New format with status dict
        status_text = 'Active' if cookie_status.get('exists') and not cookie_status.get('expired', True) else 'Expired' if cookie_status.get('exists') else 'Not Found'
        error_text = cookie_status.get('error', '')
    else:
        # Old format - just cookies list or None
        status_text = 'Active' if cookie_status else 'Not Found'
        error_text = ''
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>StealthWriter.ai Browser Proxy Server</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            .status {{ padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .success {{ background: #d4edda; border-left: 4px solid #28a745; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; }}
            .error {{ background: #f8d7da; border-left: 4px solid #dc3545; }}
            .endpoint {{ background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 3px; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ StealthWriter.ai Browser Proxy Server</h1>
            <p>Browser-based proxy server with Playwright for reliable Cloudflare bypass</p>
            
            <h2>📊 Status</h2>
            <div class="status {'success' if status_text == 'Active' else 'warning' if status_text == 'Expired' else 'error'}">
                {'✅' if status_text == 'Active' else '⚠️' if status_text == 'Expired' else '❌'} 
                Manual Login Cookies: {status_text}
                {f"<br>❌ Error: {error_text}" if error_text else ""}
            </div>
            
            <h2>🔗 Available Endpoints</h2>
            <div class="endpoint">GET /dashboard - Access StealthWriter dashboard</div>
            <div class="endpoint">GET /session-status - Check session status</div>
            <div class="endpoint">POST /refresh-session - Refresh browser session</div>
            <div class="endpoint">GET /manual-login - Trigger manual login</div>
            <div class="endpoint">POST /update-cookies - Update cookies via API</div>
            
            <h2>🚀 How to Use</h2>
            <ol>
                <li>Ensure you have valid cookies in manual_cookies.json</li>
                <li>Access any StealthWriter page via: <code>http://your-server:8000/dashboard</code></li>
                <li>The browser proxy will handle Cloudflare challenges automatically</li>
                <li>Multiple clients can share the same authenticated session</li>
            </ol>
            
            <h2>🔧 Browser Proxy Features</h2>
            <ul>
                <li>✅ Real browser engine (Chromium via Playwright)</li>
                <li>✅ Automatic Cloudflare challenge solving</li>
                <li>✅ JavaScript execution support</li>
                <li>✅ Stealth mode to avoid detection</li>
                <li>✅ Session persistence and sharing</li>
            </ul>
        </div>
    </body>
    </html>
    """
    return html_content

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    cookie_status = load_manual_cookies()
    return {
        "status": "healthy",
        "proxy_type": "browser_based",
        "manual_cookies": cookie_status if hasattr(cookie_status, 'get') else {"exists": bool(cookie_status)},
        "environment": {
            "display": os.getenv("DISPLAY"),
            "headless": os.getenv("SELENIUM_HEADLESS", "false"),
            "target_url": os.getenv("TARGET_URL")
        }
    }
