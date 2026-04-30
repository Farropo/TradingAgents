"""Background analysis jobs for the local API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import os
import threading
import traceback
import uuid
from typing import Any, Optional

from tradingagents.agents.utils.rating import parse_rating
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


_PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GOOGLE_API_KEY",),
    "xai": ("XAI_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "qwen": ("DASHSCOPE_API_KEY",),
    "glm": ("ZHIPU_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "azure": ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"),
}


class AnalysisConfigurationError(RuntimeError):
    """Raised when a normal automated analysis cannot be started locally."""


@dataclass
class AnalysisJob:
    run_id: str
    status: str
    ticker: str
    date: str
    created_at: str
    updated_at: str
    rating: Optional[str] = None
    report_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AnalysisJobManager:
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = threading.Lock()

    def start(self, request) -> AnalysisJob:
        capability = analysis_capability(request.llm_provider)
        if not capability["normal_available"]:
            raise AnalysisConfigurationError(capability["message"])

        run_id = uuid.uuid4().hex
        now = _now()
        job = AnalysisJob(
            run_id=run_id,
            status="queued",
            ticker=request.ticker.upper().strip(),
            date=request.date,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[run_id] = job
        self._executor.submit(self._run, run_id, request)
        return job

    def get(self, run_id: str) -> Optional[AnalysisJob]:
        with self._lock:
            return self._jobs.get(run_id)

    def list(self) -> list[AnalysisJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _run(self, run_id: str, request) -> None:
        self._update(run_id, status="running")
        try:
            cfg = DEFAULT_CONFIG.copy()
            if request.llm_provider:
                cfg["llm_provider"] = request.llm_provider.lower()
            if request.deep_think_llm:
                cfg["deep_think_llm"] = request.deep_think_llm
            if request.quick_think_llm:
                cfg["quick_think_llm"] = request.quick_think_llm
            cfg["checkpoint_enabled"] = request.checkpoint

            graph = TradingAgentsGraph(
                selected_analysts=request.analysts,
                debug=False,
                config=cfg,
            )
            final_state, rating = graph.propagate(request.ticker, request.date)
            report_path = _write_report(run_id, request.ticker, request.date, final_state, rating, cfg)
            self._update(run_id, status="completed", rating=rating, report_path=str(report_path))
        except Exception as exc:
            message = _clean_error(exc)
            self._update(
                run_id,
                status="failed",
                error=message,
            )

    def _update(self, run_id: str, **changes) -> None:
        with self._lock:
            job = self._jobs[run_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = _now()


def _write_report(
    run_id: str,
    ticker: str,
    trade_date: str,
    final_state: dict[str, Any],
    rating: str,
    config: dict[str, Any],
) -> Path:
    directory = Path(config["results_dir"]) / ticker.upper() / trade_date / "api_runs" / run_id
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "complete_report.md"
    sections = [
        f"# TradingAgents API Analysis: {ticker.upper()}",
        "",
        f"- run_id: {run_id}",
        f"- trade_date: {trade_date}",
        f"- rating: {rating or parse_rating(final_state.get('final_trade_decision', ''))}",
        f"- generated_at: {_now()}",
    ]
    for title, key in (
        ("Market Report", "market_report"),
        ("Sentiment Report", "sentiment_report"),
        ("News Report", "news_report"),
        ("Fundamentals Report", "fundamentals_report"),
        ("Investment Plan", "investment_plan"),
        ("Trader Proposal", "trader_investment_plan"),
        ("Final Portfolio Decision", "final_trade_decision"),
    ):
        value = final_state.get(key)
        if value:
            sections.extend(["", f"## {title}", str(value)])
    report.write_text("\n".join(sections), encoding="utf-8")
    return report


def analysis_capability(provider_override: Optional[str] = None) -> dict[str, Any]:
    provider = (provider_override or DEFAULT_CONFIG.get("llm_provider") or "openai").lower()
    if provider == "ollama":
        return {
            "normal_available": True,
            "selected_provider": provider,
            "missing_env": [],
            "message": "Normal analysis is configured for local Ollama. Codex-assisted remains available without LLM API calls.",
        }

    required = _PROVIDER_ENV.get(provider)
    if not required:
        return {
            "normal_available": False,
            "selected_provider": provider,
            "missing_env": [],
            "message": f"Unsupported provider '{provider}'. Use Codex-assisted mode or configure a supported backend provider.",
        }

    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        readable = ", ".join(missing)
        return {
            "normal_available": False,
            "selected_provider": provider,
            "missing_env": missing,
            "message": (
                "Normal automated analysis is disabled because the backend is missing "
                f"{readable}. For the current no-cost workflow, use Codex Assisted: "
                "generate the bundle locally, paste it into this Codex thread, then import the response."
            ),
        }

    return {
        "normal_available": True,
        "selected_provider": provider,
        "missing_env": [],
        "message": f"Normal automated analysis can run with provider '{provider}'. API keys remain server-side.",
    }


def _clean_error(exc: Exception) -> str:
    text = str(exc).strip()
    if "api_key" in text.lower() or "environment variable" in text.lower():
        return (
            "Normal automated analysis failed because the selected LLM provider is not configured in the backend. "
            "Use Codex Assisted for the no-API workflow, or set the provider API key as an environment variable before starting the backend."
        )
    if not text:
        text = exc.__class__.__name__
    detail = traceback.format_exc(limit=1).strip().splitlines()[-1]
    return text if text in detail else f"{text} ({detail})"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


manager = AnalysisJobManager()
