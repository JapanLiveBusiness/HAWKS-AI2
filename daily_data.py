"""Select the current daily schedule and prediction payloads safely."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
ROOT = Path(__file__).resolve().parent


def daily_data_dirs() -> tuple[Path, ...]:
    """Return daily-data locations in preferred order for equal dates."""
    shared = Path(os.getenv("AI_BASEBALL_SHARED_DATA_DIR", "/app/shared-data"))
    return shared, Path("/app/data"), ROOT / "data"


def load_current_daily_json(
    filename: str,
    fallback: Any,
    *,
    today: date | None = None,
    directories: Iterable[Path] | None = None,
) -> Any:
    """Load the newest current-or-future dated payload, never a past slate."""
    today_iso = (today or datetime.now(JST).date()).isoformat()
    candidates: list[tuple[str, int, dict[str, Any]]] = []
    source_dirs = tuple(directories) if directories is not None else daily_data_dirs()

    for priority, directory in enumerate(source_dirs):
        path = directory / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        payload_date = str(payload.get("date") or "")
        if payload_date >= today_iso:
            candidates.append((payload_date, -priority, payload))

    if not candidates:
        return fallback
    return max(candidates, key=lambda item: (item[0], item[1]))[2]
