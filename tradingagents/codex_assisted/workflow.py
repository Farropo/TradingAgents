"""Local Codex-assisted analysis workflow.

This mode intentionally never instantiates an LLM client.  It gathers market
context, writes a prompt bundle for the user to paste into a Codex thread, and
imports the resulting answer back into local reports, memory, and ledger links.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Optional

from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.agents.utils.rating import parse_rating
from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.ledger.store import LedgerStore


BUNDLE_VERSION = 2
ANALYSIS_MODE = "codex-assisted"
WORKFLOW_MODE = "codex-assisted-full-role"
MODEL_HINT = "GPT-5.5 extra reasoning"
DEFAULT_INDICATORS = (
    "close_50_sma",
    "close_200_sma",
    "macd",
    "rsi",
    "atr",
)


@dataclass(frozen=True)
class PreparedBundle:
    bundle_id: str
    bundle_dir: Path
    bundle_json_path: Path
    prompt_path: Path
    prompt_hash: str


@dataclass(frozen=True)
class CodexImportSummary:
    analysis_id: str
    analysis_dir: Path
    response_path: Path
    report_path: Path
    bundle_hash: str
    response_hash: str
    decision_link_id: int
    rating: str


def prepare_codex_analysis(
    ticker: str,
    trade_date: str,
    config: Optional[dict[str, Any]] = None,
    output_dir: str | Path | None = None,
    lookback_days: int = 30,
    indicator_lookback_days: int = 10,
    include_fundamentals: bool = True,
    collectors: Optional[dict[str, Callable[..., str]]] = None,
) -> PreparedBundle:
    cfg = (config or DEFAULT_CONFIG).copy()
    set_config(cfg)
    ticker = ticker.upper().strip()
    trade_date = _validate_date(trade_date)
    generated_at = datetime.now(timezone.utc).isoformat()
    end_date = (datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=1)).date().isoformat()
    start_date = (
        datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=lookback_days)
    ).date().isoformat()

    collectors = collectors or _default_collectors()
    data_sources = _collect_data(
        ticker=ticker,
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
        indicator_lookback_days=indicator_lookback_days,
        include_fundamentals=include_fundamentals,
        collectors=collectors,
    )
    ledger_context = _ledger_context(ticker, cfg)
    memory_context = TradingMemoryLog(cfg).get_past_context(ticker)

    bundle_body = {
        "bundle_version": BUNDLE_VERSION,
        "analysis_mode": ANALYSIS_MODE,
        "workflow_mode": WORKFLOW_MODE,
        "model_hint": MODEL_HINT,
        "ticker": ticker,
        "trade_date": trade_date,
        "generated_at": generated_at,
        "data_window": {
            "start_date": start_date,
            "end_date": end_date,
            "lookback_days": lookback_days,
            "indicator_lookback_days": indicator_lookback_days,
        },
        "data_sources": data_sources,
        "ledger_context": ledger_context,
        "memory_context": memory_context,
    }
    prompt = _build_prompt(bundle_body)
    bundle_body["prompt_hash"] = sha256_text(prompt)
    bundle_body["bundle_hash"] = sha256_json(bundle_body)

    root = Path(output_dir or cfg.get("codex_assisted_dir") or _default_codex_dir()).expanduser()
    bundle_id = f"{ticker}_{trade_date}_{bundle_body['bundle_hash'][:12]}"
    bundle_dir = root / ticker / trade_date / bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    bundle_json_path = bundle_dir / "bundle.json"
    prompt_path = bundle_dir / "prompt.md"
    bundle_json_path.write_text(
        json.dumps(bundle_body, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    prompt_path.write_text(prompt, encoding="utf-8")

    return PreparedBundle(
        bundle_id=bundle_id,
        bundle_dir=bundle_dir,
        bundle_json_path=bundle_json_path,
        prompt_path=prompt_path,
        prompt_hash=bundle_body["prompt_hash"],
    )


def import_codex_analysis(
    response_file: str | Path,
    bundle_file: str | Path | None = None,
    config: Optional[dict[str, Any]] = None,
    output_dir: str | Path | None = None,
) -> CodexImportSummary:
    cfg = (config or DEFAULT_CONFIG).copy()
    response_path = Path(response_file).expanduser()
    response_text = response_path.read_text(encoding="utf-8")
    bundle = _load_bundle(bundle_file, response_path)

    ticker = bundle["ticker"]
    trade_date = bundle["trade_date"]
    rating = parse_rating(response_text)
    response_hash = sha256_text(response_text)
    bundle_hash = bundle.get("bundle_hash") or sha256_json(bundle)
    imported_at = datetime.now(timezone.utc).isoformat()

    root = Path(output_dir or cfg.get("codex_assisted_dir") or _default_codex_dir()).expanduser()
    analysis_id = f"{ticker}_{trade_date}_{response_hash[:12]}"
    analysis_dir = root / ticker / trade_date / analysis_id
    analysis_dir.mkdir(parents=True, exist_ok=True)

    saved_response_path = analysis_dir / "codex_response.md"
    report_path = analysis_dir / "complete_report.md"
    metadata_path = analysis_dir / "analysis_metadata.json"
    saved_response_path.write_text(response_text, encoding="utf-8")

    report_text = _build_imported_report(
        bundle=bundle,
        response_text=response_text,
        rating=rating,
        response_hash=response_hash,
        imported_at=imported_at,
    )
    report_path.write_text(report_text, encoding="utf-8")

    ledger = LedgerStore(cfg["ledger_db_path"])
    decision_link_id = ledger.record_decision(
        ticker=ticker,
        trade_date=trade_date,
        rating=rating,
        decision_text=response_text,
        report_path=report_path,
    )
    TradingMemoryLog(cfg).store_decision(
        ticker=ticker,
        trade_date=trade_date,
        final_trade_decision=response_text,
    )

    metadata = {
        "analysis_mode": ANALYSIS_MODE,
        "workflow_mode": bundle.get("workflow_mode", WORKFLOW_MODE),
        "model_hint": bundle.get("model_hint", MODEL_HINT),
        "analysis_id": analysis_id,
        "ticker": ticker,
        "trade_date": trade_date,
        "rating": rating,
        "imported_at": imported_at,
        "bundle_hash": bundle_hash,
        "prompt_hash": bundle.get("prompt_hash"),
        "response_hash": response_hash,
        "decision_link_id": decision_link_id,
        "source_response_file": str(response_path),
        "report_path": str(report_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return CodexImportSummary(
        analysis_id=analysis_id,
        analysis_dir=analysis_dir,
        response_path=saved_response_path,
        report_path=report_path,
        bundle_hash=bundle_hash,
        response_hash=response_hash,
        decision_link_id=decision_link_id,
        rating=rating,
    )


def list_codex_analyses(
    config: Optional[dict[str, Any]] = None,
    output_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    cfg = (config or DEFAULT_CONFIG).copy()
    root = Path(output_dir or cfg.get("codex_assisted_dir") or _default_codex_dir()).expanduser()
    if not root.exists():
        return []
    analyses: list[dict[str, Any]] = []
    for metadata_path in root.glob("*/*/*/analysis_metadata.json"):
        try:
            analyses.append(json.loads(metadata_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return sorted(analyses, key=lambda item: (item.get("trade_date", ""), item.get("ticker", "")), reverse=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _default_codex_dir() -> str:
    return str(Path.home() / ".tradingagents" / "codex_assisted")


def _validate_date(value: str) -> str:
    datetime.strptime(value, "%Y-%m-%d")
    return value


def _default_collectors() -> dict[str, Callable[..., str]]:
    from tradingagents.dataflows.y_finance import (
        get_YFin_data_online,
        get_balance_sheet,
        get_cashflow,
        get_fundamentals,
        get_income_statement,
    )
    from tradingagents.dataflows.yfinance_news import get_global_news_yfinance, get_news_yfinance

    return {
        "market_data": get_YFin_data_online,
        "indicator": _indicator_collector,
        "news": get_news_yfinance,
        "global_news": get_global_news_yfinance,
        "fundamentals": get_fundamentals,
        "balance_sheet": get_balance_sheet,
        "cashflow": get_cashflow,
        "income_statement": get_income_statement,
    }


def _indicator_collector(ticker: str, indicator: str, trade_date: str, lookback_days: int) -> str:
    from tradingagents.dataflows.y_finance import get_stock_stats_indicators_window

    return get_stock_stats_indicators_window(ticker, indicator, trade_date, lookback_days)


def _collect_data(
    ticker: str,
    trade_date: str,
    start_date: str,
    end_date: str,
    indicator_lookback_days: int,
    include_fundamentals: bool,
    collectors: dict[str, Callable[..., str]],
) -> dict[str, Any]:
    indicators = {
        indicator: _safe_collect(
            f"indicator:{indicator}",
            collectors["indicator"],
            ticker,
            indicator,
            trade_date,
            indicator_lookback_days,
        )
        for indicator in DEFAULT_INDICATORS
    }
    data = {
        "market_data": _safe_collect(
            "market_data", collectors["market_data"], ticker, start_date, end_date
        ),
        "technical_indicators": indicators,
        "news": _safe_collect("news", collectors["news"], ticker, start_date, end_date),
        "global_news": _safe_collect(
            "global_news", collectors["global_news"], trade_date, 7, 10
        ),
    }
    if include_fundamentals:
        data.update(
            {
                "fundamentals": _safe_collect(
                    "fundamentals", collectors["fundamentals"], ticker, trade_date
                ),
                "balance_sheet": _safe_collect(
                    "balance_sheet", collectors["balance_sheet"], ticker, "quarterly", trade_date
                ),
                "cashflow": _safe_collect(
                    "cashflow", collectors["cashflow"], ticker, "quarterly", trade_date
                ),
                "income_statement": _safe_collect(
                    "income_statement", collectors["income_statement"], ticker, "quarterly", trade_date
                ),
            }
        )
    return data


def _safe_collect(name: str, func: Callable[..., str], *args) -> str:
    try:
        return func(*args)
    except Exception as exc:
        return f"ERROR collecting {name}: {exc}"


def _ledger_context(ticker: str, cfg: dict[str, Any]) -> dict[str, Any]:
    ledger_db_path = cfg.get("ledger_db_path")
    if not ledger_db_path:
        return {"enabled": False, "events": [], "decisions": []}
    store = LedgerStore(ledger_db_path)
    events = [
        event.to_record(include_raw=False)
        for event in store.list_events()
        if event.symbol == ticker or (event.received_symbol or "").upper() == ticker
    ]
    decisions = [
        decision for decision in store.list_decisions() if decision.get("ticker") == ticker
    ]
    return {
        "enabled": True,
        "ledger_db_path": str(Path(ledger_db_path).expanduser()),
        "matching_event_count": len(events),
        "events": events[-20:],
        "decisions": decisions[-10:],
    }


def _build_prompt(bundle: dict[str, Any]) -> str:
    compact_bundle = json.dumps(bundle, indent=2, ensure_ascii=False, default=str)
    return f"""# Codex-Assisted Trading Analysis Bundle

You are GPT-5.5 with extra reasoning. Run the full TradingAgents role workflow
using only the bundle evidence below. Simulate the specialized agents as a
structured internal investment committee: analysts gather evidence, researchers
argue bull and bear cases, the trader proposes a transaction, risk managers
challenge it, and the portfolio manager makes the final decision.

Rules:
- Do not claim this is financial advice.
- Do not suggest submitting anything automatically to tax authorities.
- Do not invent unavailable data; call it out as missing or requires_review.
- Keep the discussion audit-friendly and conservative.
- Make role disagreements explicit and resolve them in the final decision.

Required output shape:

## Analyst Team
### Market Analyst
- Key observations:
- Technical signals:
- Data gaps:

### News Analyst
- Relevant news:
- Sentiment:
- Data gaps:

### Fundamentals Analyst
- Financial quality:
- Valuation/quality notes:
- Data gaps:

### Social/Sentiment Analyst
- Crowd/social signal:
- Reliability:
- Data gaps:

## Researcher Team Debate
### Bull Researcher
- Thesis:
- Evidence:
- Weakest assumption:

### Bear Researcher
- Thesis:
- Evidence:
- Weakest assumption:

### Research Manager
- Debate synthesis:
- Evidence score:
- What would change the view:

## Trader Agent
**Action**: Buy | Hold | Sell
**Reasoning**:
**Entry Price**:
**Stop Loss**:
**Position Sizing**:
**Execution Notes**:

## Risk Management Team
### Conservative Risk Analyst
- Objections:
- Required safeguards:

### Neutral Risk Analyst
- Balanced assessment:
- Conditions for action:

### Aggressive Risk Analyst
- Upside case:
- Risk acceptance argument:

## Portfolio Manager Decision
**Rating**: Buy | Overweight | Hold | Underweight | Sell
**Executive Summary**:
**Investment Thesis**:
**Price Target**:
**Time Horizon**:
**Approved Action**:
**Maximum Position Size**:
**Invalidation Conditions**:

## Risk And Fiscal Notes
- Trading risks:
- Ledger/tax recording notes:
- Review flags:

## Audit Metadata
- analysis_mode: {ANALYSIS_MODE}
- workflow_mode: {bundle.get("workflow_mode", WORKFLOW_MODE)}
- model_hint: {bundle.get("model_hint", MODEL_HINT)}
- ticker: {bundle["ticker"]}
- trade_date: {bundle["trade_date"]}
- prompt_hash: {bundle.get("prompt_hash", "computed-after-write")}

Bundle JSON:

```json
{compact_bundle}
```
"""


def _load_bundle(bundle_file: str | Path | None, response_path: Path) -> dict[str, Any]:
    if bundle_file:
        path = Path(bundle_file).expanduser()
    elif (response_path.parent / "bundle.json").exists():
        path = response_path.parent / "bundle.json"
    else:
        text = response_path.read_text(encoding="utf-8")
        match = re.search(r"bundle_json_path:\s*(.+)", text)
        if not match:
            raise ValueError(
                "bundle file is required unless response is next to bundle.json "
                "or contains 'bundle_json_path: ...'"
            )
        path = Path(match.group(1).strip()).expanduser()
    return json.loads(path.read_text(encoding="utf-8"))


def _build_imported_report(
    bundle: dict[str, Any],
    response_text: str,
    rating: str,
    response_hash: str,
    imported_at: str,
) -> str:
    return "\n".join(
        [
            f"# Codex-Assisted Trading Analysis: {bundle['ticker']}",
            "",
            "## Metadata",
            f"- analysis_mode: {ANALYSIS_MODE}",
            f"- workflow_mode: {bundle.get('workflow_mode', WORKFLOW_MODE)}",
            f"- model_hint: {bundle.get('model_hint', MODEL_HINT)}",
            f"- ticker: {bundle['ticker']}",
            f"- trade_date: {bundle['trade_date']}",
            f"- imported_at: {imported_at}",
            f"- rating: {rating}",
            f"- bundle_hash: {bundle.get('bundle_hash')}",
            f"- prompt_hash: {bundle.get('prompt_hash')}",
            f"- response_hash: {response_hash}",
            "",
            "## Codex Response",
            response_text,
        ]
    )
