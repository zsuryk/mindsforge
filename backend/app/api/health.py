import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter

from app.services import minds

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    minds_status = await asyncio.to_thread(minds.check_connection)
    return {
        "status": "ok",
        "service": "mindsforge-backend",
        "minds": minds_status,
        "timestamp": datetime.now(UTC).isoformat(),
    }