from fastapi import APIRouter, HTTPException

from tradingagents.api.reports import get_report, list_reports
from tradingagents.api.schemas import ReportDetail, ReportSummary

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("", response_model=list[ReportSummary])
def reports():
    return [ReportSummary(**report) for report in list_reports()]


@router.get("/{report_id}", response_model=ReportDetail)
def report_detail(report_id: str):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="report not found")
    return ReportDetail(**report)
