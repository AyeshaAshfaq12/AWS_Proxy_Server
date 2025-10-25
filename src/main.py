from fastapi import FastAPI
from api.proxy import router

app = FastAPI()
app.include_router(router)
