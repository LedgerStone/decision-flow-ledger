"""
DecisionLedger SaaS — Approval endpoints
"""

from fastapi import APIRouter, Depends, HTTPException

from app.auth.api_key import verify_api_key
from app.database import tenant_connection
from app.schemas.schemas import ApprovalCreate
from app.services import approval_service

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


@router.post("/")
async def submit_approval(req: ApprovalCreate, auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        result = await approval_service.submit_approval(conn, auth["tenant_id"], req.model_dump())
    if "error" in result:
        raise HTTPException(status_code=result["status_code"], detail=result["error"])
    return result
