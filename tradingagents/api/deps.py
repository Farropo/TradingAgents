"""FastAPI dependency helpers."""

from __future__ import annotations

from pathlib import Path
import os
from typing import Any

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.ledger.store import LedgerStore


def get_config() -> dict[str, Any]:
    return DEFAULT_CONFIG.copy()


def get_ledger_store() -> LedgerStore:
    return LedgerStore(get_config()["ledger_db_path"])


def get_upload_dir() -> Path:
    root = Path(get_config().get("codex_assisted_dir", Path.home() / ".tradingagents"))
    upload_dir = root.parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def env_status() -> dict[str, bool]:
    keys = (
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "XAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "DASHSCOPE_API_KEY",
        "ZHIPU_API_KEY",
        "OPENROUTER_API_KEY",
        "AZURE_OPENAI_API_KEY",
    )
    return {key: bool(os.environ.get(key)) for key in keys}
