from fastapi import Header, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_401_UNAUTHORIZED
from .config import Config

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


def require_api_key(api_key_header_value: str = Security(api_key_header)):
    if not api_key_header_value or api_key_header_value != Config.API_KEY:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key")


def require_admin_key(x_admin_key: str = Header(..., alias="x-admin-key")):
    if x_admin_key != Config.ADMIN_API_KEY:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
