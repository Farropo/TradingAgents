from decimal import Decimal

import pytest

from tradingagents.ledger.models import AssetType, EventType, LedgerEvent, TradeSide
from tradingagents.ledger.tax.fifo import FifoCalculator, InsufficientHoldingsError


def _trade(date, side, qty, price, external_id, fee="0"):
    return LedgerEvent(
        timestamp=f"{date}T10:00:00Z",
        event_type=EventType.TRADE,
        side=side,
        asset_type=AssetType.EQUITY,
        symbol="AAPL",
        quantity=Decimal(qty),
        price=Decimal(price),
        currency="EUR",
        fee=Decimal(fee),
        fee_currency="EUR",
        broker="DEGIRO",
        account="main",
        external_id=external_id,
    )


@pytest.mark.unit
def test_partial_sale_consumes_oldest_lot_first_and_applies_fees():
    calc = FifoCalculator()
    disposals = calc.process_all(
        [
            _trade("2024-01-01", TradeSide.BUY, "10", "100", "b1", fee="10"),
            _trade("2024-02-01", TradeSide.SELL, "4", "120", "s1", fee="4"),
        ]
    )

    assert len(disposals) == 1
    assert disposals[0].quantity == Decimal("4")
    assert disposals[0].cost_basis_eur == Decimal("404")
    assert disposals[0].proceeds_eur == Decimal("476")
    assert disposals[0].gain_eur == Decimal("72")
    assert calc.inventory()[0].remaining_quantity == Decimal("6")


@pytest.mark.unit
def test_one_sale_spans_multiple_buy_lots():
    calc = FifoCalculator()
    disposals = calc.process_all(
        [
            _trade("2024-01-01", TradeSide.BUY, "2", "100", "b1"),
            _trade("2024-01-02", TradeSide.BUY, "3", "110", "b2"),
            _trade("2024-02-01", TradeSide.SELL, "4", "120", "s1"),
        ]
    )

    assert [d.quantity for d in disposals] == [Decimal("2"), Decimal("2")]
    assert sum((d.cost_basis_eur for d in disposals), Decimal("0")) == Decimal("420")


@pytest.mark.unit
def test_same_day_order_uses_source_row():
    buy = _trade("2024-01-01", TradeSide.BUY, "1", "100", "b1")
    buy = LedgerEvent(**{**buy.to_record(include_raw=False), "source_row": 3, "source_hash": None})
    sell = _trade("2024-01-01", TradeSide.SELL, "1", "110", "s1")
    sell = LedgerEvent(**{**sell.to_record(include_raw=False), "source_row": 4, "source_hash": None})

    disposals = FifoCalculator().process_all([sell, buy])

    assert len(disposals) == 1
    assert disposals[0].gain_eur == Decimal("10")


@pytest.mark.unit
def test_selling_more_than_holdings_raises():
    with pytest.raises(InsufficientHoldingsError):
        FifoCalculator().process_all(
            [
                _trade("2024-01-01", TradeSide.BUY, "1", "100", "b1"),
                _trade("2024-02-01", TradeSide.SELL, "2", "120", "s1"),
            ]
        )


@pytest.mark.unit
def test_sale_reports_in_disposal_year_not_acquisition_year():
    disposal = FifoCalculator().process_all(
        [
            _trade("2023-12-31", TradeSide.BUY, "1", "100", "b1"),
            _trade("2024-01-02", TradeSide.SELL, "1", "120", "s1"),
        ]
    )[0]

    assert disposal.event.timestamp.year == 2024
