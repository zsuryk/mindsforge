from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.clips import router as clips_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.memory import router as memory_router
from app.core.config import get_settings
from app.db.base import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MindsForge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/media",
    StaticFiles(directory=settings.MEDIA_DIR, check_dir=False),
    name="media",
)

app.include_router(health_router, prefix=settings.API_V1_PREFIX, tags=["health"])
app.include_router(jobs_router, prefix=f"{settings.API_V1_PREFIX}/jobs", tags=["jobs"])
app.include_router(clips_router, prefix=settings.API_V1_PREFIX, tags=["clips"])
app.include_router(memory_router, prefix=settings.API_V1_PREFIX, tags=["agent"])