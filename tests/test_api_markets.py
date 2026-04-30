from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
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
            "market_watchlists_path": str(tmp_path / "watchlists" / "markets.json"),
        }
    )
    monkeypatch.setattr("tradingagents.api.deps.DEFAULT_CONFIG", cfg)
    return cfg


def _history(values):
    dates = pd.date_range("2026-04-24", periods=len(values), freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "Open": values,
            "Close": values,
            "Volume": [1000 + index for index, _ in enumerate(values)],
        },
        index=dates,
    )


def _mock_yfinance(monkeypatch):
    histories = {
        "EDP.LS": _history([3.5, 4.0, float("nan")]),
        "GALP.LS": _history([20.0, 19.0, float("nan")]),
        "AAPL": _history([100.0, 105.0]),
        "MSFT": _history([100.0, 95.0]),
    }

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol.upper()

        @property
        def fast_info(self):
            return {"currency": "EUR" if self.symbol.endswith(".LS") else "USD"}

        def history(self, period="10d", interval="1d"):
            return histories.get(self.symbol, _history([10.0, 10.5])).copy()

    monkeypatch.setattr("tradingagents.markets.service.yf.Ticker", FakeTicker)


def test_market_watchlists_seed_when_missing(monkeypatch, tmp_path):
    cfg = _configure_tmp(monkeypatch, tmp_path)
    client = TestClient(create_app())

    response = client.get("/api/markets/watchlists")

    assert response.status_code == 200
    assert cfg["market_watchlists_path"]
    assert (tmp_path / "watchlists" / "markets.json").exists()
    pt = next(item for item in response.json()["watchlists"] if item["id"] == "pt")
    assert "EDP.LS" in pt["symbols"]


def test_market_movers_sorting_and_nan_close_fallback(monkeypatch, tmp_path):
    _configure_tmp(monkeypatch, tmp_path)
    _mock_yfinance(monkeypatch)
    client = TestClient(create_app())
    client.put("/api/markets/watchlists/pt", json={"symbols": ["EDP.LS", "GALP.LS"]})

    response = client.get("/api/markets/movers?market=pt")

    assert response.status_code == 200
    data = response.json()
    edp = next(item for item in data["quotes"] if item["symbol"] == "EDP.LS")
    assert edp["price"] == 4.0
    assert edp["as_of"].startswith("2026-04-25")
    assert data["top_gainers"][0]["symbol"] == "EDP.LS"
    assert data["top_losers"][0]["symbol"] == "GALP.LS"


def test_market_ticker_detail_includes_ledger_and_decisions(monkeypatch, tmp_path):
    cfg = _configure_tmp(monkeypatch, tmp_path)
    _mock_yfinance(monkeypatch)
    store = LedgerStore(cfg["ledger_db_path"])
    store.add_events(
        [
            LedgerEvent(
                timestamp=datetime(2026, 4, 1, tzinfo=timezone.utc),
                event_type=EventType.TRADE,
                asset_type=AssetType.EQUITY,
                symbol="EDP",
                quantity=Decimal("10"),
                side=TradeSide.BUY,
                price=Decimal("3.50"),
                currency="EUR",
            ),
            LedgerEvent(
                timestamp=datetime(2026, 4, 15, tzinfo=timezone.utc),
                event_type=EventType.TRADE,
                asset_type=AssetType.EQUITY,
                symbol="EDP",
                quantity=Decimal("2"),
                side=TradeSide.SELL,
                price=Decimal("4.00"),
                currency="EUR",
            ),
        ]
    )
    store.record_decision("EDP.LS", "2026-04-30", "Hold", "Decision")
    client = TestClient(create_app())

    response = client.get("/api/markets/tickers/EDP.LS")

    assert response.status_code == 200
    detail = response.json()
    assert detail["quote"]["symbol"] == "EDP.LS"
    assert detail["ledger"]["event_count"] == 2
    assert detail["ledger"]["net_quantity"] == "8"
    assert detail["decisions"][0]["ticker"] == "EDP.LS"
