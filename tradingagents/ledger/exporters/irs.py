"""IRS-support exports for the Portugal ledger report."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tradingagents.ledger.tax.pt import TaxReport


def export_irs_csv(report: TaxReport, path: str | Path) -> Path:
    output = Path(path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = report.as_dicts()
    fieldnames = list(rows[0].keys()) if rows else [
        "tax_year",
        "appendix",
        "category",
        "asset_type",
        "symbol",
        "isin",
        "acquisition_date",
        "realization_date",
        "quantity",
        "proceeds_eur",
        "cost_basis_eur",
        "expenses_eur",
        "gain_eur",
        "holding_days",
        "tax_treatment",
        "broker",
        "account",
        "source_country",
        "requires_review",
        "review_reason",
    ]
    with open(output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output


def export_irs_json(report: TaxReport, path: str | Path) -> Path:
    output = Path(path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "jurisdiction": report.jurisdiction,
        "year": report.year,
        "rows": report.as_dicts(),
        "totals_by_treatment": report.totals_by_treatment(),
        "inventory": report.inventory,
        "review_notes": report.review_notes,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output
