from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from tradingagents.api.deps import get_ledger_store
from tradingagents.api.schemas import LedgerImportResponse, LedgerPreviewResponse
from tradingagents.api.utils import serialize_decision, serialize_event, write_upload
from tradingagents.ledger.importers.csv import CsvImportError, import_csv_to_store, preview_csv

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@router.post("/imports/preview", response_model=LedgerPreviewResponse)
def preview_import(
    file: UploadFile = File(...),
    profile: str = Form("generic"),
):
    path = write_upload(file)
    preview = preview_csv(path, profile)
    return LedgerPreviewResponse(
        events=[serialize_event(event) for event in preview.events],
        errors=preview.errors,
    )


@router.post("/imports", response_model=LedgerImportResponse)
def import_ledger_csv(
    file: UploadFile = File(...),
    profile: str = Form("generic"),
):
    path = write_upload(file)
    try:
        summary = import_csv_to_store(path, get_ledger_store(), profile)
    except CsvImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LedgerImportResponse(
        batch_id=summary.batch_id,
        row_count=summary.row_count,
        inserted_count=summary.inserted_count,
        skipped_count=summary.skipped_count,
        source_hash=summary.source_hash,
    )


@router.get("/events")
def events(year: int | None = None, broker: str | None = None, account: str | None = None):
    return [
        serialize_event(event)
        for event in get_ledger_store().list_events(year=year, broker=broker, account=account)
    ]


@router.get("/decisions")
def decisions():
    return [serialize_decision(decision) for decision in get_ledger_store().list_decisions()]
