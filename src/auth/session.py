import httpx
import os
import asyncio
import time
import json

_master_client = None
_master_client_lock = asyncio.Lock()
_last_refresh = 0
_session_timeout = int(os.getenv("SESSION_TIMEOUT", 3600))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIES_FILE = os.path.join(PROJECT_ROOT, "manual_cookies.json")

def load_manual_cookies():
    """
    Load cookies from manual_cookies.json file and return status dict for UI/health
    """
    status = {
        "exists": False,
        "expired": True,
        "count": 0,
        "age_hours": None,
        "url": None,
        "cookies": [],
        "error": None
    }
    try:
        if not os.path.exists(COOKIES_FILE):
            status["error"] = "manual_cookies.json file not found"
            return status

        with open(COOKIES_FILE, "r") as f:
            cookies_data = json.load(f)

        if isinstance(cookies_data, list):
            cookies_data = {
                "timestamp": time.time(),
                "url": os.getenv("TARGET_URL"),
                "cookies": cookies_data
            }

        cookie_age = time.time() - cookies_data.get("timestamp", time.time())
        max_age = 86400  # 24 hours

        status["exists"] = True
        status["count"] = len(cookies_data.get("cookies", []))
        status["age_hours"] = cookie_age / 3600
        status["url"] = cookies_data.get("url")
        status["cookies"] = cookies_data.get("cookies", [])

        if cookie_age > max_age:
            status["expired"] = True
            status["error"] = f"Manual cookies are {cookie_age/3600:.1f} hours old (max {max_age/3600} hours)"
        else:
            status["expired"] = False

        return status

    except Exception as e:
        status["error"] = f"Failed to load manual cookies: {e}"
        return status

async def get_authenticated_client():
    global _master_client, _last_refresh
    async with _master_client_lock:
        current_time = time.time()
        if (_master_client is None or current_time - _last_refresh > _session_timeout):
            await _refresh_session()
            _last_refresh = current_time
        return _master_client

async def _refresh_session():
    global _master_client
    try:
        if _master_client:
            await _master_client.aclose()
            _master_client = None

        print("🔄 Refreshing session with manual cookies...")
        cookie_status = load_manual_cookies()
        if not cookie_status["exists"] or cookie_status["expired"] or not cookie_status["cookies"]:
            raise Exception(cookie_status.get("error") or "No valid manual cookies available")

        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookie_status["cookies"]}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": os.getenv("TARGET_URL")
        }

        _master_client = httpx.AsyncClient(
            cookies=cookie_dict,
            headers=headers,
            follow_redirects=True,
            timeout=30.0
        )

        # Test session
        test_url = os.getenv("TARGET_URL").rstrip("/") + "/dashboard"
        test_resp = await _master_client.get(test_url)
        if test_resp.status_code == 200 and "dashboard" in test_resp.text.lower():
            print("✅ Session refresh successful!")
        else:
            print(f"⚠️ Test request returned {test_resp.status_code}")
    except Exception as e:
        print(f"❌ Session refresh failed: {str(e)}")
        raise

async def force_refresh_session():
    global _master_client, _last_refresh
    async with _master_client_lock:
        _last_refresh = 0
        return await get_authenticated_client()

async def get_session_status():
    global _master_client, _last_refresh
    cookie_status = load_manual_cookies()
    if _master_client is None:
        return {"status": "no_session", "last_refresh": None, "cookie_status": cookie_status}
    age = time.time() - _last_refresh
    expires_in = _session_timeout - age
    return {
        "status": "active" if expires_in > 0 else "expired",
        "last_refresh": _last_refresh,
        "age_seconds": age,
        "expires_in_seconds": max(0, expires_in),
        "cookie_status": cookie_status
    }
