"""API schemas."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    local_only: bool = True


class DefaultsResponse(BaseModel):
    paths: dict[str, str]
    env: dict[str, bool]
    providers: list[str]
    message: str


class DashboardResponse(BaseModel):
    ledger_events: int
    decisions: int
    codex_analyses: int
    fiscal_review_rows_current_year: int
    current_year: int
    fiscal_error: Optional[str] = None


class CodexBundleRequest(BaseModel):
    ticker: str
    trade_date: str = Field(alias="date")
    lookback_days: int = 30
    indicator_lookback_days: int = 10
    include_fundamentals: bool = True


class CodexBundleResponse(BaseModel):
    bundle_id: str
    bundle_dir: str
    bundle_json_path: str
    prompt_path: str
    prompt_hash: str
    prompt: str


class CodexImportRequest(BaseModel):
    bundle_id: str
    response_text: str


class CodexImportResponse(BaseModel):
    analysis_id: str
    analysis_dir: str
    response_path: str
    report_path: str
    bundle_hash: str
    response_hash: str
    decision_link_id: int
    rating: str


class LedgerImportResponse(BaseModel):
    batch_id: int
    row_count: int
    inserted_count: int
    skipped_count: int
    source_hash: str


class LedgerPreviewResponse(BaseModel):
    events: list[dict[str, Any]]
    errors: list[str]


class FiscalReportResponse(BaseModel):
    jurisdiction: str
    year: int
    rows: list[dict[str, Any]]
    totals_by_treatment: dict[str, dict[str, str]]
    inventory: list[dict[str, Any]]
    review_notes: list[str]


class MarketWatchlistUpdateRequest(BaseModel):
    symbols: list[str]


class MarketWatchlistItem(BaseModel):
    symbol: str
    name: Optional[str] = None


class MarketWatchlistResponse(BaseModel):
    id: str
    label: str
    symbols: list[str]
    items: list[MarketWatchlistItem]


class MarketWatchlistsResponse(BaseModel):
    watchlists: list[MarketWatchlistResponse]


class MarketQuoteResponse(BaseModel):
    symbol: str
    name: Optional[str] = None
    market: str
    currency: str
    price: Optional[float] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    as_of: Optional[str] = None
    source: str
    status: str
    message: Optional[str] = None


class MarketMoversResponse(BaseModel):
    market: str
    generated_at: str
    source: str
    quotes: list[MarketQuoteResponse]
    top_gainers: list[MarketQuoteResponse]
    top_losers: list[MarketQuoteResponse]


class MarketTickerDetailResponse(BaseModel):
    symbol: str
    quote: MarketQuoteResponse
    history: list[dict[str, Any]]
    ledger: dict[str, Any]
    decisions: list[dict[str, Any]]


class AnalysisRequest(BaseModel):
    ticker: str
    date: str
    analysts: list[str] = Field(default_factory=lambda: ["market", "news", "fundamentals"])
    llm_provider: Optional[str] = None
    deep_think_llm: Optional[str] = None
    quick_think_llm: Optional[str] = None
    checkpoint: bool = False


class AnalysisCapabilityResponse(BaseModel):
    normal_available: bool
    selected_provider: str
    missing_env: list[str]
    message: str
    recommended_mode: str = "codex-assisted"


class AnalysisJobResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed"]
    ticker: str
    date: str
    rating: Optional[str] = None
    report_path: Optional[str] = None
    error: Optional[str] = None


class ReportSummary(BaseModel):
    report_id: str
    title: str
    path: str
    modified_at: str
    source: str


class ReportDetail(ReportSummary):
    content: str
