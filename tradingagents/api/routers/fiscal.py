from fastapi import APIRouter, Query
from fastapi.responses import Response

from tradingagents.api.deps import get_ledger_store
from tradingagents.api.schemas import FiscalReportResponse
from tradingagents.api.utils import tax_report_export_response, tax_report_to_response
from tradingagents.ledger.tax.pt import build_pt_tax_report

router = APIRouter(prefix="/api/fiscal", tags=["fiscal"])


@router.get("/pt/{year}", response_model=FiscalReportResponse)
def portugal_report(year: int):
    report = build_pt_tax_report(get_ledger_store().list_events(), year=year)
    return FiscalReportResponse(**tax_report_to_response(report, year))


@router.get("/pt/{year}/export")
def portugal_export(
    year: int,
    format: str = Query("csv", pattern="^(csv|json)$"),
) -> Response:
    report = build_pt_tax_report(get_ledger_store().list_events(), year=year)
    return tax_report_export_response(report, format, year)
