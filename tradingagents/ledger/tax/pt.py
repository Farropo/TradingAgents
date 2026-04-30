"""Portugal-oriented tax report helpers.

This module prepares auditable data for IRS work; it does not submit tax
returns and should not be treated as personal tax advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from tradingagents.ledger.models import AssetType, EventType, LedgerEvent, decimal_to_str
from tradingagents.ledger.tax.fifo import DisposalMatch, FifoCalculator


PT_CRYPTO_EXEMPT_365D = "PT_CRYPTO_365D_EXEMPT_G1"
PT_CRYPTO_TAXABLE = "PT_CRYPTO_TAXABLE_G"
PT_SECURITIES = "PT_SECURITIES_G_OR_J"
PT_DERIVATIVE_REVIEW = "PT_DERIVATIVE_REVIEW"
PT_INCOME_REVIEW = "PT_INCOME_REVIEW"


@dataclass(frozen=True)
class TaxReportRow:
    tax_year: int
    appendix: str
    category: str
    asset_type: str
    symbol: str
    isin: Optional[str]
    acquisition_date: str
    realization_date: str
    quantity: Decimal
    proceeds_eur: Decimal
    cost_basis_eur: Decimal
    expenses_eur: Decimal
    gain_eur: Decimal
    holding_days: int
    tax_treatment: str
    broker: Optional[str] = None
    account: Optional[str] = None
    source_country: Optional[str] = None
    requires_review: bool = False
    review_reason: Optional[str] = None

    def as_dict(self) -> dict[str, object]:
        return {
            "tax_year": self.tax_year,
            "appendix": self.appendix,
            "category": self.category,
            "asset_type": self.asset_type,
            "symbol": self.symbol,
            "isin": self.isin,
            "acquisition_date": self.acquisition_date,
            "realization_date": self.realization_date,
            "quantity": decimal_to_str(self.quantity),
            "proceeds_eur": decimal_to_str(self.proceeds_eur),
            "cost_basis_eur": decimal_to_str(self.cost_basis_eur),
            "expenses_eur": decimal_to_str(self.expenses_eur),
            "gain_eur": decimal_to_str(self.gain_eur),
            "holding_days": self.holding_days,
            "tax_treatment": self.tax_treatment,
            "broker": self.broker,
            "account": self.account,
            "source_country": self.source_country,
            "requires_review": self.requires_review,
            "review_reason": self.review_reason,
        }


@dataclass(frozen=True)
class TaxReport:
    jurisdiction: str
    year: Optional[int]
    rows: list[TaxReportRow]
    inventory: list[dict[str, object]]
    review_notes: list[str]

    def as_dicts(self) -> list[dict[str, object]]:
        return [row.as_dict() for row in self.rows]

    def totals_by_treatment(self) -> dict[str, dict[str, str]]:
        totals: dict[str, dict[str, Decimal]] = {}
        for row in self.rows:
            bucket = totals.setdefault(
                row.tax_treatment,
                {"proceeds_eur": Decimal("0"), "cost_basis_eur": Decimal("0"), "gain_eur": Decimal("0")},
            )
            bucket["proceeds_eur"] += row.proceeds_eur
            bucket["cost_basis_eur"] += row.cost_basis_eur
            bucket["gain_eur"] += row.gain_eur
        return {
            treatment: {key: decimal_to_str(value) for key, value in values.items()}
            for treatment, values in totals.items()
        }


def build_pt_tax_report(events: Iterable[LedgerEvent], year: Optional[int] = None) -> TaxReport:
    event_list = list(events)
    calculator = FifoCalculator()
    disposals = calculator.process_all(event_list)

    rows = [
        _row_from_disposal(match)
        for match in disposals
        if year is None or match.event.timestamp.year == year
    ]
    rows.extend(_income_review_rows(event_list, year))
    rows.sort(key=lambda r: (r.realization_date, r.symbol, r.acquisition_date))

    inventory = [
        {
            "broker": lot.broker,
            "account": lot.account,
            "asset_type": lot.asset_type.value,
            "symbol": lot.symbol,
            "acquisition_date": lot.acquisition_date.date().isoformat(),
            "remaining_quantity": decimal_to_str(lot.remaining_quantity),
            "cost_basis_eur": decimal_to_str(lot.cost_basis_eur),
            "requires_review": lot.requires_review,
            "review_reason": lot.review_reason,
        }
        for lot in calculator.inventory()
    ]
    return TaxReport(
        jurisdiction="PT",
        year=year,
        rows=rows,
        inventory=inventory,
        review_notes=calculator.review_notes,
    )


def _row_from_disposal(match: DisposalMatch) -> TaxReportRow:
    event = match.event
    lot = match.lot
    appendix, category, treatment, review, reason = _classify(match)
    return TaxReportRow(
        tax_year=event.timestamp.year,
        appendix=appendix,
        category=category,
        asset_type=event.asset_type.value,
        symbol=event.symbol,
        isin=event.isin,
        acquisition_date=lot.acquisition_date.date().isoformat(),
        realization_date=event.timestamp.date().isoformat(),
        quantity=match.quantity,
        proceeds_eur=match.proceeds_eur,
        cost_basis_eur=match.cost_basis_eur,
        expenses_eur=match.expenses_eur,
        gain_eur=match.gain_eur,
        holding_days=match.holding_days,
        tax_treatment=treatment,
        broker=event.broker,
        account=event.account,
        source_country=event.source_country or event.broker_country,
        requires_review=review,
        review_reason=reason,
    )


def _classify(match: DisposalMatch) -> tuple[str, str, str, bool, Optional[str]]:
    event = match.event
    security_like = (
        event.asset_type in {AssetType.EQUITY, AssetType.ETF, AssetType.DERIVATIVE}
        or event.security_token
        or match.lot.security_token
    )
    foreign = (event.source_country or event.broker_country or "").upper() not in {"", "PT", "PRT", "PORTUGAL"}
    appendix = "J" if foreign else "G"
    review = match.requires_review
    reason = match.review_reason

    if event.asset_type == AssetType.DERIVATIVE:
        return appendix, "G", PT_DERIVATIVE_REVIEW, True, _append_reason(reason, "derivative/CFD treatment requires review")

    if event.asset_type == AssetType.CRYPTO and not security_like:
        if match.holding_days >= 365:
            return "G1", "G1", PT_CRYPTO_EXEMPT_365D, review, reason
        return "G", "G", PT_CRYPTO_TAXABLE, review, reason

    return appendix, "G", PT_SECURITIES, review, reason


def _income_review_rows(events: list[LedgerEvent], year: Optional[int]) -> list[TaxReportRow]:
    rows: list[TaxReportRow] = []
    for event in events:
        if event.event_type != EventType.INCOME:
            continue
        if year is not None and event.timestamp.year != year:
            continue
        amount = event.amount_eur or Decimal("0")
        rows.append(
            TaxReportRow(
                tax_year=event.timestamp.year,
                appendix="J" if (event.source_country or event.broker_country or "").upper() not in {"", "PT", "PRT", "PORTUGAL"} else "REVIEW",
                category="REVIEW",
                asset_type=event.asset_type.value,
                symbol=event.symbol,
                isin=event.isin,
                acquisition_date=event.timestamp.date().isoformat(),
                realization_date=event.timestamp.date().isoformat(),
                quantity=event.quantity,
                proceeds_eur=amount,
                cost_basis_eur=Decimal("0"),
                expenses_eur=event.fee_eur or Decimal("0"),
                gain_eur=amount,
                holding_days=0,
                tax_treatment=PT_INCOME_REVIEW,
                broker=event.broker,
                account=event.account,
                source_country=event.source_country or event.broker_country,
                requires_review=True,
                review_reason=_append_reason(event.review_reason, "income category must be confirmed"),
            )
        )
    return rows


def _append_reason(existing: Optional[str], addition: Optional[str]) -> Optional[str]:
    if not addition:
        return existing
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing}; {addition}"
