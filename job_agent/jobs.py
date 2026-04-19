import asyncio
import uuid
from typing import Any
from fastapi import APIRouter

router = APIRouter()

_store: dict[str, dict[str, Any]] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _store[job_id] = {"status": "pending", "progress": 0, "result": None, "error": None}
    return job_id


def update_job(job_id: str, **kwargs) -> None:
    if job_id in _store:
        _store[job_id].update(kwargs)


def get_job(job_id: str) -> dict | None:
    return _store.get(job_id)


async def run_background(job_id: str, coro):
    update_job(job_id, status="running")
    try:
        result = await coro
        update_job(job_id, status="completed", progress=100, result=result)
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))


@router.get("/{job_id}/status")
async def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}
