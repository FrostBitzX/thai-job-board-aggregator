from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.search import router
from backend.config import settings

app = FastAPI(title="Thai Job Board Aggregator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)