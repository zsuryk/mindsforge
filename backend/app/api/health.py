import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter

from app.services import llm

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    llm_status = await asyncio.to_thread(llm.check_connection)
    return {
        "status": "ok",
        "service": "mindsforge-backend",
        "llm": llm_status,
        "timestamp": datetime.now(UTC).isoformat(),
    }
