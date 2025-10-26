from dotenv import load_dotenv
import os

# Load environment variables first
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from api.proxy import router
from auth.selenium_login import get_manual_cookie_status
import json

app = FastAPI(
    title="StealthWriter.ai Proxy Server",
    description="Proxy server for StealthWriter.ai with Cloudflare bypass",
    version="1.0.0"
)

app.include_router(router)

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root endpoint with status and instructions
    """
    cookie_status = get_manual_cookie_status()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>StealthWriter.ai Proxy Server</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .status {{ padding: 15px; margin: 15px 0; border-radius: 5px; }}
            .success {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .warning {{ background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }}
            .error {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
            .info {{ background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }}
            .endpoint {{ background-color: #f8f9fa; padding: 10px; margin: 10px 0; border-left: 4px solid #007bff; }}
            pre {{ background-color: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto; }}
            button {{ background-color: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 5px; }}
            button:hover {{ background-color: #0056b3; }}
            .red {{ background-color: #dc3545; }}
            .red:hover {{ background-color: #c82333; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ StealthWriter.ai Proxy Server</h1>
            <p>Proxy server with Cloudflare Turnstile bypass for StealthWriter.ai</p>
            
            <h2>📊 Status</h2>
            <div class="status {'success' if cookie_status['exists'] and not cookie_status.get('expired', True) else 'warning' if cookie_status['exists'] else 'error'}">
                {'✅' if cookie_status['exists'] and not cookie_status.get('expired', True) else '⚠️' if cookie_status['exists'] else '❌'} 
                Manual Login Cookies: {'Active' if cookie_status['exists'] and not cookie_status.get('expired', True) else 'Expired' if cookie_status['exists'] else 'Not Found'}
                {f"<br>📊 Count: {cookie_status['count']} cookies" if cookie_status['exists'] else ""}
                {f"<br>⏰ Age: {cookie_status['age_hours']:.1f} hours" if cookie_status['exists'] else ""}
                {f"<br>🌐 Last URL: {cookie_status.get('url', 'unknown')}" if cookie_status['exists'] else ""}
            </div>
            
            <h2>🎯 Quick Actions</h2>
            <button onclick="manualLogin()">🔐 Start Manual Login</button>
            <button onclick="checkStatus()">📊 Check Session Status</button>
            <button onclick="refreshSession()" class="red">🔄 Refresh Session</button>
            
            <h2>📋 Available Endpoints</h2>
            
            <div class="endpoint">
                <strong>GET /manual-login</strong><br>
                Start manual login process (opens browser for you to login manually)
            </div>
            
            <div class="endpoint">
                <strong>GET /session-status</strong><br>
                Check current session and cookie status
            </div>
            
            <div class="endpoint">
                <strong>POST /refresh-session</strong><br>
                Force refresh the session using available cookies
            </div>
            
            <div class="endpoint">
                <strong>/{"{"}path{"}"}</strong><br>
                Proxy requests to StealthWriter.ai (after manual login)
            </div>
            
            <h2>🚀 Getting Started</h2>
            <div class="info">
                <h3>First Time Setup:</h3>
                <ol>
                    <li>Click "Start Manual Login" button above</li>
                    <li>Complete the login manually in the browser window</li>
                    <li>Once logged in, the proxy will capture your session cookies</li>
                    <li>You can then use the proxy to access StealthWriter.ai</li>
                </ol>
            </div>
            
            <h2>🔧 Usage Examples</h2>
            <pre>
# Start manual login
curl http://your-server:8000/manual-login

# Check status
curl http://your-server:8000/session-status

# Access StealthWriter.ai dashboard through proxy
curl http://your-server:8000/dashboard

# Access any StealthWriter.ai page through proxy
curl http://your-server:8000/any-path-here
            </pre>
            
            <div id="result" style="margin-top: 20px;"></div>
        </div>
        
        <script>
            async function manualLogin() {{
                const result = document.getElementById('result');
                result.innerHTML = '<div class="status info">🔄 Starting manual login process...</div>';
                
                try {{
                    const response = await fetch('/manual-login');
                    const data = await response.json();
                    
                    if (data.status === 'success') {{
                        result.innerHTML = `<div class="status success">✅ ${{data.message}}</div>`;
                        setTimeout(() => location.reload(), 2000);
                    }} else {{
                        result.innerHTML = `<div class="status error">❌ ${{data.message}}</div>`;
                    }}
                }} catch (error) {{
                    result.innerHTML = `<div class="status error">❌ Error: ${{error.message}}</div>`;
                }}
            }}
            
            async function checkStatus() {{
                const result = document.getElementById('result');
                result.innerHTML = '<div class="status info">🔄 Checking status...</div>';
                
                try {{
                    const response = await fetch('/session-status');
                    const data = await response.json();
                    result.innerHTML = `<div class="status info">📊 Status: <pre>${{JSON.stringify(data, null, 2)}}</pre></div>`;
                }} catch (error) {{
                    result.innerHTML = `<div class="status error">❌ Error: ${{error.message}}</div>`;
                }}
            }}
            
            async function refreshSession() {{
                const result = document.getElementById('result');
                result.innerHTML = '<div class="status info">🔄 Refreshing session...</div>';
                
                try {{
                    const response = await fetch('/refresh-session', {{ method: 'POST' }});
                    const data = await response.json();
                    
                    if (data.status === 'success') {{
                        result.innerHTML = `<div class="status success">✅ ${{data.message}}</div>`;
                    }} else {{
                        result.innerHTML = `<div class="status error">❌ ${{data.message}}</div>`;
                    }}
                }} catch (error) {{
                    result.innerHTML = `<div class="status error">❌ Error: ${{error.message}}</div>`;
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    return html_content

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    cookie_status = get_manual_cookie_status()
    
    return {
        "status": "healthy",
        "manual_cookies": cookie_status,
        "environment": {
            "display": os.getenv("DISPLAY"),
            "headless": os.getenv("SELENIUM_HEADLESS", "false"),
            "target_url": os.getenv("TARGET_URL")
        }
    }
