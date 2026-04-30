from decimal import Decimal

import pytest

from tradingagents.ledger.importers.csv import import_csv_to_store
from tradingagents.ledger.store import LedgerStore
from tradingagents.ledger.tax.pt import PT_CRYPTO_EXEMPT_365D, PT_SECURITIES, build_pt_tax_report


@pytest.mark.unit
def test_import_to_store_to_pt_tax_report_regression(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "trade_id,trade_at,type,asset_type,symbol,isin,quantity,price,currency,fee,fee_currency,fx_rate_to_eur,broker,account\n"
        "degiro-1,2024-01-10T10:00:00Z,BUY,EQUITY,AAPL,US0378331005,10,100.00,USD,1.00,USD,0.92,DEGIRO,main\n"
        "degiro-2,2024-03-10T10:00:00Z,SELL,EQUITY,AAPL,US0378331005,4,120.00,USD,1.00,USD,0.91,DEGIRO,main\n"
        "crypto-1,2023-01-01T00:00:00Z,BUY,CRYPTO,BTC,,1,16000.00,EUR,10.00,EUR,1,Kraken,main\n"
        "crypto-2,2024-01-02T00:00:00Z,SELL,CRYPTO,BTC,,1,30000.00,EUR,20.00,EUR,1,Kraken,main\n",
        encoding="utf-8",
    )
    store = LedgerStore(tmp_path / "ledger.sqlite")

    first = import_csv_to_store(csv_path, store)
    second = import_csv_to_store(csv_path, store)
    report = build_pt_tax_report(store.list_events(), year=2024)

    assert first.inserted_count == 4
    assert second.inserted_count == 0
    rows = {row.symbol: row for row in report.rows}
    assert rows["BTC"].tax_treatment == PT_CRYPTO_EXEMPT_365D
    assert rows["BTC"].proceeds_eur == Decimal("29980.00")
    assert rows["BTC"].cost_basis_eur == Decimal("16010.00")
    assert rows["BTC"].gain_eur == Decimal("13970.00")
    assert rows["AAPL"].tax_treatment == PT_SECURITIES
    assert len(report.inventory) == 1
    assert report.inventory[0]["symbol"] == "AAPL"
    assert report.inventory[0]["remaining_quantity"] == "6"
