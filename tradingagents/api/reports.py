"""Local report discovery."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib

from tradingagents.default_config import DEFAULT_CONFIG


def list_reports() -> list[dict]:
    roots = [
        ("results", Path(DEFAULT_CONFIG["results_dir"]).expanduser()),
        ("codex", Path(DEFAULT_CONFIG["codex_assisted_dir"]).expanduser()),
    ]
    reports: list[dict] = []
    for source, root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if path.name.lower() not in {"complete_report.md", "codex_response.md"}:
                continue
            reports.append(_summary(path, source))
    return sorted(reports, key=lambda item: item["modified_at"], reverse=True)


def get_report(report_id: str) -> dict | None:
    for summary in list_reports():
        if summary["report_id"] == report_id:
            path = Path(summary["path"])
            return {**summary, "content": path.read_text(encoding="utf-8")}
    return None


def _summary(path: Path, source: str) -> dict:
    stat = path.stat()
    report_id = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    return {
        "report_id": report_id,
        "title": path.parent.name if path.name == "complete_report.md" else path.name,
        "path": str(path.resolve()),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "source": source,
    }
