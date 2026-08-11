from fastapi import APIRouter, HTTPException, status

from app.schemas.memory import MemoryOut, MemoryUpdateIn, MemoryUpdateOut
from app.services import minds

router = APIRouter()


def _raise_minds_error(exc: minds.MindsError) -> None:
    if isinstance(exc, minds.MindsConfigError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/agent/memory", response_model=MemoryOut)
def get_memory() -> MemoryOut:
    try:
        agent_id = minds._agent_id()
        memory = minds.fetch_memory(agent_id)
    except minds.MindsError as exc:
        _raise_minds_error(exc)
    return MemoryOut(agent_id=agent_id, memory=memory)


@router.post("/agent/memory/update", response_model=MemoryUpdateOut)
def update_memory(payload: MemoryUpdateIn) -> MemoryUpdateOut:
    try:
        agent_id = minds._agent_id()
        success = minds.update_memory(agent_id, payload.key, payload.value)
    except minds.MindsError as exc:
        _raise_minds_error(exc)
    return MemoryUpdateOut(success=success)
