from fastapi import APIRouter, HTTPException, status

from app.schemas.memory import MemoryOut, MemoryUpdateIn, MemoryUpdateOut
from app.services import llm

router = APIRouter()


def _raise_memory_error(exc: llm.LLMError) -> None:
    if isinstance(exc, llm.LLMConfigError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/agent/memory", response_model=MemoryOut)
def get_memory() -> MemoryOut:
    try:
        memory = llm.fetch_memory()
    except llm.LLMError as exc:
        _raise_memory_error(exc)
    return MemoryOut(agent_id=llm.LOCAL_AGENT_ID, memory=memory)


@router.post("/agent/memory/update", response_model=MemoryUpdateOut)
def update_memory(payload: MemoryUpdateIn) -> MemoryUpdateOut:
    try:
        success = llm.update_memory(payload.key, payload.value)
    except llm.LLMError as exc:
        _raise_memory_error(exc)
    return MemoryUpdateOut(success=success)
