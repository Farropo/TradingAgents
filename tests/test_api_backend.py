from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
from tradingagents.api.analysis_jobs import manager
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.ledger.models import AssetType, EventType, LedgerEvent, TradeSide
from tradingagents.ledger.store import LedgerStore


def _configure_tmp(monkeypatch, tmp_path):
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(
        {
            "results_dir": str(tmp_path / "logs"),
            "data_cache_dir": str(tmp_path / "cache"),
            "memory_log_path": str(tmp_path / "memory" / "trading_memory.md"),
            "ledger_db_path": str(tmp_path / "ledger" / "ledger.sqlite"),
            "codex_assisted_dir": str(tmp_path / "codex"),
        }
    )
    monkeypatch.setattr("tradingagents.api.deps.DEFAULT_CONFIG", cfg)
    monkeypatch.setattr("tradingagents.api.utils.DEFAULT_CONFIG", cfg, raising=False)
    monkeypatch.setattr("tradingagents.api.reports.DEFAULT_CONFIG", cfg)
    monkeypatch.setattr("tradingagents.api.analysis_jobs.DEFAULT_CONFIG", cfg)
    monkeypatch.setattr("tradingagents.codex_assisted.workflow.DEFAULT_CONFIG", cfg)
    return cfg


def _client(monkeypatch, tmp_path):
    _configure_tmp(monkeypatch, tmp_path)
    return TestClient(create_app())


def test_health_and_defaults(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    assert client.get("/api/health").json()["local_only"] is True
    defaults = client.get("/api/config/defaults").json()
    assert "ledger_db_path" in defaults["paths"]
    assert defaults["llm"]["provider"]
    assert defaults["message"].startswith("Local-only")


def test_ledger_preview_import_and_fiscal_summary(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    csv_data = (
        "trade_id,trade_at,type,asset_type,symbol,quantity,price,currency,fee,fee_currency,fx_rate_to_eur,broker,account\n"
        "b1,2024-01-01T00:00:00Z,BUY,EQUITY,AAPL,1,100,EUR,1,EUR,1,DEGIRO,main\n"
        "s1,2024-02-01T00:00:00Z,SELL,EQUITY,AAPL,1,120,EUR,1,EUR,1,DEGIRO,main\n"
    )

    preview = client.post(
        "/api/ledger/imports/preview",
        files={"file": ("trades.csv", csv_data, "text/csv")},
    )
    assert preview.status_code == 200
    assert len(preview.json()["events"]) == 2

    imported = client.post(
        "/api/ledger/imports",
        files={"file": ("trades.csv", csv_data, "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["inserted_count"] == 2

    fiscal = client.get("/api/fiscal/pt/2024")
    assert fiscal.status_code == 200
    assert fiscal.json()["rows"][0]["gain_eur"] == "18"

    exported = client.get("/api/fiscal/pt/2024/export?format=csv")
    assert exported.status_code == 200
    assert "gain_eur" in exported.text


def test_codex_bundle_import_and_dashboard(monkeypatch, tmp_path):
    cfg = _configure_tmp(monkeypatch, tmp_path)
    client = TestClient(create_app())

    def fake_prepare(**kwargs):
        bundle_dir = Path(kwargs.get("output_dir") or cfg["codex_assisted_dir"]) / "NVDA" / "2026-04-30" / "bundle-1"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_json = bundle_dir / "bundle.json"
        prompt = bundle_dir / "prompt.md"
        bundle_json.write_text('{"ticker":"NVDA","trade_date":"2026-04-30","bundle_hash":"abc","prompt_hash":"def"}', encoding="utf-8")
        prompt.write_text("prompt body", encoding="utf-8")
        return SimpleNamespace(
            bundle_id="bundle-1",
            bundle_dir=bundle_dir,
            bundle_json_path=bundle_json,
            prompt_path=prompt,
            prompt_hash="def",
        )

    monkeypatch.setattr("tradingagents.api.routers.codex.prepare_codex_analysis", fake_prepare)
    bundle = client.post("/api/codex/bundles", json={"ticker": "NVDA", "date": "2026-04-30"}).json()
    assert bundle["prompt"] == "prompt body"

    imported = client.post(
        "/api/codex/import",
        json={"bundle_id": "bundle-1", "response_text": "**Rating**: Buy\n\nDecision."},
    )
    assert imported.status_code == 200
    assert imported.json()["rating"] == "Buy"
    assert client.get("/api/dashboard").json()["decisions"] == 1


def test_analysis_job_with_mocked_graph(monkeypatch, tmp_path):
    cfg = _configure_tmp(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    class DummyGraph:
        def __init__(self, *args, **kwargs):
            pass

        def propagate(self, ticker, date):
            return (
                {
                    "market_report": "Market",
                    "investment_plan": "Plan",
                    "trader_investment_plan": "Trader",
                    "final_trade_decision": "**Rating**: Hold\nThesis.",
                },
                "Hold",
            )

    monkeypatch.setattr("tradingagents.api.analysis_jobs.TradingAgentsGraph", DummyGraph)
    client = TestClient(create_app())
    response = client.post("/api/analyses", json={"ticker": "NVDA", "date": "2026-04-30"})
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # The dummy graph is synchronous and fast; poll a few times for completion.
    status = None
    for _ in range(20):
        status = client.get(f"/api/analyses/{run_id}").json()
        if status["status"] == "completed":
            break
    assert status["status"] == "completed"
    report = client.get(f"/api/analyses/{run_id}/report")
    assert report.status_code == 200
    assert "TradingAgents API Analysis" in report.json()["content"]


def test_analysis_job_without_api_key_returns_clean_guidance(monkeypatch, tmp_path):
    _configure_tmp(monkeypatch, tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = TestClient(create_app())

    capability = client.get("/api/analyses/capability")
    assert capability.status_code == 200
    assert capability.json()["normal_available"] is False
    assert capability.json()["recommended_mode"] == "codex-assisted"

    response = client.post("/api/analyses", json={"ticker": "NVDA", "date": "2026-04-30"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "Codex Assisted" in detail
    assert "Traceback" not in detail
