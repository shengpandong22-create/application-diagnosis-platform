from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app_diagnosis.adapters.persistence import Database


class HealthResponse(BaseModel):
    status: Literal["ok", "ready"]


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    database: Database = request.app.state.database
    if not await database.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database is not ready",
        )
    return HealthResponse(status="ready")
