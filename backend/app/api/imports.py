from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.import_service import import_csv

router = APIRouter(tags=["imports"])


@router.post("/accounts/{account_id}/import")
async def upload_csv(account_id: int, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    result = import_csv(account_id, text)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Import failed"))

    return result
