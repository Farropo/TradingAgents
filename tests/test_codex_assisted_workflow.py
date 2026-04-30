from pathlib import Path

from tradingagents.codex_assisted import (
    import_codex_analysis,
    list_codex_analyses,
    prepare_codex_analysis,
)
from tradingagents.ledger.store import LedgerStore


def _config(tmp_path):
    return {
        "data_cache_dir": str(tmp_path / "cache"),
        "results_dir": str(tmp_path / "logs"),
        "memory_log_path": str(tmp_path / "memory" / "trading_memory.md"),
        "ledger_db_path": str(tmp_path / "ledger" / "ledger.sqlite"),
        "codex_assisted_dir": str(tmp_path / "codex"),
        "data_vendors": {
            "core_stock_apis": "yfinance",
            "technical_indicators": "yfinance",
            "fundamental_data": "yfinance",
            "news_data": "yfinance",
        },
        "tool_vendors": {},
    }


def _collectors():
    return {
        "market_data": lambda ticker, start, end: f"market {ticker} {start} {end}",
        "indicator": lambda ticker, indicator, date, lookback: f"{indicator} {ticker} {date} {lookback}",
        "news": lambda ticker, start, end: f"news {ticker}",
        "global_news": lambda date, lookback, limit: f"global {date}",
        "fundamentals": lambda ticker, date: f"fundamentals {ticker}",
        "balance_sheet": lambda ticker, freq, date: f"balance {ticker}",
        "cashflow": lambda ticker, freq, date: f"cashflow {ticker}",
        "income_statement": lambda ticker, freq, date: f"income {ticker}",
    }


def test_prepare_codex_analysis_writes_bundle_and_prompt(tmp_path):
    prepared = prepare_codex_analysis(
        ticker="nvda",
        trade_date="2026-04-30",
        config=_config(tmp_path),
        collectors=_collectors(),
    )

    assert prepared.bundle_json_path.exists()
    assert prepared.prompt_path.exists()
    prompt = prepared.prompt_path.read_text(encoding="utf-8")
    assert "Codex-Assisted Trading Analysis Bundle" in prompt
    assert "full TradingAgents role workflow" in prompt
    assert "## Analyst Team" in prompt
    assert "## Researcher Team Debate" in prompt
    assert "## Trader Agent" in prompt
    assert "## Risk Management Team" in prompt
    assert "## Portfolio Manager Decision" in prompt
    assert "GPT-5.5 with extra reasoning" in prompt
    assert "**Rating**: Buy | Overweight | Hold | Underweight | Sell" in prompt


def test_import_codex_analysis_records_report_ledger_and_memory(tmp_path):
    cfg = _config(tmp_path)
    prepared = prepare_codex_analysis(
        ticker="NVDA",
        trade_date="2026-04-30",
        config=cfg,
        collectors=_collectors(),
    )
    response = prepared.bundle_dir / "codex_response.md"
    response.write_text(
        "## Portfolio Decision\n\n"
        "**Rating**: Overweight\n\n"
        "**Executive Summary**: Build gradually.\n\n"
        "**Investment Thesis**: Evidence supports measured exposure.",
        encoding="utf-8",
    )

    summary = import_codex_analysis(response, config=cfg)

    assert summary.rating == "Overweight"
    assert summary.report_path.exists()
    report_text = summary.report_path.read_text(encoding="utf-8")
    assert "response_hash" in report_text
    assert "workflow_mode: codex-assisted-full-role" in report_text

    decisions = LedgerStore(cfg["ledger_db_path"]).list_decisions()
    assert len(decisions) == 1
    assert decisions[0]["ticker"] == "NVDA"
    assert decisions[0]["rating"] == "Overweight"

    memory_text = Path(cfg["memory_log_path"]).read_text(encoding="utf-8")
    assert "[2026-04-30 | NVDA | Overweight | pending]" in memory_text

    analyses = list_codex_analyses(config=cfg)
    assert analyses[0]["analysis_id"] == summary.analysis_id
