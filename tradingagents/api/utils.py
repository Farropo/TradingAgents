"""API utility functions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import csv
import io
import json
import shutil
import uuid

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

from tradingagents.api.deps import get_config, get_upload_dir
from tradingagents.ledger.store import LedgerStore
from tradingagents.ledger.tax.pt import TaxReport


def write_upload(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "upload.csv").suffix or ".csv"
    safe_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex}{suffix}"
    path = get_upload_dir() / safe_name
    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path


def find_bundle(bundle_id: str) -> Path:
    root = Path(get_config()["codex_assisted_dir"]).expanduser()
    matches = list(root.glob(f"*/*/{bundle_id}/bundle.json"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"Bundle not found: {bundle_id}")
    return matches[0]


def tax_report_to_response(report: TaxReport, year: int) -> dict:
    return {
        "jurisdiction": report.jurisdiction,
        "year": year,
        "rows": report.as_dicts(),
        "totals_by_treatment": report.totals_by_treatment(),
        "inventory": report.inventory,
        "review_notes": report.review_notes,
    }


def tax_report_export_response(report: TaxReport, fmt: str, year: int) -> Response:
    fmt = fmt.lower()
    if fmt == "json":
        content = json.dumps(tax_report_to_response(report, year), indent=2, ensure_ascii=False)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="irs_pt_{year}.json"'},
        )
    if fmt == "csv":
        rows = report.as_dicts()
        fieldnames = list(rows[0].keys()) if rows else [
            "tax_year",
            "appendix",
            "category",
            "asset_type",
            "symbol",
            "isin",
            "acquisition_date",
            "realization_date",
            "quantity",
            "proceeds_eur",
            "cost_basis_eur",
            "expenses_eur",
            "gain_eur",
            "holding_days",
            "tax_treatment",
            "broker",
            "account",
            "source_country",
            "requires_review",
            "review_reason",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="irs_pt_{year}.csv"'},
        )
    raise HTTPException(status_code=400, detail="format must be csv or json")


def serialize_event(event) -> dict:
    return event.to_record(include_raw=False)


def serialize_decision(decision: dict) -> dict:
    return dict(decision)


def ledger_summary(store: LedgerStore) -> tuple[int, int]:
    return len(store.list_events()), len(store.list_decisions())
