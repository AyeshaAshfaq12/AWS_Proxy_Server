import httpx
import os
import asyncio
import time
import json
from aws.integration import get_target_credentials
from .selenium_login import get_stealthwriter_cookies, load_manual_cookies

_master_client = None
_master_client_lock = asyncio.Lock()
_last_refresh = 0
_session_timeout = int(os.getenv("SESSION_TIMEOUT", 3600))

async def get_authenticated_client():
    global _master_client, _last_refresh
    async with _master_client_lock:
        current_time = time.time()
        
        # Check if we need to refresh the session
        if (_master_client is None or 
            current_time - _last_refresh > _session_timeout):
            
            await _refresh_session()
            _last_refresh = current_time
        
        return _master_client

async def _refresh_session():
    global _master_client
    
    try:
        # Close existing client if it exists
        if _master_client:
            await _master_client.aclose()
            _master_client = None
        
        print("🔄 Refreshing session...")
        
        # First, try to load manual cookies
        cookies = load_manual_cookies()
        
        if cookies:
            print(f"✅ Using manual cookies ({len(cookies)} found)")
        else:
            print("❌ No manual cookies found, trying automated login...")
            # Get credentials from AWS SSM for automated login
            credentials = get_target_credentials()
            
            # Use Selenium to get fresh cookies with Cloudflare bypass
            print("Refreshing session with Selenium...")
            cookies = await asyncio.get_event_loop().run_in_executor(
                None, 
                get_stealthwriter_cookies,
                credentials['username'],
                credentials['password']
            )
        
        if not cookies:
            raise Exception("No cookies available from any method")
        
        # Convert cookies to httpx format
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        
        # Create new HTTP client with cookies and proper headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        
        _master_client = httpx.AsyncClient(
            cookies=cookie_dict,
            headers=headers,
            follow_redirects=True,
            timeout=30.0
        )
        
        # Verify the session works by making a test request
        test_url = os.getenv("TARGET_URL").rstrip("/") + "/dashboard"
        test_resp = await _master_client.get(test_url)
        
        if test_resp.status_code == 200:
            if "dashboard" in test_resp.text.lower() or "app.stealthwriter.ai" in test_resp.url:
                print("✅ Session refresh successful!")
                
                # Save cookies for persistence (optional)
                await _save_cookies_to_file(cookies)
            else:
                print("⚠️  Got 200 but content doesn't look like dashboard")
                # Still proceed as it might be valid
        else:
            print(f"⚠️  Test request returned {test_resp.status_code}, but proceeding anyway")
            
    except Exception as e:
        print(f"❌ Session refresh failed: {str(e)}")
        # Try to load cookies from file as fallback
        if await _load_cookies_from_file():
            print("✅ Loaded cookies from backup file as fallback")
        else:
            raise Exception(f"Failed to refresh session and no fallback available: {str(e)}")

async def _save_cookies_to_file(cookies):
    """Save cookies to file for persistence across restarts"""
    try:
        cookies_file = "session_cookies.json"
        cookie_data = {
            "timestamp": time.time(),
            "cookies": cookies
        }
        
        with open(cookies_file, "w") as f:
            json.dump(cookie_data, f, indent=2)
        
        print(f"💾 Cookies saved to {cookies_file}")
    except Exception as e:
        print(f"❌ Failed to save cookies: {e}")

async def _load_cookies_from_file():
    """Load cookies from file if they're still valid"""
    try:
        cookies_file = "session_cookies.json"
        
        if not os.path.exists(cookies_file):
            return False
        
        with open(cookies_file, "r") as f:
            cookie_data = json.load(f)
        
        # Check if cookies are still fresh (within timeout period)
        cookie_age = time.time() - cookie_data["timestamp"]
        if cookie_age > _session_timeout:
            print(f"⏰ Saved cookies are {cookie_age/3600:.1f} hours old (expired)")
            return False
        
        # Convert cookies and create client
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookie_data["cookies"]}
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        global _master_client
        _master_client = httpx.AsyncClient(
            cookies=cookie_dict,
            headers=headers,
            follow_redirects=True,
            timeout=30.0
        )
        
        # Test the loaded cookies
        test_url = os.getenv("TARGET_URL").rstrip("/") + "/dashboard"
        test_resp = await _master_client.get(test_url)
        
        if test_resp.status_code == 200:
            print("✅ Loaded cookies are valid")
            return True
        else:
            print(f"❌ Loaded cookies are invalid (status: {test_resp.status_code})")
            await _master_client.aclose()
            _master_client = None
            return False
            
    except Exception as e:
        print(f"❌ Failed to load cookies from file: {e}")
        return False

async def force_refresh_session():
    """Force a session refresh (useful for manual triggers)"""
    global _master_client, _last_refresh
    async with _master_client_lock:
        _last_refresh = 0  # Force refresh
        return await get_authenticated_client()

async def get_session_status():
    """Get current session status for monitoring"""
    global _master_client, _last_refresh
    
    if _master_client is None:
        return {"status": "no_session", "last_refresh": None}
    
    age = time.time() - _last_refresh
    expires_in = _session_timeout - age
    
    return {
        "status": "active" if expires_in > 0 else "expired",
        "last_refresh": _last_refresh,
        "age_seconds": age,
        "expires_in_seconds": max(0, expires_in)
    }
