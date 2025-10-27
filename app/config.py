import os
from typing import Dict

class Config:
    PROXY_BASE_URL: str = os.getenv("PROXY_BASE_URL", "http://localhost:8080")
    TARGET_BASE_URL: str = os.getenv("TARGET_BASE_URL", "https://app.stealthwriter.ai")
    API_KEY: str = os.getenv("API_KEY", "")
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")
    SESSION_COOKIE_STRING: str = os.getenv("SESSION_COOKIE_STRING", "")  # "a=1; b=2"


def parse_cookie_string(cookie_str: str) -> Dict[str, str]:
    """Parse 'a=1; b=2' into dict."""
    cookies = {}
    if not cookie_str:
        return cookies
    parts = [p.strip() for p in cookie_str.split(";") if p.strip()]
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies
