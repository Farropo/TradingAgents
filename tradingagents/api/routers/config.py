from fastapi import APIRouter

from tradingagents.api.deps import env_status, get_config
from tradingagents.api.schemas import DefaultsResponse
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/defaults", response_model=DefaultsResponse)
def defaults():
    cfg = get_config()
    return DefaultsResponse(
        paths={
            "results_dir": cfg["results_dir"],
            "data_cache_dir": cfg["data_cache_dir"],
            "memory_log_path": cfg["memory_log_path"],
            "ledger_db_path": cfg["ledger_db_path"],
            "codex_assisted_dir": cfg["codex_assisted_dir"],
            "market_watchlists_path": cfg["market_watchlists_path"],
        },
        env=env_status(),
        providers=sorted(MODEL_OPTIONS.keys()),
        message="Local-only app. API keys are read by the backend environment and never returned.",
    )
