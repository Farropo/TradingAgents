from datetime import datetime

from fastapi import APIRouter

from tradingagents.api.deps import get_ledger_store
from tradingagents.api.schemas import DashboardResponse
from tradingagents.codex_assisted import list_codex_analyses
from tradingagents.ledger.tax.pt import build_pt_tax_report

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard():
    store = get_ledger_store()
    events = store.list_events()
    decisions = store.list_decisions()
    current_year = datetime.now().year
    fiscal_review_rows = 0
    fiscal_error = None
    try:
        report = build_pt_tax_report(events, year=current_year)
        fiscal_review_rows = sum(1 for row in report.rows if row.requires_review)
    except Exception as exc:
        fiscal_error = str(exc)
    return DashboardResponse(
        ledger_events=len(events),
        decisions=len(decisions),
        codex_analyses=len(list_codex_analyses()),
        fiscal_review_rows_current_year=fiscal_review_rows,
        current_year=current_year,
        fiscal_error=fiscal_error,
    )
