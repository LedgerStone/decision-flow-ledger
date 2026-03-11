"""
DecisionLedger SaaS — Decision endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.api_key import verify_api_key
from app.database import tenant_connection
from app.schemas.schemas import DecisionCreate, DecisionExecute, DecisionCancel
from app.services import decision_service

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.post("/")
async def create_decision(req: DecisionCreate, auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        result = await decision_service.create_decision(conn, auth["tenant_id"], req.model_dump())
    return result


@router.get("/")
async def list_decisions(
    status: str | None = Query(None),
    decision_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    auth: dict = Depends(verify_api_key),
):
    async with tenant_connection(auth["tenant_id"]) as conn:
        return await decision_service.list_decisions(
            conn, auth["tenant_id"], status, decision_type, page, per_page
        )


@router.get("/{decision_id}")
async def get_decision(decision_id: str, auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        result = await decision_service.get_decision(conn, auth["tenant_id"], decision_id)
    if not result:
        raise HTTPException(status_code=404, detail="Decision not found")
    return result


@router.post("/{decision_id}/execute")
async def execute_decision(decision_id: str, req: DecisionExecute, auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        result = await decision_service.execute_decision(conn, auth["tenant_id"], decision_id, req.executor)
    if "error" in result:
        raise HTTPException(status_code=result["status_code"], detail=result["error"])
    return result


@router.post("/{decision_id}/cancel")
async def cancel_decision(decision_id: str, req: DecisionCancel, auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        result = await decision_service.cancel_decision(
            conn, auth["tenant_id"], decision_id, req.cancelled_by, req.reason
        )
    if "error" in result:
        raise HTTPException(status_code=result["status_code"], detail=result["error"])
    return result
