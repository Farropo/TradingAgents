from fastapi import APIRouter, HTTPException

from tradingagents.api.analysis_jobs import AnalysisConfigurationError, analysis_capability, manager
from tradingagents.api.schemas import AnalysisCapabilityResponse, AnalysisJobResponse, AnalysisRequest

router = APIRouter(prefix="/api/analyses", tags=["analysis"])


@router.post("", response_model=AnalysisJobResponse)
def start_analysis(request: AnalysisRequest):
    try:
        job = manager.start(request)
    except AnalysisConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AnalysisJobResponse(**job.to_dict())


@router.get("/capability", response_model=AnalysisCapabilityResponse)
def get_analysis_capability(provider: str | None = None):
    return AnalysisCapabilityResponse(**analysis_capability(provider))


@router.get("", response_model=list[AnalysisJobResponse])
def list_analyses():
    return [AnalysisJobResponse(**job.to_dict()) for job in manager.list()]


@router.get("/{run_id}", response_model=AnalysisJobResponse)
def get_analysis(run_id: str):
    job = manager.get(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return AnalysisJobResponse(**job.to_dict())


@router.get("/{run_id}/report")
def get_analysis_report(run_id: str):
    job = manager.get(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="analysis run not found")
    if not job.report_path:
        raise HTTPException(status_code=404, detail="report not available")
    from pathlib import Path

    path = Path(job.report_path)
    return {
        "run_id": run_id,
        "report_path": str(path),
        "content": path.read_text(encoding="utf-8"),
    }
