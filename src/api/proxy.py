from fastapi import APIRouter, Request, Depends, Response, HTTPException
from httpx import AsyncClient, RequestError
from auth.session import get_authenticated_client
from utils.helpers import filter_headers
import os

router = APIRouter()

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def browser_proxy(path: str, request: Request, client: AsyncClient = Depends(get_authenticated_client)):
    # Build the target URL
    target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
    if path == "":
        target_url = os.getenv("TARGET_URL")  # root path

    # Prepare headers and body
    headers = filter_headers(dict(request.headers))
    body = await request.body()

    try:
        # Forward the request to the target site
        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )

        # Stream the response back to the browser
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() not in ["content-encoding", "transfer-encoding", "connection"]}
        )
    except RequestError as e:
        raise HTTPException(status_code=502, detail=f"Proxy Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy Error: {str(e)}")