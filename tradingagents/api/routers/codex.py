from pathlib import Path

from fastapi import APIRouter

from tradingagents.api.schemas import (
    CodexBundleRequest,
    CodexBundleResponse,
    CodexImportRequest,
    CodexImportResponse,
)
from tradingagents.api.utils import find_bundle
from tradingagents.codex_assisted import (
    import_codex_analysis,
    list_codex_analyses,
    prepare_codex_analysis,
)

router = APIRouter(prefix="/api/codex", tags=["codex"])


@router.post("/bundles", response_model=CodexBundleResponse)
def create_bundle(request: CodexBundleRequest):
    prepared = prepare_codex_analysis(
        ticker=request.ticker,
        trade_date=request.trade_date,
        lookback_days=request.lookback_days,
        indicator_lookback_days=request.indicator_lookback_days,
        include_fundamentals=request.include_fundamentals,
    )
    return CodexBundleResponse(
        bundle_id=prepared.bundle_id,
        bundle_dir=str(prepared.bundle_dir),
        bundle_json_path=str(prepared.bundle_json_path),
        prompt_path=str(prepared.prompt_path),
        prompt_hash=prepared.prompt_hash,
        prompt=prepared.prompt_path.read_text(encoding="utf-8"),
    )


@router.get("/bundles/{bundle_id}/prompt")
def bundle_prompt(bundle_id: str):
    bundle_json = find_bundle(bundle_id)
    prompt_path = bundle_json.parent / "prompt.md"
    return {
        "bundle_id": bundle_id,
        "bundle_json_path": str(bundle_json),
        "prompt_path": str(prompt_path),
        "prompt": prompt_path.read_text(encoding="utf-8"),
    }


@router.post("/import", response_model=CodexImportResponse)
def import_response(request: CodexImportRequest):
    bundle_json = find_bundle(request.bundle_id)
    response_path = bundle_json.parent / "codex_response.md"
    response_path.write_text(request.response_text, encoding="utf-8")
    summary = import_codex_analysis(response_path, bundle_file=bundle_json)
    return CodexImportResponse(
        analysis_id=summary.analysis_id,
        analysis_dir=str(summary.analysis_dir),
        response_path=str(summary.response_path),
        report_path=str(summary.report_path),
        bundle_hash=summary.bundle_hash,
        response_hash=summary.response_hash,
        decision_link_id=summary.decision_link_id,
        rating=summary.rating,
    )


@router.get("/analyses")
def analyses():
    return list_codex_analyses()
