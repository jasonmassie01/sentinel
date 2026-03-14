from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import get_db

router = APIRouter(tags=["accounts"])


class AccountCreate(BaseModel):
    name: str
    type: str  # brokerage, crypto, checking, credit_card
    institution: str


class AccountResponse(BaseModel):
    id: int
    name: str
    type: str
    institution: str
    last_import_date: Optional[str] = None


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name, type, institution, last_import_date FROM accounts").fetchall()
    return [dict(row) for row in rows]


@router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(account: AccountCreate):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO accounts (name, type, institution) VALUES (?, ?, ?)",
            (account.name, account.type, account.institution),
        )
        account_id = cursor.lastrowid
        row = conn.execute(
            "SELECT id, name, type, institution, last_import_date FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
    return dict(row)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
def get_account(account_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, type, institution, last_import_date FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    return dict(row)
