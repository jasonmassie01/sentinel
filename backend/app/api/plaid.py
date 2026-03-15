from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services import plaid_service

router = APIRouter(tags=["plaid"])


class PublicTokenExchange(BaseModel):
    public_token: str
    institution_name: str = ""


@router.get("/plaid/status")
def plaid_status():
    """Check if Plaid is configured."""
    return {
        "configured": plaid_service.is_configured(),
        "linked_items": plaid_service.get_linked_items() if plaid_service.is_configured() else [],
    }


@router.post("/plaid/link-token")
def create_link_token():
    """Create a Plaid Link token for the frontend to open Plaid Link."""
    if not plaid_service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Plaid not configured. Set SENTINEL_PLAID_CLIENT_ID and SENTINEL_PLAID_SECRET environment variables.",
        )
    try:
        return plaid_service.create_link_token()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plaid/exchange-token")
def exchange_token(data: PublicTokenExchange):
    """Exchange public token from Plaid Link and create accounts."""
    if not plaid_service.is_configured():
        raise HTTPException(status_code=400, detail="Plaid not configured")
    try:
        return plaid_service.exchange_public_token(data.public_token, data.institution_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plaid/sync")
def sync_all(item_id: Optional[str] = None):
    """Sync transactions, holdings, and balances from all linked accounts."""
    if not plaid_service.is_configured():
        raise HTTPException(status_code=400, detail="Plaid not configured")

    results = {}
    try:
        results["transactions"] = plaid_service.sync_transactions(item_id)
    except Exception as e:
        results["transactions"] = {"error": str(e)}

    try:
        results["holdings"] = plaid_service.sync_holdings(item_id)
    except Exception as e:
        results["holdings"] = {"error": str(e)}

    try:
        results["balances"] = plaid_service.sync_balances(item_id)
    except Exception as e:
        results["balances"] = {"error": str(e)}

    return results


@router.post("/plaid/sync/transactions")
def sync_transactions(item_id: Optional[str] = None):
    """Sync only transactions."""
    try:
        return plaid_service.sync_transactions(item_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plaid/sync/holdings")
def sync_holdings(item_id: Optional[str] = None):
    """Sync only investment holdings."""
    try:
        return plaid_service.sync_holdings(item_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plaid/sync/balances")
def sync_balances(item_id: Optional[str] = None):
    """Sync only account balances."""
    try:
        return plaid_service.sync_balances(item_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plaid/items")
def list_items():
    """List all linked Plaid items."""
    return plaid_service.get_linked_items()


@router.delete("/plaid/items/{item_id}")
def remove_item(item_id: str):
    """Unlink a Plaid item."""
    plaid_service.remove_item(item_id)
    return {"status": "removed"}
