"""
DecisionLedger SaaS — Blockchain endpoints
"""

from fastapi import APIRouter, Depends, HTTPException

from app.auth.api_key import verify_api_key
from app.blockchain.manager import blockchain_manager

router = APIRouter(prefix="/api/v1/blockchain", tags=["blockchain"])


@router.get("/")
async def get_chain(auth: dict = Depends(verify_api_key)):
    chain = blockchain_manager.get_chain(auth["tenant_id"])
    data = chain.get_full_chain()
    return {
        "chain": data,
        "total_blocks": len(data),
        "total_transactions": sum(len(b["transactions"]) for b in data),
    }


@router.get("/stats")
async def get_stats(auth: dict = Depends(verify_api_key)):
    chain = blockchain_manager.get_chain(auth["tenant_id"])
    return chain.stats()


@router.get("/verify")
async def verify_chain(auth: dict = Depends(verify_api_key)):
    chain = blockchain_manager.get_chain(auth["tenant_id"])
    return chain.verify_chain()


@router.get("/block/{index}")
async def get_block(index: int, auth: dict = Depends(verify_api_key)):
    chain = blockchain_manager.get_chain(auth["tenant_id"])
    block = chain.get_block(index)
    if block is None:
        raise HTTPException(status_code=404, detail=f"Block {index} not found")
    return block


@router.get("/tx/{tx_hash}")
async def get_transaction(tx_hash: str, auth: dict = Depends(verify_api_key)):
    chain = blockchain_manager.get_chain(auth["tenant_id"])
    result = chain.get_transaction_by_hash(tx_hash)
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.get("/decision/{decision_id}")
async def get_decision_trail(decision_id: str, auth: dict = Depends(verify_api_key)):
    chain = blockchain_manager.get_chain(auth["tenant_id"])
    results = chain.get_transactions_for_decision(decision_id)
    return {
        "decision_id": decision_id,
        "events": results,
        "total_events": len(results),
    }
