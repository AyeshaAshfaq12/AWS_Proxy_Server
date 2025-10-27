import httpx
import os
import asyncio
import time
import json
import random
import hashlib
import base64

_master_client = None
_master_client_lock = asyncio.Lock()
_last_refresh = 0
_session_timeout = int(os.getenv("SESSION_TIMEOUT", 3600))

# Fix: Go up 3 levels from src/auth/session.py to get to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COOKIES_FILE = os.path.join(PROJECT_ROOT, "manual_cookies.json")

def generate_cf_ray():
    """Generate a fake Cloudflare Ray ID"""
    return f"{random.randint(10**15, 10**16-1):x}-{random.choice(['DFW', 'LAX', 'ORD', 'JFK', 'ATL'])}"

def generate_browser_fingerprint():
    """Generate browser fingerprint headers"""
    return {
        "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-platform-version": '"15.0.0"',
        "sec-ch-ua-arch": '"x86"',
        "sec-ch-ua-bitness": '"64"',
        "sec-ch-ua-model": '""',
        "sec-ch-ua-full-version": '"119.0.6045.199"',
        "sec-ch-ua-full-version-list": '"Google Chrome";v="119.0.6045.199", "Chromium";v="119.0.6045.199", "Not?A_Brand";v="24.0.0.0"'
    }

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
        print(f"🔍 Looking for cookies at: {COOKIES_FILE}")  # Debug log
        if not os.path.exists(COOKIES_FILE):
            status["error"] = f"manual_cookies.json file not found at {COOKIES_FILE}"
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
        max_age = 86400 * 7  # 7 days instead of 24 hours

        status["exists"] = True
        status["count"] = len(cookies_data.get("cookies", []))
        status["age_hours"] = cookie_age / 3600
        status["url"] = cookies_data.get("url")
        status["cookies"] = cookies_data.get("cookies", [])

        # Make expiration more lenient for manual cookies
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

        print("🔄 Refreshing session with enhanced Cloudflare bypass...")
        cookie_status = load_manual_cookies()
        if not cookie_status["exists"] or cookie_status["expired"] or not cookie_status["cookies"]:
            raise Exception(cookie_status.get("error") or "No valid manual cookies available")

        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookie_status["cookies"]}
        
        # Add Cloudflare-specific cookies to bypass detection
        cf_cookies = {
            "__cf_bm": base64.b64encode(f"cf_{int(time.time())}_{random.randint(1000,9999)}".encode()).decode()[:64],
            "_cfuvid": f"{random.randint(10**20, 10**21-1):x}",
        }
        cookie_dict.update(cf_cookies)
        
        # Enhanced headers with better fingerprinting
        fingerprint = generate_browser_fingerprint()
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Connection": "keep-alive",
            "CF-RAY": generate_cf_ray(),
            "CF-Visitor": '{"scheme":"https"}',
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
            **fingerprint
        }

        # Create client with enhanced settings and better transport
        transport = httpx.HTTPTransport(
            http2=True,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            ),
            retries=3
        )

        _master_client = httpx.AsyncClient(
            cookies=cookie_dict,
            headers=headers,
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0),
            transport=transport,
            verify=True
        )

        print("✅ Enhanced session created with Cloudflare bypass measures")
            
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
