from decimal import Decimal

import pytest

from tradingagents.ledger.models import AssetType, EventType, IncomeType, LedgerEvent, TradeSide
from tradingagents.ledger.tax.pt import (
    PT_CRYPTO_EXEMPT_365D,
    PT_CRYPTO_TAXABLE,
    PT_INCOME_REVIEW,
    PT_SECURITIES,
    build_pt_tax_report,
)


def _crypto(date, side, symbol, qty, price, external_id, **kwargs):
    return LedgerEvent(
        timestamp=f"{date}T00:00:00Z",
        event_type=EventType.TRADE,
        side=side,
        asset_type=AssetType.CRYPTO,
        symbol=symbol,
        quantity=Decimal(qty),
        price=Decimal(price),
        currency="EUR",
        fee=Decimal(kwargs.pop("fee", "0")),
        fee_currency="EUR",
        broker="Kraken",
        account="main",
        external_id=external_id,
        **kwargs,
    )


@pytest.mark.unit
def test_crypto_disposal_before_365_days_is_taxable_category_g():
    report = build_pt_tax_report(
        [
            _crypto("2023-01-01", TradeSide.BUY, "BTC", "1", "10000", "b1"),
            _crypto("2023-12-31", TradeSide.SELL, "BTC", "1", "20000", "s1"),
        ],
        year=2023,
    )

    assert report.rows[0].holding_days == 364
    assert report.rows[0].tax_treatment == PT_CRYPTO_TAXABLE
    assert report.rows[0].appendix == "G"


@pytest.mark.unit
def test_crypto_disposal_after_365_days_is_exempt_reportable_g1():
    report = build_pt_tax_report(
        [
            _crypto("2023-01-01", TradeSide.BUY, "BTC", "1", "10000", "b1"),
            _crypto("2024-01-01", TradeSide.SELL, "BTC", "1", "20000", "s1"),
        ],
        year=2024,
    )

    assert report.rows[0].holding_days == 365
    assert report.rows[0].tax_treatment == PT_CRYPTO_EXEMPT_365D
    assert report.rows[0].appendix == "G1"


@pytest.mark.unit
def test_crypto_to_crypto_swap_defers_disposal_and_carries_cost_basis():
    swap = LedgerEvent(
        timestamp="2023-06-01T00:00:00Z",
        event_type=EventType.TRADE,
        side=TradeSide.SWAP,
        asset_type=AssetType.CRYPTO,
        symbol="BTC",
        quantity=Decimal("1"),
        price=Decimal("20000"),
        currency="EUR",
        received_symbol="ETH",
        received_asset_type=AssetType.CRYPTO,
        received_quantity=Decimal("10"),
        broker="Kraken",
        account="main",
        external_id="swap1",
    )
    report = build_pt_tax_report(
        [
            _crypto("2023-01-01", TradeSide.BUY, "BTC", "1", "10000", "b1"),
            swap,
            _crypto("2024-01-02", TradeSide.SELL, "ETH", "10", "1500", "s1"),
        ],
        year=2024,
    )

    assert len(report.rows) == 1
    assert report.rows[0].symbol == "ETH"
    assert report.rows[0].cost_basis_eur == Decimal("10000")
    assert report.rows[0].gain_eur == Decimal("5000")


@pytest.mark.unit
def test_security_token_crypto_uses_securities_treatment_not_365_day_exemption():
    report = build_pt_tax_report(
        [
            _crypto("2023-01-01", TradeSide.BUY, "TOKEN", "1", "100", "b1", security_token=True),
            _crypto("2024-01-02", TradeSide.SELL, "TOKEN", "1", "200", "s1", security_token=True),
        ],
        year=2024,
    )

    assert report.rows[0].tax_treatment == PT_SECURITIES


@pytest.mark.unit
def test_crypto_staking_income_is_marked_for_review():
    event = LedgerEvent(
        timestamp="2024-06-01T00:00:00Z",
        event_type=EventType.INCOME,
        income_type=IncomeType.STAKING,
        asset_type=AssetType.CRYPTO,
        symbol="ETH",
        quantity=Decimal("0.25"),
        price=Decimal("3000"),
        currency="EUR",
        broker="Kraken",
        account="main",
        external_id="stake1",
    )

    report = build_pt_tax_report([event], year=2024)

    assert report.rows[0].tax_treatment == PT_INCOME_REVIEW
    assert report.rows[0].requires_review is True
