from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from .config import Config
from .auth import require_api_key, require_admin_key
from .proxy import ProxyClient

app = FastAPI(title="StealthWriter Single-Session Proxy")

# global proxy client (set at startup)
proxy_client: Optional[ProxyClient] = None

@app.on_event("startup")
async def startup_event():
    global proxy_client
    cookie_string = Config.SESSION_COOKIE_STRING
    if not cookie_string:
        # If no cookie is present at startup we still start but respond with clear error
        proxy_client = None
        app.state.startup_ok = False
    else:
        proxy_client = ProxyClient(cookie_string)
        app.state.startup_ok = True

@app.get("/health")
async def health():
    return {"ok": True, "session_loaded": getattr(app.state, "startup_ok", False)}

@app.post("/admin/set_cookies")
async def set_cookies(payload: dict, x_admin_key: str = Depends(require_admin_key)):
    """
    Admin-only endpoint to update session cookies.
    POST JSON body: {"cookie_string": "a=1; b=2"}
    """
    cookie_string = payload.get("cookie_string")
    if not cookie_string:
        raise HTTPException(status_code=400, detail="cookie_string is required")
    global proxy_client
    if proxy_client is None:
        proxy_client = ProxyClient(cookie_string)
    else:
        proxy_client.set_cookies_from_string(cookie_string)
    # You should also persist the cookie_string to Secrets Manager / SSM here
    return {"ok": True}

# wildcard proxy route. All client requests must include x-api-key header
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def catch_all(full_path: str, request: Request, _auth=Depends(require_api_key)):
    global proxy_client
    if proxy_client is None:
        return JSONResponse({"error": "No session cookie configured on server"}, status_code=503)
    return await proxy_client.proxy_request(request, full_path)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, log_level="info")
