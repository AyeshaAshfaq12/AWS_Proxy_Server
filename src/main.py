from dotenv import load_dotenv
import os

# Load environment variables first
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from api.proxy import router
from auth.selenium_login import load_manual_cookies
import json
import atexit

app = FastAPI(
    title="StealthWriter.ai Proxy Server",
    description="Enhanced proxy server for StealthWriter.ai with robust asset handling",
    version="2.0.0"
)

app.include_router(router)

# Cleanup browser session on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    try:
        from auth.browser_session import _browser_session
        if _browser_session:
            await _browser_session.close()
    except ImportError:
        pass

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with enhanced status and instructions"""
    cookie_status = load_manual_cookies()
    if hasattr(cookie_status, 'get'):
        status_text = 'Active' if cookie_status.get('exists') and not cookie_status.get('expired', True) else 'Expired' if cookie_status.get('exists') else 'Not Found'
        error_text = cookie_status.get('error', '')
    else:
        status_text = 'Active' if cookie_status else 'Not Found'
        error_text = ''
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>StealthWriter.ai Enhanced Proxy Server</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f8fafc; }}
            .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .status {{ padding: 20px; border-radius: 8px; margin: 15px 0; }}
            .success {{ background: #d4edda; border-left: 5px solid #28a745; }}
            .warning {{ background: #fff3cd; border-left: 5px solid #ffc107; }}
            .error {{ background: #f8d7da; border-left: 5px solid #dc3545; }}
            .endpoint {{ background: #f8f9fa; padding: 12px; margin: 8px 0; border-radius: 6px; font-family: 'Monaco', monospace; border-left: 3px solid #007bff; }}
            .feature {{ background: #e7f3ff; padding: 15px; margin: 10px 0; border-radius: 6px; }}
            h1 {{ color: #2c3e50; margin-bottom: 10px; }}
            h2 {{ color: #34495e; margin-top: 30px; }}
            .badge {{ display: inline-block; padding: 4px 8px; background: #007bff; color: white; border-radius: 4px; font-size: 12px; margin-left: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ StealthWriter.ai Enhanced Proxy Server <span class="badge">v2.0</span></h1>
            <p>Advanced proxy server with intelligent asset handling and Cloudflare bypass capabilities</p>
            
            <h2>📊 Current Status</h2>
            <div class="status {'success' if status_text == 'Active' else 'warning' if status_text == 'Expired' else 'error'}">
                {'✅' if status_text == 'Active' else '⚠️' if status_text == 'Expired' else '❌'} 
                <strong>Authentication Cookies:</strong> {status_text}
                {f"<br><small>❌ Error: {error_text}</small>" if error_text else ""}
            </div>
            
            <h2>🔗 API Endpoints</h2>
            <div class="endpoint">GET /dashboard - Access StealthWriter dashboard</div>
            <div class="endpoint">GET /session-status - Check session and cookie status</div>
            <div class="endpoint">POST /refresh-session - Force refresh all sessions</div>
            <div class="endpoint">GET /manual-login - Trigger manual login flow</div>
            <div class="endpoint">POST /update-cookies - Update cookies via API</div>
            <div class="endpoint">GET /health - System health check</div>
            
            <h2>🚀 Enhanced Features</h2>
            <div class="feature">
                <strong>✅ Smart Asset Handling:</strong> Optimized loading of CSS, JS, fonts, and images
            </div>
            <div class="feature">
                <strong>✅ Browser Engine:</strong> Real Chromium browser for authentic requests
            </div>
            <div class="feature">
                <strong>✅ Fallback System:</strong> Automatic fallback to HTTPX if browser fails
            </div>
            <div class="feature">
                <strong>✅ Cloudflare Bypass:</strong> Advanced techniques to bypass protection
            </div>
            <div class="feature">
                <strong>✅ Session Sharing:</strong> Multiple clients can share authenticated session
            </div>
            
            <h2>🎯 Usage Instructions</h2>
            <ol>
                <li><strong>Ensure valid cookies:</strong> Check that manual_cookies.json contains fresh authentication cookies</li>
                <li><strong>Access dashboard:</strong> Navigate to <code>http://your-server:8000/dashboard</code></li>
                <li><strong>Static assets:</strong> CSS, JS, and images are automatically handled and optimized</li>
                <li><strong>Monitor status:</strong> Use <code>/session-status</code> to monitor authentication health</li>
            </ol>
            
            <h2>🔧 Performance Improvements</h2>
            <ul>
                <li>Separate handling for static assets (CSS, JS, fonts)</li>
                <li>Optimized browser settings for faster loading</li>
                <li>Intelligent content-type detection</li>
                <li>Enhanced header filtering and CORS support</li>
                <li>Reduced navigation timeouts for better responsiveness</li>
            </ul>
            
            <p><small>Server running on port 8000 • Enhanced proxy with asset optimization</small></p>
        </div>
    </body>
    </html>
    """
    return html_content

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint"""
    cookie_status = load_manual_cookies()
    
    # Check browser session availability
    browser_available = False
    try:
        from auth.browser_session import get_browser_session
        browser_available = True
    except ImportError:
        pass
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "features": {
            "browser_session": browser_available,
            "asset_optimization": True,
            "fallback_system": True,
            "cloudflare_bypass": True
        },
        "manual_cookies": cookie_status if hasattr(cookie_status, 'get') else {"exists": bool(cookie_status)},
        "environment": {
            "target_url": os.getenv("TARGET_URL"),
            "session_timeout": os.getenv("SESSION_TIMEOUT", "3600"),
            "headless_mode": os.getenv("SELENIUM_HEADLESS", "false")
        }
    }
