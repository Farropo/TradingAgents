from decimal import Decimal

import pytest

from tradingagents.ledger.models import AssetType, EventType, LedgerEvent, TradeSide
from tradingagents.ledger.store import LedgerStore


def _event(external_id="t1"):
    return LedgerEvent(
        timestamp="2024-01-10T10:00:00Z",
        event_type=EventType.TRADE,
        side=TradeSide.BUY,
        asset_type=AssetType.EQUITY,
        symbol="AAPL",
        isin="US0378331005",
        quantity=Decimal("10.12345678"),
        price=Decimal("100.12"),
        currency="USD",
        fee=Decimal("1.23"),
        fee_currency="USD",
        fx_rate_to_eur=Decimal("0.92"),
        broker="DEGIRO",
        account="main",
        external_id=external_id,
    )


@pytest.mark.unit
def test_store_initializes_schema_and_round_trips_decimal(tmp_path):
    store = LedgerStore(tmp_path / "ledger.sqlite")
    summary = store.import_events([_event()], "sample.csv", "generic", source_hash="file-1")

    assert summary.inserted_count == 1
    events = store.list_events()
    assert len(events) == 1
    assert events[0].quantity == Decimal("10.12345678")
    assert events[0].price == Decimal("100.12")
    assert events[0].fx_rate_to_eur == Decimal("0.92")


@pytest.mark.unit
def test_import_batch_is_idempotent_by_source_hash(tmp_path):
    store = LedgerStore(tmp_path / "ledger.sqlite")
    first = store.import_events([_event()], "sample.csv", "generic", source_hash="same-file")
    second = store.import_events([_event()], "sample.csv", "generic", source_hash="same-file")

    assert first.inserted_count == 1
    assert second.inserted_count == 0
    assert second.skipped_count == 1
    assert len(store.list_events()) == 1


@pytest.mark.unit
def test_record_decision_is_idempotent(tmp_path):
    store = LedgerStore(tmp_path / "ledger.sqlite")
    first_id = store.record_decision("NVDA", "2026-01-15", "Buy", "Rating: Buy")
    second_id = store.record_decision("NVDA", "2026-01-15", "Buy", "Rating: Buy")

    assert first_id == second_id
    decisions = store.list_decisions()
    assert len(decisions) == 1
    assert decisions[0]["ticker"] == "NVDA"


@pytest.mark.unit
def test_list_events_filters_by_year_broker_and_account(tmp_path):
    store = LedgerStore(tmp_path / "ledger.sqlite")
    store.import_events(
        [
            _event("a"),
            LedgerEvent(
                timestamp="2025-02-10T10:00:00Z",
                event_type=EventType.TRADE,
                side=TradeSide.BUY,
                asset_type=AssetType.EQUITY,
                symbol="MSFT",
                quantity=Decimal("1"),
                price=Decimal("10"),
                broker="IBKR",
                account="other",
                external_id="b",
            ),
        ],
        "sample.csv",
        "generic",
        source_hash="file-2",
    )

    assert [event.symbol for event in store.list_events(year=2024)] == ["AAPL"]
    assert [event.symbol for event in store.list_events(broker="IBKR")] == ["MSFT"]
    assert [event.symbol for event in store.list_events(account="main")] == ["AAPL"]
