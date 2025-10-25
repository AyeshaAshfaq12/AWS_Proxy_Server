from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from fastapi import FastAPI
from api.proxy import router

app = FastAPI()
app.include_router(router)
