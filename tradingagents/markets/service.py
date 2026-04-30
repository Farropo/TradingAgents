"""Local watchlists and delayed market quotes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
from pathlib import Path
from typing import Any, Iterable, Literal

import pandas as pd
import yfinance as yf

from tradingagents.ledger.models import EventType, TradeSide
from tradingagents.ledger.store import LedgerStore


MarketId = Literal["pt", "us", "all"]


DEFAULT_WATCHLISTS: dict[str, dict[str, Any]] = {
    "pt": {
        "label": "Portugal",
        "items": [
            {"symbol": "EDP.LS", "name": "EDP"},
            {"symbol": "GALP.LS", "name": "Galp Energia"},
            {"symbol": "BCP.LS", "name": "Millennium BCP"},
            {"symbol": "JMT.LS", "name": "Jeronimo Martins"},
            {"symbol": "EDPR.LS", "name": "EDP Renovaveis"},
            {"symbol": "SON.LS", "name": "Sonae"},
            {"symbol": "NOS.LS", "name": "NOS"},
            {"symbol": "NVG.LS", "name": "Navigator"},
            {"symbol": "REN.LS", "name": "REN"},
            {"symbol": "SEM.LS", "name": "Semapa"},
        ],
    },
    "us": {
        "label": "EUA",
        "items": [
            {"symbol": "AAPL", "name": "Apple"},
            {"symbol": "MSFT", "name": "Microsoft"},
            {"symbol": "NVDA", "name": "NVIDIA"},
            {"symbol": "AMZN", "name": "Amazon"},
            {"symbol": "GOOGL", "name": "Alphabet"},
            {"symbol": "META", "name": "Meta Platforms"},
            {"symbol": "TSLA", "name": "Tesla"},
            {"symbol": "AMD", "name": "AMD"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
            {"symbol": "QQQ", "name": "Invesco QQQ ETF"},
        ],
    },
}


@dataclass(frozen=True)
class WatchlistItem:
    symbol: str
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "name": self.name}


def load_watchlists(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    path = _watchlists_path(config)
    if not path.exists():
        _write_watchlists(path, DEFAULT_WATCHLISTS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raw = DEFAULT_WATCHLISTS
        _write_watchlists(path, raw)
    return _normalize_watchlists(raw)


def save_watchlist(config: dict[str, Any], watchlist_id: str, symbols: Iterable[str]) -> dict[str, Any]:
    watchlist_id = watchlist_id.lower().strip()
    if watchlist_id not in ("pt", "us"):
        raise ValueError("watchlist_id must be 'pt' or 'us'")

    watchlists = load_watchlists(config)
    current_names = {
        item["symbol"].upper(): item.get("name")
        for item in watchlists.get(watchlist_id, {}).get("items", [])
    }
    items = []
    seen = set()
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append({"symbol": normalized, "name": current_names.get(normalized)})

    watchlists[watchlist_id] = {
        "label": watchlists.get(watchlist_id, {}).get("label") or DEFAULT_WATCHLISTS[watchlist_id]["label"],
        "items": items,
    }
    _write_watchlists(_watchlists_path(config), watchlists)
    return _watchlist_response(watchlist_id, watchlists[watchlist_id])


def get_watchlists_response(config: dict[str, Any]) -> dict[str, Any]:
    watchlists = load_watchlists(config)
    return {
        "watchlists": [
            _watchlist_response("pt", watchlists["pt"]),
            _watchlist_response("us", watchlists["us"]),
        ]
    }


def get_market_movers(config: dict[str, Any], market: str = "all") -> dict[str, Any]:
    market = market.lower().strip()
    if market not in ("pt", "us", "all"):
        raise ValueError("market must be pt, us, or all")

    watchlists = load_watchlists(config)
    items = _items_for_market(watchlists, market)
    quotes = [quote_symbol(item.symbol, item.name) for item in items]
    movable = [quote for quote in quotes if quote.get("status") == "ok" and quote.get("change_percent") is not None]
    gainers = sorted(
        [quote for quote in movable if quote["change_percent"] > 0],
        key=lambda item: item["change_percent"],
        reverse=True,
    )
    losers = sorted(
        [quote for quote in movable if quote["change_percent"] < 0],
        key=lambda item: item["change_percent"],
    )
    return {
        "market": market,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance",
        "quotes": quotes,
        "top_gainers": gainers[:10],
        "top_losers": losers[:10],
    }


def get_market_detail(config: dict[str, Any], symbol: str) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    watchlists = load_watchlists(config)
    name = None
    for item in _items_for_market(watchlists, "all"):
        if item.symbol == symbol:
            name = item.name
            break

    quote = quote_symbol(symbol, name, period="35d")
    history = quote.pop("history", [])
    ledger = _ledger_exposure(config, symbol)
    return {
        "symbol": symbol,
        "quote": quote,
        "history": history[-30:],
        "ledger": ledger,
        "decisions": _decisions_for_symbol(config, symbol),
    }


def quote_symbol(symbol: str, name: str | None = None, period: str = "10d") -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period=period, interval="1d")
        fast_info = _safe_fast_info(ticker)
        return _quote_from_history(symbol, name, history, fast_info)
    except Exception as exc:
        return _empty_quote(symbol, name, "error", str(exc))


def normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _quote_from_history(
    symbol: str,
    name: str | None,
    history: pd.DataFrame,
    fast_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if history is None or history.empty or "Close" not in history.columns:
        return _empty_quote(symbol, name, "data_unavailable", "No price history returned")

    rows = history.copy()
    rows = rows[rows["Close"].notna()]
    if rows.empty:
        return _empty_quote(symbol, name, "data_unavailable", "No non-null close price returned")

    latest = rows.iloc[-1]
    previous = rows.iloc[-2] if len(rows) >= 2 else None
    close = _number(latest.get("Close"))
    previous_close = _number(previous.get("Close")) if previous is not None else None
    change = close - previous_close if close is not None and previous_close is not None else None
    change_percent = (
        (change / previous_close) * 100
        if change is not None and previous_close not in (None, 0)
        else None
    )

    history_points = []
    for index, row in rows.tail(30).iterrows():
        close_value = _number(row.get("Close"))
        if close_value is None:
            continue
        history_points.append(
            {
                "date": _date_value(index),
                "close": close_value,
                "volume": _integer(row.get("Volume")),
            }
        )

    return {
        "symbol": symbol,
        "name": name or _fast_info_value(fast_info, "shortName") or _fast_info_value(fast_info, "longName"),
        "market": _market_for_symbol(symbol),
        "currency": _fast_info_value(fast_info, "currency") or _default_currency(symbol),
        "price": close,
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_percent,
        "volume": _integer(latest.get("Volume")),
        "as_of": _date_value(rows.index[-1]),
        "source": "yfinance",
        "status": "ok",
        "message": None,
        "history": history_points,
    }


def _ledger_exposure(config: dict[str, Any], symbol: str) -> dict[str, Any]:
    symbols = _symbol_candidates(symbol)
    try:
        store = LedgerStore(config["ledger_db_path"])
        events = [event for event in store.list_events() if event.symbol in symbols]
    except Exception as exc:
        return {
            "event_count": 0,
            "net_quantity": "0",
            "buy_quantity": "0",
            "sell_quantity": "0",
            "latest_event_at": None,
            "error": str(exc),
        }

    buy_quantity = Decimal("0")
    sell_quantity = Decimal("0")
    net_quantity = Decimal("0")
    latest = None
    for event in events:
        if event.event_type == EventType.TRADE and event.side == TradeSide.BUY:
            buy_quantity += event.quantity
            net_quantity += event.quantity
        elif event.event_type == EventType.TRADE and event.side == TradeSide.SELL:
            sell_quantity += event.quantity
            net_quantity -= event.quantity
        latest = event.timestamp.isoformat()

    return {
        "event_count": len(events),
        "net_quantity": format(net_quantity, "f"),
        "buy_quantity": format(buy_quantity, "f"),
        "sell_quantity": format(sell_quantity, "f"),
        "latest_event_at": latest,
        "error": None,
    }


def _decisions_for_symbol(config: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    symbols = _symbol_candidates(symbol)
    try:
        store = LedgerStore(config["ledger_db_path"])
        decisions = [decision for decision in store.list_decisions() if normalize_symbol(decision.get("ticker")) in symbols]
    except Exception:
        return []
    return sorted(decisions, key=lambda item: item.get("trade_date", ""), reverse=True)[:10]


def _items_for_market(watchlists: dict[str, dict[str, Any]], market: str) -> list[WatchlistItem]:
    ids = ("pt", "us") if market == "all" else (market,)
    items: list[WatchlistItem] = []
    seen = set()
    for watchlist_id in ids:
        for item in watchlists.get(watchlist_id, {}).get("items", []):
            symbol = normalize_symbol(item.get("symbol"))
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            items.append(WatchlistItem(symbol=symbol, name=item.get("name")))
    return items


def _normalize_watchlists(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized = {}
    for watchlist_id in ("pt", "us"):
        source = raw.get(watchlist_id) or DEFAULT_WATCHLISTS[watchlist_id]
        raw_items = source.get("items") or source.get("symbols") or []
        items = []
        for raw_item in raw_items:
            if isinstance(raw_item, str):
                symbol = normalize_symbol(raw_item)
                name = None
            else:
                symbol = normalize_symbol(raw_item.get("symbol"))
                name = raw_item.get("name")
            if symbol:
                items.append({"symbol": symbol, "name": name})
        normalized[watchlist_id] = {
            "label": source.get("label") or DEFAULT_WATCHLISTS[watchlist_id]["label"],
            "items": items,
        }
    return normalized


def _watchlist_response(watchlist_id: str, watchlist: dict[str, Any]) -> dict[str, Any]:
    items = [WatchlistItem(**item).to_dict() for item in watchlist.get("items", [])]
    return {
        "id": watchlist_id,
        "label": watchlist.get("label") or watchlist_id.upper(),
        "symbols": [item["symbol"] for item in items],
        "items": items,
    }


def _watchlists_path(config: dict[str, Any]) -> Path:
    return Path(config["market_watchlists_path"]).expanduser()


def _write_watchlists(path: Path, watchlists: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(watchlists, indent=2, sort_keys=True), encoding="utf-8")


def _empty_quote(symbol: str, name: str | None, status: str, message: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": name,
        "market": _market_for_symbol(symbol),
        "currency": _default_currency(symbol),
        "price": None,
        "previous_close": None,
        "change": None,
        "change_percent": None,
        "volume": None,
        "as_of": None,
        "source": "yfinance",
        "status": status,
        "message": message,
        "history": [],
    }


def _market_for_symbol(symbol: str) -> str:
    return "pt" if symbol.endswith(".LS") else "us"


def _default_currency(symbol: str) -> str:
    return "EUR" if symbol.endswith(".LS") else "USD"


def _symbol_candidates(symbol: str) -> set[str]:
    normalized = normalize_symbol(symbol)
    candidates = {normalized}
    if "." in normalized:
        candidates.add(normalized.split(".", 1)[0])
    return candidates


def _safe_fast_info(ticker) -> dict[str, Any]:
    try:
        info = ticker.fast_info
        return dict(info) if info else {}
    except Exception:
        return {}


def _fast_info_value(info: dict[str, Any] | None, key: str) -> Any:
    if not info:
        return None
    try:
        return info.get(key)
    except AttributeError:
        return None


def _date_value(index_value: Any) -> str:
    try:
        return index_value.isoformat()
    except AttributeError:
        return str(index_value)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _integer(value: Any) -> int | None:
    number = _number(value)
    if number is None:
        return None
    return int(number)
