from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


REPORT_ROOT = Path("reports/local_test")


def read_json(path: str | Path, default: dict | None = None) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return default or {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def read_csv(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if limit is not None:
        return rows[-limit:]
    return rows


def latest_dashboard_data(report_root: str | Path | None = None) -> dict:
    root = Path(report_root) if report_root is not None else REPORT_ROOT
    summary = read_json(root / "summary.json")
    aggregate = read_json(REPORT_ROOT / "batch" / "aggregate.json")
    if root != REPORT_ROOT:
        aggregate = read_json(root / "batch" / "aggregate.json")
    trades = read_csv(root / "trades.csv", limit=100)
    signals = read_csv(root / "signals.csv", limit=100)
    equity = read_csv(root / "equity_curve.csv", limit=400)
    runs = read_csv(REPORT_ROOT / "batch" / "runs.csv")
    return {
        "summary": summary,
        "aggregate": aggregate,
        "trades": trades,
        "signals": signals,
        "equity": equity,
        "runs": runs,
    }
