import httpx
import os
import asyncio
from aws.integration import get_target_credentials
from auth.selenium_login import get_stealthwriter_cookies

_master_client = None
_master_client_lock = asyncio.Lock()

async def get_authenticated_client():
    global _master_client
    async with _master_client_lock:
        if _master_client is None:
            credentials = get_target_credentials()
            # Get cookies from Selenium
            cookies = get_stealthwriter_cookies(credentials["username"], credentials["password"])
            jar = httpx.Cookies()
            for cookie in cookies:
                jar.set(cookie["name"], cookie["value"], domain=cookie.get("domain"), path=cookie.get("path"))
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "identity",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            client = httpx.AsyncClient(headers=headers, cookies=jar, follow_redirects=True)
            _master_client = client
        return _master_client
