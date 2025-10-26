def structured_log(message: str, **kwargs) -> None:
    import structlog

    logger = structlog.get_logger()
    logger.info(message, **kwargs)

def filter_headers(headers: dict) -> dict:
    sensitive_headers = ['Authorization', 'Cookie']
    return {k: v for k, v in headers.items() if k not in sensitive_headers}

import json
from typing import Dict

import requests


def convert_browser_cookies_to_json(cookie_string: str) -> Dict[str, str]:
    """
    Convert browser copy-paste cookies to JSON format

    Args:
        cookie_string: Cookie string like "name1=value1; name2=value2"

    Returns:
        Dictionary of cookie name-value pairs
    """
    cookies = {}
    if not cookie_string:
        return cookies

    for cookie in cookie_string.split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            name, value = cookie.split('=', 1)
            cookies[name.strip()] = value.strip()

    return cookies

def format_cookies_for_stealthwriter(cookies: Dict[str, str]) -> Dict[str, str]:
    """
    Format and validate cookies for StealthWriter.ai

    Args:
        cookies: Raw cookie dictionary

    Returns:
        Formatted cookie dictionary
    """
    # Known important cookies for StealthWriter.ai
    important_cookies = [
        '__Secure-better-auth.session_data',
        '__Secure-better-auth.session_token',
        '_fbp',
        '_gcl_au',
        'intercom-device-id-esc25l7u',
        'intercom-session-esc25l7u'
    ]

    formatted_cookies = {}

    # Include all provided cookies
    for name, value in cookies.items():
        if name and value:  # Only include non-empty cookies
            formatted_cookies[name] = value

    # Check if we have the essential auth cookies
    auth_cookies = [name for name in formatted_cookies.keys() if 'auth' in name.lower() or 'session' in name.lower()]

    if not auth_cookies:
        print("⚠️  Warning: No authentication cookies found. The session may not work.")

    print(f"✅ Formatted {len(formatted_cookies)} cookies")
    print(f"🔑 Authentication cookies found: {auth_cookies}")

    return formatted_cookies

def test_proxy_session(proxy_url: str = "http://localhost:8000") -> bool:
    """
    Test if the proxy session is working

    Args:
        proxy_url: URL of the proxy server

    Returns:
        True if session is working, False otherwise
    """
    try:
        # Test session status
        response = requests.get(f"{proxy_url}/session-status", timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"📊 Session Status: {data}")
            return data.get('status') == 'active'
        else:
            print(f"❌ Session status check failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error testing session: {e}")
        return False

def setup_cookies_from_browser():
    """
    Interactive helper to set up cookies from browser
    """
    print("🍪 Cookie Setup Helper")
    print("=" * 50)
    print()
    print("1. Login to https://app.stealthwriter.ai in your browser")
    print("2. Open Developer Tools (F12)")
    print("3. Go to Application/Storage → Cookies → https://app.stealthwriter.ai")
    print("4. Copy all cookies (you can select all and copy)")
    print()

    # Get cookies from user
    print("📋 Paste your cookies here (format: name1=value1; name2=value2):")
    cookie_input = input().strip()

    if not cookie_input:
        print("❌ No cookies provided")
        return False

    try:
        # Convert to JSON format
        cookies = convert_browser_cookies_to_json(cookie_input)

        if not cookies:
            print("❌ No valid cookies found")
            return False

        # Format for StealthWriter
        formatted_cookies = format_cookies_for_stealthwriter(cookies)

        # Send to proxy server
        proxy_url = input("🌐 Enter proxy URL (default: http://localhost:8000): ").strip()
        if not proxy_url:
            proxy_url = "http://localhost:8000"

        print(f"🚀 Setting cookies on {proxy_url}...")

        response = requests.post(
            f"{proxy_url}/set-cookies-direct",
            json=formatted_cookies,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print(f"✅ {data['message']}")

                # Test the session
                print("🧪 Testing session...")
                if test_proxy_session(proxy_url):
                    print("🎉 Success! Your proxy is ready to use!")
                    print(f"🌐 Access your proxied session at: {proxy_url}")
                    return True
                else:
                    print("⚠️  Cookies set but session test failed")
                    return False
            else:
                print(f"❌ Failed: {data.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Example usage
    your_cookies = {
        "__Secure-better-auth.session_data": "eyJzZXNzaW9uIjp7InNlc3Npb24iOnsiZXhwaXJlc0F0IjoiMjAyNS0xMS0wMlQxNjo0MToxNC41NTBaIiwidG9rZW4iOiIzTmF5czNBTVQxdDJCNUdqWTZIQ3BmZ3cxVjN3MnZEVyIsImNyZWF0ZWRBdCI6IjIwMjUtMTAtMjZUMTY6NDE6MTQuNTU2WiIsInVwZGF0ZWRBdCI6IjIwMjUtMTAtMjZUMTY6NDE6MTQuNTU2WiIsImlwQWRkcmVzcyI6IiIsInVzZXJBZ2VudCI6IiIsInVzZXJJZCI6Im85MWtMZkN2bzhWNEpkdFZDbDhzRVVpd0hYN2t0WUZMIiwiaWQiOiJJY2lVNmpnN0w3cFF1eUwxQmlOb3BLUVdFYlRRNWZRMCJ9LCJ1c2VyIjp7Im5hbWUiOiJBeWVzaGEgQXNoZmFxIiwiZW1haWwiOiJheWVzaGFhc2hmYXE5MjVAZ21haWwuY29tIiwiZW1haWxWZXJpZmllZCI6dHJ1ZSwiaW1hZ2UiOm51bGwsImNyZWF0ZWRBdCI6IjIwMjUtMTAtMjRUMjA6MDg6MzEuMjQ3WiIsInVwZGF0ZWRBdCI6IjIwMjUtMTAtMjRUMjA6MDk6MDEuNzI5WiIsImlkIjoibzkxa0xmQ3ZvOFY0SmR0VkNsOHNFVWl3SFg3a3RZRkwifX0sImV4cGlyZXNBdCI6MTc2MTQ5NzE3NDY1Mywic2lnbmF0dXJlIjoiUWZWZmpnVEMtZ0tZVnFvZ0c5NzNaT1cxaTJGWnlZWWNCZlFZM2l4T0o3byJ9",
        "__Secure-better-auth.session_token": "3Nays3AMT1t2B5GjY6HCpfgw1V3w2vDW.QRWiNVIqtZ7pm2b2ejt616seZP7fm%2B00LLEIe2P2TLY%3D",
        "_fbp": "fb.1.1761159174437.716440727532027868",
        "_gcl_au": "1.1.385005791.1761159176",
        "intercom-device-id-esc25l7u": "aa1ac6d7-b4b6-4745-9ade-62f9e0ab4008",
        "intercom-session-esc25l7u": "Q3hOZjZSRnFiamRuSlFxZGJyNWdwbFBxeWI3RWY2ZnFPb1cvQWJ2M2hTSnU3Yy9PeG9vQ3pOUUF2TFZSa1ZMaTFHWGp1UHFYWHc0b2dDMzZwWnVpelpoN2lBUmpwdlRudlZ0QS8vV1BpL009LS1HWWE1cWJHWFFodXpxdUdnRWYxTVlRPT0=--60cadbf1668eb647a7e1607ecee40508eb53f57c"
    }

    print("🧪 Testing with your provided cookies...")
    formatted = format_cookies_for_stealthwriter(your_cookies)

    print("\n📋 Formatted cookies ready for use:")
    print(json.dumps(formatted, indent=2))

    # Uncomment to run interactive setup
    # setup_cookies_from_browser()
