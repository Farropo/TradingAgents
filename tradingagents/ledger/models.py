"""Normalized ledger models.

The ledger deliberately stores canonical transaction facts rather than
broker-specific report shapes.  Importers map source rows into these models;
tax/reporting code then works against one stable contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any, Optional


ZERO = Decimal("0")
ONE = Decimal("1")


class AssetType(str, Enum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    CASH = "CASH"
    DERIVATIVE = "DERIVATIVE"
    OTHER = "OTHER"


class EventType(str, Enum):
    TRADE = "TRADE"
    TRANSFER = "TRANSFER"
    INCOME = "INCOME"
    FEE = "FEE"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    SWAP = "SWAP"


class TransferDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"


class IncomeType(str, Enum):
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    STAKING = "STAKING"
    AIRDROP = "AIRDROP"
    MINING = "MINING"
    REWARD = "REWARD"
    OTHER = "OTHER"


def decimal_to_str(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return format(value, "f")


def parse_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Parse common broker CSV decimal formats into Decimal.

    Supports plain decimals, European decimal comma, and common thousands
    separators. Empty values return ``default``.
    """
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip()
    if not text:
        return default
    text = text.replace("\u00a0", "").replace(" ", "")

    if "," in text and "." in text:
        # Last separator is assumed to be the decimal separator.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    return Decimal(text)


def normalize_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("timestamp is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def enum_value(value: Optional[Enum | str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    return str(value)


def coerce_enum(enum_cls, value: Any, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, enum_cls):
        return value
    text = str(value).strip().upper()
    try:
        return enum_cls(text)
    except ValueError:
        for item in enum_cls:
            if item.value.upper() == text or item.name.upper() == text:
                return item
        raise


@dataclass(frozen=True)
class LedgerEvent:
    """One normalized financial event.

    For trades, ``symbol``/``quantity`` represent the asset being bought,
    sold, or swapped away.  For swaps, ``received_symbol`` and
    ``received_quantity`` describe the acquired asset.
    """

    timestamp: datetime
    event_type: EventType
    asset_type: AssetType
    symbol: str
    quantity: Decimal
    side: Optional[TradeSide] = None
    transfer_direction: Optional[TransferDirection] = None
    income_type: Optional[IncomeType] = None
    price: Optional[Decimal] = None
    currency: str = "EUR"
    fee: Decimal = ZERO
    fee_currency: Optional[str] = None
    fx_rate_to_eur: Optional[Decimal] = ONE
    fee_fx_rate_to_eur: Optional[Decimal] = None
    isin: Optional[str] = None
    broker: Optional[str] = None
    account: Optional[str] = None
    external_id: Optional[str] = None
    source: Optional[str] = None
    source_row: Optional[int] = None
    source_hash: Optional[str] = None
    source_country: Optional[str] = None
    broker_country: Optional[str] = None
    received_symbol: Optional[str] = None
    received_asset_type: Optional[AssetType] = None
    received_quantity: Optional[Decimal] = None
    transfer_id: Optional[str] = None
    decision_link_id: Optional[int] = None
    security_token: bool = False
    requires_review: bool = False
    review_reason: Optional[str] = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", normalize_datetime(self.timestamp))
        object.__setattr__(self, "event_type", coerce_enum(EventType, self.event_type))
        object.__setattr__(self, "asset_type", coerce_enum(AssetType, self.asset_type))
        object.__setattr__(self, "side", coerce_enum(TradeSide, self.side))
        object.__setattr__(
            self,
            "transfer_direction",
            coerce_enum(TransferDirection, self.transfer_direction),
        )
        object.__setattr__(self, "income_type", coerce_enum(IncomeType, self.income_type))
        object.__setattr__(
            self,
            "received_asset_type",
            coerce_enum(AssetType, self.received_asset_type, self.asset_type),
        )
        object.__setattr__(self, "symbol", self.symbol.upper().strip())
        object.__setattr__(self, "currency", (self.currency or "EUR").upper().strip())
        object.__setattr__(
            self,
            "fee_currency",
            (self.fee_currency or self.currency or "EUR").upper().strip(),
        )

        for name in (
            "quantity",
            "price",
            "fee",
            "fx_rate_to_eur",
            "fee_fx_rate_to_eur",
            "received_quantity",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Decimal):
                object.__setattr__(self, name, parse_decimal(value))

        if self.quantity <= ZERO:
            raise ValueError("quantity must be positive")
        if self.fee < ZERO:
            raise ValueError("fee must not be negative")
        if self.side == TradeSide.SWAP and (
            not self.received_symbol or not self.received_quantity
        ):
            raise ValueError("swap events require received_symbol and received_quantity")

        if not self.source_hash:
            object.__setattr__(self, "source_hash", self.compute_source_hash())

    @property
    def amount_eur(self) -> Optional[Decimal]:
        if self.price is None:
            return None
        if self.currency != "EUR" and self.fx_rate_to_eur is None:
            return None
        return self.quantity * self.price * (self.fx_rate_to_eur or ONE)

    @property
    def fee_eur(self) -> Optional[Decimal]:
        if self.fee == ZERO:
            return ZERO
        rate = self.fee_fx_rate_to_eur
        if rate is None:
            if self.fee_currency == self.currency:
                rate = self.fx_rate_to_eur
            elif self.fee_currency == "EUR":
                rate = ONE
            else:
                return None
        return self.fee * (rate or ONE)

    def compute_source_hash(self) -> str:
        if self.external_id:
            payload = {
                "account": self.account,
                "broker": self.broker,
                "external_id": self.external_id,
                "source": self.source,
            }
        else:
            payload = self.to_record(include_hash=False, include_raw=False)
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def to_record(self, include_hash: bool = True, include_raw: bool = True) -> dict[str, Any]:
        record: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "asset_type": self.asset_type.value,
            "symbol": self.symbol,
            "quantity": decimal_to_str(self.quantity),
            "side": enum_value(self.side),
            "transfer_direction": enum_value(self.transfer_direction),
            "income_type": enum_value(self.income_type),
            "price": decimal_to_str(self.price),
            "currency": self.currency,
            "fee": decimal_to_str(self.fee),
            "fee_currency": self.fee_currency,
            "fx_rate_to_eur": decimal_to_str(self.fx_rate_to_eur),
            "fee_fx_rate_to_eur": decimal_to_str(self.fee_fx_rate_to_eur),
            "isin": self.isin,
            "broker": self.broker,
            "account": self.account,
            "external_id": self.external_id,
            "source": self.source,
            "source_row": self.source_row,
            "source_country": self.source_country,
            "broker_country": self.broker_country,
            "received_symbol": self.received_symbol.upper() if self.received_symbol else None,
            "received_asset_type": enum_value(self.received_asset_type),
            "received_quantity": decimal_to_str(self.received_quantity),
            "transfer_id": self.transfer_id,
            "decision_link_id": self.decision_link_id,
            "security_token": int(self.security_token),
            "requires_review": int(self.requires_review),
            "review_reason": self.review_reason,
        }
        if include_hash:
            record["source_hash"] = self.source_hash
        if include_raw:
            record["raw_json"] = json.dumps(self.raw_data, sort_keys=True, ensure_ascii=False)
        return record

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> "LedgerEvent":
        raw_json = row.get("raw_json")
        raw_data = json.loads(raw_json) if raw_json else {}
        return cls(
            timestamp=row["timestamp"],
            event_type=row["event_type"],
            asset_type=row["asset_type"],
            symbol=row["symbol"],
            quantity=parse_decimal(row["quantity"], ZERO),
            side=row.get("side"),
            transfer_direction=row.get("transfer_direction"),
            income_type=row.get("income_type"),
            price=parse_decimal(row.get("price")),
            currency=row.get("currency") or "EUR",
            fee=parse_decimal(row.get("fee"), ZERO) or ZERO,
            fee_currency=row.get("fee_currency"),
            fx_rate_to_eur=parse_decimal(row.get("fx_rate_to_eur"), ONE),
            fee_fx_rate_to_eur=parse_decimal(row.get("fee_fx_rate_to_eur")),
            isin=row.get("isin"),
            broker=row.get("broker"),
            account=row.get("account"),
            external_id=row.get("external_id"),
            source=row.get("source"),
            source_row=row.get("source_row"),
            source_hash=row.get("source_hash"),
            source_country=row.get("source_country"),
            broker_country=row.get("broker_country"),
            received_symbol=row.get("received_symbol"),
            received_asset_type=row.get("received_asset_type"),
            received_quantity=parse_decimal(row.get("received_quantity")),
            transfer_id=row.get("transfer_id"),
            decision_link_id=row.get("decision_link_id"),
            security_token=bool(row.get("security_token")),
            requires_review=bool(row.get("requires_review")),
            review_reason=row.get("review_reason"),
            raw_data=raw_data,
        )
