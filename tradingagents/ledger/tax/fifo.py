"""FIFO lot matching for ledger events."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Deque, Iterable, Optional

from tradingagents.ledger.models import (
    AssetType,
    EventType,
    LedgerEvent,
    TradeSide,
    TransferDirection,
    ZERO,
)


class FifoCalculationError(ValueError):
    pass


class InsufficientHoldingsError(FifoCalculationError):
    pass


@dataclass(frozen=True)
class TaxLot:
    broker: Optional[str]
    account: Optional[str]
    asset_type: AssetType
    symbol: str
    acquisition_date: datetime
    quantity: Decimal
    remaining_quantity: Decimal
    cost_basis_eur: Decimal
    source_hash: str
    security_token: bool = False
    requires_review: bool = False
    review_reason: Optional[str] = None

    @property
    def cost_per_unit(self) -> Decimal:
        if self.remaining_quantity == ZERO:
            return ZERO
        return self.cost_basis_eur / self.remaining_quantity


@dataclass(frozen=True)
class DisposalMatch:
    event: LedgerEvent
    lot: TaxLot
    quantity: Decimal
    proceeds_eur: Decimal
    cost_basis_eur: Decimal
    expenses_eur: Decimal
    requires_review: bool = False
    review_reason: Optional[str] = None

    @property
    def gain_eur(self) -> Decimal:
        return self.proceeds_eur - self.cost_basis_eur

    @property
    def holding_days(self) -> int:
        return (self.event.timestamp.date() - self.lot.acquisition_date.date()).days


class FifoCalculator:
    def __init__(self) -> None:
        self._lots: dict[tuple[str, str, str, str], Deque[TaxLot]] = defaultdict(deque)
        self._pending_transfers: dict[tuple[str, str], Deque[TaxLot]] = defaultdict(deque)
        self.disposals: list[DisposalMatch] = []
        self.review_notes: list[str] = []

    def process_all(self, events: Iterable[LedgerEvent]) -> list[DisposalMatch]:
        for event in sorted(events, key=lambda e: (e.timestamp, e.source_row or 0, e.source_hash or "")):
            self.process(event)
        return list(self.disposals)

    def process(self, event: LedgerEvent) -> None:
        if event.event_type == EventType.TRADE:
            if event.side == TradeSide.BUY:
                self._add_buy_lot(event)
            elif event.side == TradeSide.SELL:
                self._add_sale_disposals(event)
            elif event.side == TradeSide.SWAP:
                self._process_swap(event)
        elif event.event_type == EventType.TRANSFER:
            self._process_transfer(event)
        elif event.event_type == EventType.INCOME:
            self._add_income_lot(event)
        elif event.event_type == EventType.FEE:
            self.review_notes.append(f"standalone fee requires review: {event.source_hash}")

    def inventory(self) -> list[TaxLot]:
        lots: list[TaxLot] = []
        for queue in self._lots.values():
            lots.extend(lot for lot in queue if lot.remaining_quantity > ZERO)
        return lots

    def _add_buy_lot(self, event: LedgerEvent) -> None:
        amount = event.amount_eur
        fee = event.fee_eur
        requires_review = event.requires_review or amount is None or fee is None
        reason = event.review_reason
        if amount is None:
            reason = _append_reason(reason, "missing EUR acquisition value")
        if fee is None:
            reason = _append_reason(reason, "missing EUR fee value")
        cost_basis = (amount or ZERO) + (fee or ZERO)
        self._push_lot(self._event_lot(event, event.quantity, cost_basis, requires_review, reason))

    def _add_income_lot(self, event: LedgerEvent) -> None:
        requires_review = True if event.asset_type == AssetType.CRYPTO else event.requires_review
        reason = event.review_reason
        if event.asset_type == AssetType.CRYPTO:
            reason = _append_reason(reason, "crypto income lot has zero cost basis until reviewed")
        self._push_lot(self._event_lot(event, event.quantity, ZERO, requires_review, reason))

    def _add_sale_disposals(self, event: LedgerEvent) -> None:
        matches = self._consume_lots(event, event.quantity)
        gross = event.amount_eur
        fee = event.fee_eur
        requires_review = event.requires_review or gross is None or fee is None
        reason = event.review_reason
        if gross is None:
            reason = _append_reason(reason, "missing EUR realization value")
        if fee is None:
            reason = _append_reason(reason, "missing EUR fee value")
        gross = gross or ZERO
        fee = fee or ZERO

        for lot, qty, cost_basis in matches:
            ratio = qty / event.quantity
            expenses = fee * ratio
            proceeds = (gross * ratio) - expenses
            self.disposals.append(
                DisposalMatch(
                    event=event,
                    lot=lot,
                    quantity=qty,
                    proceeds_eur=proceeds,
                    cost_basis_eur=cost_basis,
                    expenses_eur=expenses,
                    requires_review=requires_review or lot.requires_review,
                    review_reason=_append_reason(reason, lot.review_reason),
                )
            )

    def _process_swap(self, event: LedgerEvent) -> None:
        matches = self._consume_lots(event, event.quantity)
        fee = event.fee_eur
        fee = fee or ZERO

        crypto_to_crypto = (
            event.asset_type == AssetType.CRYPTO
            and event.received_asset_type == AssetType.CRYPTO
            and not event.security_token
        )

        if not crypto_to_crypto:
            gross = event.amount_eur or ZERO
            fee = event.fee_eur or ZERO
            for lot, qty, cost_basis in matches:
                ratio = qty / event.quantity
                expenses = fee * ratio
                proceeds = (gross * ratio) - expenses
                self.disposals.append(
                    DisposalMatch(
                        event=event,
                        lot=lot,
                        quantity=qty,
                        proceeds_eur=proceeds,
                        cost_basis_eur=cost_basis,
                        expenses_eur=expenses,
                        requires_review=True,
                        review_reason=_append_reason(
                            event.review_reason,
                            "non-crypto swap requires manual tax review",
                        ),
                    )
                )
            if event.received_symbol and event.received_quantity:
                self._push_lot(
                    TaxLot(
                        broker=event.broker,
                        account=event.account,
                        asset_type=event.received_asset_type or event.asset_type,
                        symbol=event.received_symbol.upper(),
                        acquisition_date=event.timestamp,
                        quantity=event.received_quantity,
                        remaining_quantity=event.received_quantity,
                        cost_basis_eur=gross,
                        source_hash=f"{event.source_hash}:swap-received",
                        security_token=event.security_token,
                        requires_review=True,
                        review_reason="non-crypto swap acquisition basis requires review",
                    )
                )
            return

        received_total = event.received_quantity or ZERO
        if received_total <= ZERO:
            raise FifoCalculationError("swap requires positive received quantity")

        for lot, qty, cost_basis in matches:
            ratio = qty / event.quantity
            received_qty = received_total * ratio
            inherited_cost = cost_basis + (fee * ratio)
            new_lot = TaxLot(
                broker=event.broker,
                account=event.account,
                asset_type=event.received_asset_type or event.asset_type,
                symbol=(event.received_symbol or event.symbol).upper(),
                acquisition_date=lot.acquisition_date,
                quantity=received_qty,
                remaining_quantity=received_qty,
                cost_basis_eur=inherited_cost,
                source_hash=f"{event.source_hash}:{lot.source_hash}:swap",
                security_token=event.security_token,
                requires_review=event.requires_review or lot.requires_review,
                review_reason=_append_reason(event.review_reason, lot.review_reason),
            )
            self._push_lot(new_lot)

    def _process_transfer(self, event: LedgerEvent) -> None:
        if event.transfer_direction == TransferDirection.OUT:
            matches = self._consume_lots(event, event.quantity)
            transfer_key = self._transfer_key(event)
            for lot, qty, cost_basis in matches:
                self._pending_transfers[transfer_key].append(
                    replace(
                        lot,
                        quantity=qty,
                        remaining_quantity=qty,
                        cost_basis_eur=cost_basis,
                        source_hash=f"{event.source_hash}:{lot.source_hash}:transfer",
                    )
                )
        elif event.transfer_direction == TransferDirection.IN:
            transfer_key = self._transfer_key(event)
            remaining = event.quantity
            while remaining > ZERO and self._pending_transfers[transfer_key]:
                lot = self._pending_transfers[transfer_key].popleft()
                qty = min(remaining, lot.remaining_quantity)
                ratio = qty / lot.remaining_quantity
                self._push_lot(
                    replace(
                        lot,
                        broker=event.broker,
                        account=event.account,
                        quantity=qty,
                        remaining_quantity=qty,
                        cost_basis_eur=lot.cost_basis_eur * ratio,
                        source_hash=f"{event.source_hash}:{lot.source_hash}:received",
                    )
                )
                remainder = lot.remaining_quantity - qty
                if remainder > ZERO:
                    self._pending_transfers[transfer_key].appendleft(
                        replace(
                            lot,
                            quantity=remainder,
                            remaining_quantity=remainder,
                            cost_basis_eur=lot.cost_basis_eur * (remainder / lot.remaining_quantity),
                        )
                    )
                remaining -= qty
            if remaining > ZERO:
                reason = _append_reason(event.review_reason, "incoming transfer without matched outgoing lot")
                self._push_lot(self._event_lot(event, remaining, ZERO, True, reason))

    def _consume_lots(
        self, event: LedgerEvent, quantity: Decimal
    ) -> list[tuple[TaxLot, Decimal, Decimal]]:
        key = self._key(event.broker, event.account, event.asset_type, event.symbol)
        queue = self._lots[key]
        remaining = quantity
        matches: list[tuple[TaxLot, Decimal, Decimal]] = []

        while remaining > ZERO and queue:
            lot = queue.popleft()
            qty = min(remaining, lot.remaining_quantity)
            ratio = qty / lot.remaining_quantity
            cost_basis = lot.cost_basis_eur * ratio
            matches.append((lot, qty, cost_basis))

            remainder = lot.remaining_quantity - qty
            if remainder > ZERO:
                queue.appendleft(
                    replace(
                        lot,
                        remaining_quantity=remainder,
                        cost_basis_eur=lot.cost_basis_eur - cost_basis,
                    )
                )
            remaining -= qty

        if remaining > ZERO:
            raise InsufficientHoldingsError(
                f"not enough holdings for {event.symbol}: missing {remaining}"
            )
        return matches

    def _push_lot(self, lot: TaxLot) -> None:
        self._lots[self._key(lot.broker, lot.account, lot.asset_type, lot.symbol)].append(lot)

    def _event_lot(
        self,
        event: LedgerEvent,
        quantity: Decimal,
        cost_basis: Decimal,
        requires_review: bool,
        reason: Optional[str],
    ) -> TaxLot:
        return TaxLot(
            broker=event.broker,
            account=event.account,
            asset_type=event.asset_type,
            symbol=event.symbol,
            acquisition_date=event.timestamp,
            quantity=quantity,
            remaining_quantity=quantity,
            cost_basis_eur=cost_basis,
            source_hash=event.source_hash or "",
            security_token=event.security_token,
            requires_review=requires_review,
            review_reason=reason,
        )

    @staticmethod
    def _key(
        broker: Optional[str],
        account: Optional[str],
        asset_type: AssetType,
        symbol: str,
    ) -> tuple[str, str, str, str]:
        return (broker or "", account or "", asset_type.value, symbol.upper())

    @staticmethod
    def _transfer_key(event: LedgerEvent) -> tuple[str, str]:
        return (event.transfer_id or "", f"{event.asset_type.value}:{event.symbol.upper()}")


def _append_reason(existing: Optional[str], addition: Optional[str]) -> Optional[str]:
    if not addition:
        return existing
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing}; {addition}"
