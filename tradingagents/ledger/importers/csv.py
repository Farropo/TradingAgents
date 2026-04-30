"""Generic CSV importer for broker/exchange exports."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any, Iterable, Optional

from tradingagents.ledger.models import (
    AssetType,
    EventType,
    IncomeType,
    LedgerEvent,
    ONE,
    TradeSide,
    TransferDirection,
    ZERO,
    parse_decimal,
)
from tradingagents.ledger.store import ImportSummary, LedgerStore


class CsvImportError(ValueError):
    pass


@dataclass(frozen=True)
class CsvImportProfile:
    name: str = "generic"
    column_map: dict[str, list[str]] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CsvImportPreview:
    events: list[LedgerEvent]
    errors: list[str]


DEFAULT_COLUMNS: dict[str, list[str]] = {
    "external_id": ["external_id", "trade_id", "transaction_id", "id"],
    "timestamp": ["timestamp", "trade_at", "date", "datetime", "time"],
    "type": ["type", "event_type", "side", "operation"],
    "asset_type": ["asset_type", "asset_class"],
    "symbol": ["symbol", "ticker", "asset"],
    "isin": ["isin"],
    "quantity": ["quantity", "qty", "amount"],
    "price": ["price", "unit_price"],
    "currency": ["currency", "quote_currency"],
    "fee": ["fee", "commission", "fees"],
    "fee_currency": ["fee_currency", "commission_currency"],
    "fx_rate_to_eur": ["fx_rate_to_eur", "eur_fx", "fx_eur"],
    "fee_fx_rate_to_eur": ["fee_fx_rate_to_eur", "fee_fx_eur"],
    "broker": ["broker", "platform", "exchange"],
    "account": ["account", "wallet"],
    "source_country": ["source_country", "country"],
    "broker_country": ["broker_country"],
    "received_symbol": ["received_symbol", "to_symbol", "received_asset"],
    "received_asset_type": ["received_asset_type", "to_asset_type"],
    "received_quantity": ["received_quantity", "to_quantity", "received_amount"],
    "transfer_id": ["transfer_id", "withdrawal_id", "deposit_id"],
    "income_type": ["income_type", "reward_type"],
    "security_token": ["security_token", "is_security_token"],
}


TYPE_ALIASES = {
    "BUY": (EventType.TRADE, TradeSide.BUY, None, None),
    "SELL": (EventType.TRADE, TradeSide.SELL, None, None),
    "SWAP": (EventType.TRADE, TradeSide.SWAP, None, None),
    "CONVERT": (EventType.TRADE, TradeSide.SWAP, None, None),
    "TRANSFER_IN": (EventType.TRANSFER, None, TransferDirection.IN, None),
    "DEPOSIT": (EventType.TRANSFER, None, TransferDirection.IN, None),
    "TRANSFER_OUT": (EventType.TRANSFER, None, TransferDirection.OUT, None),
    "WITHDRAWAL": (EventType.TRANSFER, None, TransferDirection.OUT, None),
    "FEE": (EventType.FEE, None, None, None),
    "DIVIDEND": (EventType.INCOME, None, None, IncomeType.DIVIDEND),
    "INTEREST": (EventType.INCOME, None, None, IncomeType.INTEREST),
    "STAKING": (EventType.INCOME, None, None, IncomeType.STAKING),
    "AIRDROP": (EventType.INCOME, None, None, IncomeType.AIRDROP),
    "MINING": (EventType.INCOME, None, None, IncomeType.MINING),
    "REWARD": (EventType.INCOME, None, None, IncomeType.REWARD),
    "INCOME": (EventType.INCOME, None, None, IncomeType.OTHER),
}


def load_csv_profile(profile: str | Path | CsvImportProfile | None = None) -> CsvImportProfile:
    if isinstance(profile, CsvImportProfile):
        return profile
    if profile is None or str(profile).lower() == "generic":
        return CsvImportProfile(name="generic", column_map=DEFAULT_COLUMNS, defaults={})

    path = Path(profile).expanduser()
    if not path.exists():
        raise CsvImportError(f"CSV profile not found: {path}")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = _parse_simple_yaml(text)

    raw_map = data.get("column_map", data.get("columns", {}))
    column_map = {
        key: value if isinstance(value, list) else [str(value)]
        for key, value in raw_map.items()
    }
    merged = {**DEFAULT_COLUMNS, **column_map}
    return CsvImportProfile(
        name=data.get("name", path.stem),
        column_map=merged,
        defaults=data.get("defaults", {}),
    )


def preview_csv(path: str | Path, profile: str | Path | CsvImportProfile | None = None) -> CsvImportPreview:
    csv_path = Path(path).expanduser()
    csv_profile = load_csv_profile(profile)
    events: list[LedgerEvent] = []
    errors: list[str] = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row_number, row in enumerate(reader, start=2):
            try:
                events.append(_row_to_event(row, row_number, csv_path, csv_profile))
            except Exception as exc:
                errors.append(f"row {row_number}: {exc}")

    return CsvImportPreview(events=events, errors=errors)


def import_csv_to_store(
    path: str | Path,
    store: LedgerStore,
    profile: str | Path | CsvImportProfile | None = None,
) -> ImportSummary:
    csv_path = Path(path).expanduser()
    csv_profile = load_csv_profile(profile)
    preview = preview_csv(csv_path, csv_profile)
    if preview.errors:
        raise CsvImportError("; ".join(preview.errors))
    return store.import_events(
        preview.events,
        source_path=csv_path,
        profile=csv_profile.name,
        source_hash=LedgerStore.file_hash(csv_path),
    )


def _row_to_event(
    row: dict[str, str],
    row_number: int,
    csv_path: Path,
    profile: CsvImportProfile,
) -> LedgerEvent:
    raw_type = _required(row, profile, "type").upper().replace(" ", "_")
    if raw_type not in TYPE_ALIASES:
        raise ValueError(f"unsupported event type '{raw_type}'")

    event_type, side, direction, inferred_income = TYPE_ALIASES[raw_type]
    asset_type = AssetType((_get(row, profile, "asset_type", "OTHER") or "OTHER").upper())
    symbol = _required(row, profile, "symbol")
    currency = (_get(row, profile, "currency", "EUR") or "EUR").upper()
    quantity = parse_decimal(_get(row, profile, "quantity", "1"), ZERO)
    if quantity is None or quantity <= ZERO:
        raise ValueError("quantity must be positive")

    price = parse_decimal(_get(row, profile, "price"))
    fee = parse_decimal(_get(row, profile, "fee"), ZERO) or ZERO
    fx_rate = parse_decimal(_get(row, profile, "fx_rate_to_eur"))
    if fx_rate is None and currency == "EUR":
        fx_rate = ONE

    fee_currency = (_get(row, profile, "fee_currency", currency) or currency).upper()
    fee_fx = parse_decimal(_get(row, profile, "fee_fx_rate_to_eur"))
    if fee_fx is None and fee_currency == "EUR":
        fee_fx = ONE

    requires_review = False
    review_reasons: list[str] = []
    if event_type == EventType.TRADE and side in {TradeSide.BUY, TradeSide.SELL} and price is None:
        raise ValueError("buy/sell rows require price")
    if event_type == EventType.TRADE and currency != "EUR" and fx_rate is None:
        requires_review = True
        review_reasons.append("missing FX rate to EUR")
    if fee and fee_currency != "EUR" and fee_fx is None and fee_currency != currency:
        requires_review = True
        review_reasons.append("missing fee FX rate to EUR")

    income_type = inferred_income
    raw_income = _get(row, profile, "income_type")
    if raw_income:
        income_type = IncomeType(raw_income.upper())
    if event_type == EventType.INCOME and asset_type == AssetType.CRYPTO:
        requires_review = True
        review_reasons.append("crypto income classification requires review")

    received_symbol = _get(row, profile, "received_symbol")
    received_quantity = parse_decimal(_get(row, profile, "received_quantity"))
    received_asset_type_raw = _get(row, profile, "received_asset_type")
    received_asset_type = (
        AssetType(received_asset_type_raw.upper())
        if received_asset_type_raw
        else asset_type
    )

    security_token = _parse_bool(_get(row, profile, "security_token", False))

    return LedgerEvent(
        timestamp=_required(row, profile, "timestamp"),
        event_type=event_type,
        side=side,
        transfer_direction=direction,
        income_type=income_type,
        asset_type=asset_type,
        symbol=symbol,
        isin=_get(row, profile, "isin"),
        quantity=quantity,
        price=price,
        currency=currency,
        fee=fee,
        fee_currency=fee_currency,
        fx_rate_to_eur=fx_rate,
        fee_fx_rate_to_eur=fee_fx,
        broker=_get(row, profile, "broker"),
        account=_get(row, profile, "account"),
        external_id=_get(row, profile, "external_id"),
        source=str(csv_path),
        source_row=row_number,
        source_country=_get(row, profile, "source_country"),
        broker_country=_get(row, profile, "broker_country"),
        received_symbol=received_symbol,
        received_asset_type=received_asset_type,
        received_quantity=received_quantity,
        transfer_id=_get(row, profile, "transfer_id"),
        security_token=security_token,
        requires_review=requires_review,
        review_reason="; ".join(review_reasons) if review_reasons else None,
        raw_data=dict(row),
    )


def _get(
    row: dict[str, str],
    profile: CsvImportProfile,
    field_name: str,
    default: Any = None,
) -> Any:
    for candidate in profile.column_map.get(field_name, [field_name]):
        if candidate in row and row[candidate] not in (None, ""):
            return row[candidate]
    return profile.defaults.get(field_name, default)


def _required(row: dict[str, str], profile: CsvImportProfile, field_name: str) -> str:
    value = _get(row, profile, field_name)
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    return str(value).strip()


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "sim"}


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the tiny YAML subset needed for column profiles.

    This avoids adding PyYAML as a dependency. Supported shape:
    ``name: x``, then ``column_map:``/``defaults:`` with indented
    ``key: value`` pairs.
    """
    data: dict[str, Any] = {}
    current: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current = line[:-1].strip()
            data[current] = {}
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if current and raw_line.startswith((" ", "\t")):
            data.setdefault(current, {})[key] = [v.strip() for v in value.split(",")] if "," in value else value
        else:
            data[key] = value
            current = None
    return data
