from decimal import Decimal

import pytest

from tradingagents.ledger.importers.csv import CsvImportError, import_csv_to_store, preview_csv
from tradingagents.ledger.models import AssetType, EventType, TradeSide
from tradingagents.ledger.store import LedgerStore


@pytest.mark.unit
def test_preview_csv_normalizes_generic_rows_with_bom_and_decimal_comma(tmp_path):
    csv_path = tmp_path / "trades.csv"
    csv_path.write_text(
        "\ufefftrade_id,trade_at,type,asset_type,symbol,quantity,price,currency,fee,fee_currency,fx_rate_to_eur,broker,account\n"
        "row-1,2024-01-10T10:00:00Z,BUY,EQUITY,AAPL,\"1,5\",\"100,25\",EUR,\"1,20\",EUR,1,DEGIRO,main\n",
        encoding="utf-8",
    )

    preview = preview_csv(csv_path)

    assert preview.errors == []
    event = preview.events[0]
    assert event.event_type == EventType.TRADE
    assert event.side == TradeSide.BUY
    assert event.asset_type == AssetType.EQUITY
    assert event.quantity == Decimal("1.5")
    assert event.price == Decimal("100.25")
    assert event.fee == Decimal("1.20")


@pytest.mark.unit
def test_preview_marks_missing_non_eur_fx_for_review(tmp_path):
    csv_path = tmp_path / "trades.csv"
    csv_path.write_text(
        "trade_id,trade_at,type,asset_type,symbol,quantity,price,currency,fee,fee_currency,broker,account\n"
        "row-1,2024-01-10T10:00:00Z,BUY,EQUITY,AAPL,1,100,USD,1,USD,DEGIRO,main\n",
        encoding="utf-8",
    )

    preview = preview_csv(csv_path)

    assert preview.errors == []
    assert preview.events[0].requires_review is True
    assert "missing FX rate" in preview.events[0].review_reason


@pytest.mark.unit
def test_preview_reports_invalid_rows(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "trade_id,trade_at,type,asset_type,symbol,quantity,price,currency\n"
        "row-1,2024-01-10T10:00:00Z,BUY,EQUITY,AAPL,-1,100,EUR\n",
        encoding="utf-8",
    )

    preview = preview_csv(csv_path)

    assert len(preview.errors) == 1
    assert "quantity must be positive" in preview.errors[0]


@pytest.mark.unit
def test_import_csv_to_store_is_idempotent(tmp_path):
    csv_path = tmp_path / "trades.csv"
    csv_path.write_text(
        "trade_id,trade_at,type,asset_type,symbol,quantity,price,currency,fee,fee_currency,fx_rate_to_eur,broker,account\n"
        "row-1,2024-01-10T10:00:00Z,BUY,EQUITY,AAPL,1,100,EUR,1,EUR,1,DEGIRO,main\n",
        encoding="utf-8",
    )
    store = LedgerStore(tmp_path / "ledger.sqlite")

    first = import_csv_to_store(csv_path, store)
    second = import_csv_to_store(csv_path, store)

    assert first.inserted_count == 1
    assert second.inserted_count == 0
    assert second.skipped_count == 1


@pytest.mark.unit
def test_import_csv_raises_when_preview_has_errors(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "trade_id,trade_at,type,asset_type,symbol,quantity,price,currency\n"
        "row-1,2024-01-10T10:00:00Z,BOGUS,EQUITY,AAPL,1,100,EUR\n",
        encoding="utf-8",
    )
    store = LedgerStore(tmp_path / "ledger.sqlite")

    with pytest.raises(CsvImportError):
        import_csv_to_store(csv_path, store)
