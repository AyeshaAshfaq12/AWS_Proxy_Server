from fastapi import APIRouter, Request, Depends, HTTPException
from httpx import AsyncClient, RequestError
from auth.session import get_authenticated_client
from utils.helpers import filter_headers
import os

router = APIRouter()

@router.post("/proxy/{path:path}")
async def proxy_request(path: str, request: Request, client: AsyncClient = Depends(get_authenticated_client)):
    target_url = os.getenv("TARGET_URL").rstrip("/") + f"/{path}"
    headers = filter_headers(request.headers)
    data = await request.json() if request.method in ["POST", "PUT"] else None

    try:
        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            json=data,
            params=request.query_params
        )
        # Handle upstream errors
        if response.status_code >= 400:
            return {
                "error": "Proxy Error: Upstream service unavailable",
                "status_code": response.status_code,
                "details": response.text
            }
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "data": response.json()
        }
    except RequestError as e:
        raise HTTPException(status_code=502, detail=f"Proxy Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")