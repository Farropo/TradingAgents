"""SQLite-backed ledger store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import sqlite3
from typing import Iterable, Optional

from tradingagents.ledger.models import LedgerEvent


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ImportSummary:
    batch_id: int
    row_count: int
    inserted_count: int
    skipped_count: int
    source_hash: str


class LedgerStore:
    """Durable local ledger.

    The store is intentionally small and dependency-free.  Decimal values are
    persisted as text so tax calculations can round only at presentation time.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS import_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT,
                    profile TEXT,
                    source_hash TEXT NOT NULL UNIQUE,
                    imported_at TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    inserted_count INTEGER NOT NULL,
                    skipped_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS decision_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    rating TEXT,
                    decision_text TEXT NOT NULL,
                    report_path TEXT,
                    state_log_path TEXT,
                    source_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ledger_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_batch_id INTEGER REFERENCES import_batches(id),
                    decision_link_id INTEGER REFERENCES decision_links(id),
                    source_hash TEXT NOT NULL UNIQUE,
                    external_id TEXT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    side TEXT,
                    transfer_direction TEXT,
                    income_type TEXT,
                    asset_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    isin TEXT,
                    quantity TEXT NOT NULL,
                    price TEXT,
                    currency TEXT NOT NULL,
                    fee TEXT NOT NULL,
                    fee_currency TEXT,
                    fx_rate_to_eur TEXT,
                    fee_fx_rate_to_eur TEXT,
                    broker TEXT,
                    account TEXT,
                    source TEXT,
                    source_row INTEGER,
                    source_country TEXT,
                    broker_country TEXT,
                    received_symbol TEXT,
                    received_asset_type TEXT,
                    received_quantity TEXT,
                    transfer_id TEXT,
                    security_token INTEGER NOT NULL DEFAULT 0,
                    requires_review INTEGER NOT NULL DEFAULT 0,
                    review_reason TEXT,
                    raw_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tax_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER REFERENCES ledger_events(id),
                    broker TEXT,
                    account TEXT,
                    asset_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    acquisition_date TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    remaining_quantity TEXT NOT NULL,
                    cost_basis_eur TEXT NOT NULL,
                    source_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ledger_events_timestamp
                    ON ledger_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_ledger_events_symbol
                    ON ledger_events(symbol);
                CREATE INDEX IF NOT EXISTS idx_ledger_events_account
                    ON ledger_events(broker, account);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

    def import_events(
        self,
        events: Iterable[LedgerEvent],
        source_path: str | Path,
        profile: str,
        source_hash: Optional[str] = None,
    ) -> ImportSummary:
        event_list = list(events)
        source_path_str = str(source_path)
        batch_hash = source_hash or self.file_hash(source_path)
        imported_at = datetime.now(timezone.utc).isoformat()

        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id, row_count, inserted_count, skipped_count FROM import_batches WHERE source_hash = ?",
                (batch_hash,),
            ).fetchone()
            if existing:
                return ImportSummary(
                    batch_id=existing["id"],
                    row_count=existing["row_count"],
                    inserted_count=0,
                    skipped_count=existing["row_count"],
                    source_hash=batch_hash,
                )

            cursor = conn.execute(
                """
                INSERT INTO import_batches(
                    source_path, profile, source_hash, imported_at,
                    row_count, inserted_count, skipped_count
                ) VALUES (?, ?, ?, ?, ?, 0, 0)
                """,
                (source_path_str, profile, batch_hash, imported_at, len(event_list)),
            )
            batch_id = int(cursor.lastrowid)
            inserted = 0
            skipped = 0
            for event in event_list:
                record = event.to_record()
                columns = [
                    "import_batch_id",
                    "decision_link_id",
                    "source_hash",
                    "external_id",
                    "timestamp",
                    "event_type",
                    "side",
                    "transfer_direction",
                    "income_type",
                    "asset_type",
                    "symbol",
                    "isin",
                    "quantity",
                    "price",
                    "currency",
                    "fee",
                    "fee_currency",
                    "fx_rate_to_eur",
                    "fee_fx_rate_to_eur",
                    "broker",
                    "account",
                    "source",
                    "source_row",
                    "source_country",
                    "broker_country",
                    "received_symbol",
                    "received_asset_type",
                    "received_quantity",
                    "transfer_id",
                    "security_token",
                    "requires_review",
                    "review_reason",
                    "raw_json",
                    "created_at",
                ]
                values = {
                    **record,
                    "import_batch_id": batch_id,
                    "created_at": imported_at,
                }
                placeholders = ", ".join("?" for _ in columns)
                try:
                    conn.execute(
                        f"INSERT INTO ledger_events({', '.join(columns)}) VALUES ({placeholders})",
                        tuple(values.get(col) for col in columns),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    skipped += 1

            conn.execute(
                """
                UPDATE import_batches
                SET inserted_count = ?, skipped_count = ?
                WHERE id = ?
                """,
                (inserted, skipped, batch_id),
            )

        return ImportSummary(
            batch_id=batch_id,
            row_count=len(event_list),
            inserted_count=inserted,
            skipped_count=skipped,
            source_hash=batch_hash,
        )

    def add_events(self, events: Iterable[LedgerEvent]) -> int:
        summary = self.import_events(
            list(events),
            source_path="<manual>",
            profile="manual",
            source_hash=datetime.now(timezone.utc).isoformat(),
        )
        return summary.inserted_count

    def list_events(
        self,
        year: Optional[int] = None,
        account: Optional[str] = None,
        broker: Optional[str] = None,
    ) -> list[LedgerEvent]:
        clauses = []
        params: list[object] = []
        if year is not None:
            clauses.append("substr(timestamp, 1, 4) = ?")
            params.append(str(year))
        if account:
            clauses.append("account = ?")
            params.append(account)
        if broker:
            clauses.append("broker = ?")
            params.append(broker)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM ledger_events {where} ORDER BY timestamp, id"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [LedgerEvent.from_record(dict(row)) for row in rows]

    def record_decision(
        self,
        ticker: str,
        trade_date: str,
        rating: str,
        decision_text: str,
        report_path: str | Path | None = None,
        state_log_path: str | Path | None = None,
    ) -> int:
        payload = "|".join([str(ticker), str(trade_date), str(rating), decision_text])
        source_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO decision_links(
                    ticker, trade_date, rating, decision_text, report_path,
                    state_log_path, source_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    str(trade_date),
                    rating,
                    decision_text,
                    str(report_path) if report_path else None,
                    str(state_log_path) if state_log_path else None,
                    source_hash,
                    created_at,
                ),
            )
            row = conn.execute(
                "SELECT id FROM decision_links WHERE source_hash = ?",
                (source_hash,),
            ).fetchone()
        return int(row["id"])

    def list_decisions(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM decision_links ORDER BY trade_date, ticker"
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def file_hash(path: str | Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
