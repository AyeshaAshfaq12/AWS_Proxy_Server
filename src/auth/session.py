from httpx import AsyncClient
from aws.integration import get_target_credentials
import os
import asyncio

_master_client = None
_master_client_lock = asyncio.Lock()

async def get_authenticated_client():
    global _master_client
    async with _master_client_lock:
        if _master_client is None:
            credentials = get_target_credentials()
            client = AsyncClient()
            # Login to the target site
            login_url = os.getenv("TARGET_URL").rstrip("/") + "/login"
            resp = await client.post(login_url, data={
                "username": credentials["username"],
                "password": credentials["password"]
            })
            if resp.status_code != 200:
                raise Exception(f"Failed to authenticate with target site: {resp.text}")
            _master_client = client
        return _master_client