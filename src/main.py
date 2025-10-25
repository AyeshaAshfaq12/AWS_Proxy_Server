from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader
from aws.integration import get_api_key, get_target_credentials
import os
from dotenv import load_dotenv
from utils.helpers import structured_log

load_dotenv()
app = FastAPI()

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME)

async def validate_api_key(api_key: str = Depends(api_key_header)):
    secret_api_key = await get_api_key()
    if api_key != secret_api_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    # Example: Pre-fetch credentials and log startup
    credentials = get_target_credentials()
    structured_log("Proxy server startup", username=credentials['username'])
    # You can initialize your master session here if needed

@app.on_event("shutdown")
async def shutdown_event():
    # Example: Log shutdown
    structured_log("Proxy server shutdown")