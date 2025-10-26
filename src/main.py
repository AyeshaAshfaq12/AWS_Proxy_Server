import os

from dotenv import load_dotenv

# Load environment variables first
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from api.proxy import router
from auth.selenium_login import get_manual_cookie_status

app = FastAPI(
    title="StealthWriter.ai Proxy Server",
    description="Proxy server for StealthWriter.ai with Cloudflare bypass",
    version="1.0.0"
)

app.include_router(router)

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root endpoint with status and instructions - No authentication required
    """
    # Get cookie status without triggering authentication
    try:
        cookie_status = get_manual_cookie_status()
    except Exception as e:
        cookie_status = {"exists": False, "error": str(e)}

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
            .green {{ background-color: #28a745; }}
            .green:hover {{ background-color: #218838; }}
            .orange {{ background-color: #fd7e14; }}
            .orange:hover {{ background-color: #e8690b; }}
            .loading {{ opacity: 0.6; pointer-events: none; }}
            textarea {{ width: 100%; height: 150px; margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-family: monospace; }}
            .cookie-section {{ background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border: 1px solid #dee2e6; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ StealthWriter.ai Proxy Server</h1>
            <p>Proxy server with Cloudflare Turnstile bypass for StealthWriter.ai</p>

            <h2>📊 Status</h2>
            <div class="status {'success' if cookie_status.get('exists') and not cookie_status.get('expired', True) else 'warning' if cookie_status.get('exists') else 'error'}">
                {'✅' if cookie_status.get('exists') and not cookie_status.get('expired', True) else '⚠️' if cookie_status.get('exists') else '❌'}
                Manual Login Cookies: {'Active' if cookie_status.get('exists') and not cookie_status.get('expired', True) else 'Expired' if cookie_status.get('exists') else 'Not Found'}
                {f"<br>📊 Count: {cookie_status['count']} cookies" if cookie_status.get('exists') else ""}
                {f"<br>⏰ Age: {cookie_status['age_hours']:.1f} hours" if cookie_status.get('exists') else ""}
                {f"<br>🌐 Last URL: {cookie_status.get('url', 'unknown')}" if cookie_status.get('exists') else ""}
                {f"<br>❌ Error: {cookie_status.get('error', '')}" if cookie_status.get('error') else ""}
            </div>

            <h2>🎯 Quick Actions</h2>
            <button onclick="toggleCookieInput()" class="orange" id="cookieInputBtn">🍪 Set Cookies Manually</button>
            <button onclick="manualLogin()" class="green" id="manualLoginBtn">🔐 Start Manual Login</button>
            <button onclick="checkStatus()" id="statusBtn">📊 Check Session Status</button>
            <button onclick="refreshSession()" class="red" id="refreshBtn">🔄 Refresh Session</button>

            <!-- Manual Cookie Input Section -->
            <div class="cookie-section" id="cookieInputSection" style="display: none;">
                <h3>🍪 Manual Cookie Input</h3>
                <p>Paste your cookies here. You can use either JSON format or browser copy-paste format:</p>

                <div>
                    <label><strong>Cookie Format:</strong></label>
                    <select id="cookieFormat" onchange="updateCookieExample()">
                        <option value="json">JSON Format</option>
                        <option value="browser">Browser Copy-Paste</option>
                    </select>
                </div>

                <textarea id="cookieInput" placeholder="Paste your cookies here..."></textarea>

                <div id="cookieExample" style="margin: 10px 0; padding: 10px; background: #e9ecef; border-radius: 5px; font-size: 0.9em;">
                </div>

                <button onclick="setCookiesManually()" class="green" id="setCookiesBtn">🚀 Set Cookies & Initialize Session</button>
                <button onclick="toggleCookieInput()" class="red">❌ Cancel</button>
            </div>

            <h2>📋 Available Endpoints</h2>

            <div class="endpoint">
                <strong>POST /set-cookies-direct</strong><br>
                Set cookies directly from JSON input (new feature)
            </div>

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
                Proxy requests to StealthWriter.ai (after authentication)
            </div>

            <h2>🚀 Getting Started</h2>
            <div class="info">
                <h3>Option 1: Manual Cookies (Recommended):</h3>
                <ol>
                    <li><strong>Click "Set Cookies Manually" button above</strong></li>
                    <li>Open StealthWriter.ai in your browser and login normally</li>
                    <li>Copy cookies from browser dev tools (F12 → Application → Cookies)</li>
                    <li>Paste them in the text area and click "Set Cookies"</li>
                    <li>Your session will be ready immediately!</li>
                </ol>

                <h3>Option 2: Automated Login:</h3>
                <ol>
                    <li><strong>Click "Start Manual Login" button above</strong></li>
                    <li>Wait for the browser to open (this may take 30-60 seconds)</li>
                    <li>Complete the login manually in the browser window</li>
                    <li>Enter your email and password</li>
                    <li>Complete the Cloudflare Turnstile challenge</li>
                    <li>Navigate to the dashboard</li>
                    <li>Return to the terminal and press Enter to capture cookies</li>
                </ol>

                <h3>⚠️ Important Notes:</h3>
                <ul>
                    <li>Manual cookies method is faster and more reliable</li>
                    <li>Automated login requires terminal interaction</li>
                    <li>The browser runs in virtual display mode (DISPLAY={os.getenv('DISPLAY', 'none')})</li>
                    <li>You may need VNC viewer to see the browser window</li>
                </ul>
            </div>

            <h2>🔧 Usage Examples</h2>
            <pre>
# Set cookies directly via API
curl -X POST http://your-server:8000/set-cookies-direct \\
  -H "Content-Type: application/json" \\
  -d '{{"cookie_name": "cookie_value", "another_cookie": "another_value"}}'

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
            function updateCookieExample() {{
                const format = document.getElementById('cookieFormat').value;
                const exampleDiv = document.getElementById('cookieExample');

                if (format === 'json') {{
                    exampleDiv.innerHTML = `
                        <strong>JSON Example:</strong><br>
                        <code>{{<br>
                        &nbsp;&nbsp;"__Secure-better-auth.session_data": "eyJzZXNzaW9uIjp7InNlc3Npb24i...",<br>
                        &nbsp;&nbsp;"__Secure-better-auth.session_token": "3Nays3AMT1t2B5GjY6HCpfgw...",<br>
                        &nbsp;&nbsp;"_fbp": "fb.1.1761159174437.716440727532027868"<br>
                        }}</code>
                    `;
                }} else {{
                    exampleDiv.innerHTML = `
                        <strong>Browser Copy-Paste Example:</strong><br>
                        <code>__Secure-better-auth.session_data=eyJzZXNzaW9uIjp7InNlc3Npb24i...; __Secure-better-auth.session_token=3Nays3AMT1t2B5GjY6HCpfgw...; _fbp=fb.1.1761159174437.716440727532027868</code>
                    `;
                }}
            }}

            function toggleCookieInput() {{
                const section = document.getElementById('cookieInputSection');
                const btn = document.getElementById('cookieInputBtn');

                if (section.style.display === 'none') {{
                    section.style.display = 'block';
                    btn.textContent = '❌ Hide Cookie Input';
                    updateCookieExample();
                }} else {{
                    section.style.display = 'none';
                    btn.textContent = '🍪 Set Cookies Manually';
                }}
            }}

            function parseCookies(input, format) {{
                if (format === 'json') {{
                    try {{
                        return JSON.parse(input);
                    }} catch (e) {{
                        throw new Error('Invalid JSON format');
                    }}
                }} else {{
                    // Parse browser copy-paste format
                    const cookies = {{}};
                    const parts = input.split(';');

                    for (let part of parts) {{
                        const trimmed = part.trim();
                        if (trimmed && trimmed.includes('=')) {{
                            const [name, ...valueParts] = trimmed.split('=');
                            const value = valueParts.join('='); // In case value contains '='
                            cookies[name.trim()] = value.trim();
                        }}
                    }}

                    return cookies;
                }}
            }}

            async function setCookiesManually() {{
                const input = document.getElementById('cookieInput').value.trim();
                const format = document.getElementById('cookieFormat').value;
                const result = document.getElementById('result');

                if (!input) {{
                    result.innerHTML = '<div class="status error">❌ Please enter cookies</div>';
                    return;
                }}

                setButtonLoading('setCookiesBtn', true);
                result.innerHTML = '<div class="status info">🔄 Setting cookies and initializing session...</div>';

                try {{
                    const cookies = parseCookies(input, format);
                    const cookieCount = Object.keys(cookies).length;

                    if (cookieCount === 0) {{
                        throw new Error('No valid cookies found in input');
                    }}

                    const response = await fetch('/set-cookies-direct', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(cookies)
                    }});

                    const data = await response.json();

                    if (data.status === 'success') {{
                        result.innerHTML = `<div class="status success">✅ ${{data.message}}<br><strong>🔄 Refreshing page in 3 seconds...</strong></div>`;
                        toggleCookieInput(); // Hide the input section
                        setTimeout(() => location.reload(), 3000);
                    }} else {{
                        result.innerHTML = `<div class="status error">❌ ${{data.message}}</div>`;
                    }}

                }} catch (error) {{
                    result.innerHTML = `<div class="status error">❌ Error: ${{error.message}}</div>`;
                }} finally {{
                    setButtonLoading('setCookiesBtn', false);
                }}
            }}

            function setButtonLoading(buttonId, loading) {{
                const btn = document.getElementById(buttonId);
                if (loading) {{
                    btn.classList.add('loading');
                    btn.disabled = true;
                }} else {{
                    btn.classList.remove('loading');
                    btn.disabled = false;
                }}
            }}

            async function manualLogin() {{
                const result = document.getElementById('result');
                setButtonLoading('manualLoginBtn', true);
                result.innerHTML = '<div class="status info">🔄 Starting manual login process...<br><strong>⏳ This may take 30-60 seconds to start the browser. Please wait...</strong></div>';

                try {{
                    const response = await fetch('/manual-login');
                    const data = await response.json();

                    if (data.status === 'success') {{
                        result.innerHTML = `<div class="status success">✅ ${{data.message}}<br><strong>🔄 Refreshing page in 3 seconds...</strong></div>`;
                        setTimeout(() => location.reload(), 3000);
                    }} else if (data.status === 'failed') {{
                        result.innerHTML = `<div class="status warning">⚠️ ${{data.message}}<br><strong>💡 You may need to try again or check the terminal for more details.</strong></div>`;
                    }} else {{
                        result.innerHTML = `<div class="status error">❌ ${{data.message}}<br><strong>🔍 Check the server terminal for detailed error information.</strong></div>`;
                    }}
                }} catch (error) {{
                    result.innerHTML = `<div class="status error">❌ Network Error: ${{error.message}}<br><strong>🔍 The manual login process may still be running in the background. Check the server terminal.</strong></div>`;
                }} finally {{
                    setButtonLoading('manualLoginBtn', false);
                }}
            }}

            async function checkStatus() {{
                const result = document.getElementById('result');
                setButtonLoading('statusBtn', true);
                result.innerHTML = '<div class="status info">🔄 Checking status...</div>';

                try {{
                    const response = await fetch('/session-status');
                    const data = await response.json();

                    let statusClass = 'info';
                    if (data.status === 'active') statusClass = 'success';
                    else if (data.status === 'expired') statusClass = 'warning';
                    else if (data.status === 'error') statusClass = 'error';

                    result.innerHTML = `<div class="status ${{statusClass}}">📊 Status: <pre>${{JSON.stringify(data, null, 2)}}</pre></div>`;
                }} catch (error) {{
                    result.innerHTML = `<div class="status error">❌ Error: ${{error.message}}</div>`;
                }} finally {{
                    setButtonLoading('statusBtn', false);
                }}
            }}

            async function refreshSession() {{
                const result = document.getElementById('result');
                setButtonLoading('refreshBtn', true);
                result.innerHTML = '<div class="status info">🔄 Refreshing session...</div>';

                try {{
                    const response = await fetch('/refresh-session', {{ method: 'POST' }});
                    const data = await response.json();

                    if (data.status === 'success') {{
                        result.innerHTML = `<div class="status success">✅ ${{data.message}}</div>`;
                        setTimeout(() => location.reload(), 2000);
                    }} else {{
                        result.innerHTML = `<div class="status error">❌ ${{data.message}}</div>`;
                    }}
                }} catch (error) {{
                    result.innerHTML = `<div class="status error">❌ Error: ${{error.message}}</div>`;
                }} finally {{
                    setButtonLoading('refreshBtn', false);
                }}
            }}

            // Auto-refresh status every 30 seconds
            setInterval(() => {{
                // Only auto-refresh if no other operation is in progress
                if (!document.querySelector('.loading')) {{
                    checkStatus();
                }}
            }}, 30000);

            // Initialize on page load
            updateCookieExample();
        </script>
    </body>
    </html>
    """

    return html_content

@app.get("/health")
async def health_check():
    """Health check endpoint - No authentication required"""
    try:
        cookie_status = get_manual_cookie_status()
    except Exception as e:
        cookie_status = {"exists": False, "error": str(e)}

    return {
        "status": "healthy",
        "manual_cookies": cookie_status,
        "environment": {
            "display": os.getenv("DISPLAY"),
            "headless": os.getenv("SELENIUM_HEADLESS", "false"),
            "target_url": os.getenv("TARGET_URL")
        }
    }
