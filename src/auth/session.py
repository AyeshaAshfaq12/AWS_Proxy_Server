import httpx
import os
import asyncio
from aws.integration import get_target_credentials

_master_client = None
_master_client_lock = asyncio.Lock()

async def get_authenticated_client():
    global _master_client
    async with _master_client_lock:
        if _master_client is None:
            credentials = get_target_credentials()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "identity",  # Request uncompressed for easier debugging
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            client = httpx.AsyncClient(headers=headers, follow_redirects=True)
            login_url = os.getenv("TARGET_URL").rstrip("/") + "/auth/sign-in"
            # Try both form and JSON payloads if unsure
            resp = await client.post(login_url, data={
                "email": credentials["username"],
                "password": credentials["password"]
            })
            print("Status code:", resp.status_code)
            print("Headers:", resp.headers)
            print("Raw content:", resp.content[:500])  # Print first 500 bytes for debugging

            if resp.status_code != 200 or "Just a moment" in resp.text or "Enable JavaScript" in resp.text:
                # Try JSON payload if form fails
                resp_json = await client.post(login_url, json={
                    "email": credentials["username"],
                    "password": credentials["password"]
                })
                print("JSON Status code:", resp_json.status_code)
                print("JSON Headers:", resp_json.headers)
                print("JSON Raw content:", resp_json.content[:500])
                if resp_json.status_code != 200 or "Just a moment" in resp_json.text or "Enable JavaScript" in resp_json.text:
                    raise Exception(f"Failed to authenticate with target site: {resp_json.text}")
                _master_client = client
            else:
                _master_client = client
        return _master_client
