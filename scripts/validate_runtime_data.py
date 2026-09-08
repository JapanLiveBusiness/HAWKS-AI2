#!/usr/bin/env python3
"""Validate the live data mounted into the production container."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing data file: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid data file: {path}: {exc}") from exc


def newest_daily(filename: str, directories: list[Path], today_iso: str) -> tuple[Path, dict]:
    candidates: list[tuple[str, int, Path, dict]] = []
    for priority, directory in enumerate(directories):
        path = directory / filename
        if not path.exists():
            continue
        payload = read_json(path)
        if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
            raise ValueError(f"{path} must contain an object with a games list")
        payload_date = str(payload.get("date") or "")
        if payload_date >= today_iso:
            candidates.append((payload_date, -priority, path, payload))
    if not candidates:
        locations = ", ".join(str(directory / filename) for directory in directories)
        raise ValueError(f"no current data for {filename}; checked {locations}")
    _, _, path, payload = max(candidates, key=lambda item: (item[0], item[1]))
    return path, payload


def validate(data_dir: Path, shared_data_dir: Path, today_iso: str) -> list[str]:
    directories = [directory for directory in (shared_data_dir, data_dir) if directory.is_dir()]
    if not directories:
        raise ValueError("neither the shared nor production data directory is mounted")

    messages: list[str] = []
    schedule_path, schedule = newest_daily("npb_today.json", directories, today_iso)
    prediction_path, predictions = newest_daily("today_ai_predictions.json", directories, today_iso)
    if str(schedule.get("date")) != str(predictions.get("date")):
        raise ValueError(
            "schedule and prediction dates differ: "
            f"{schedule.get('date')} != {predictions.get('date')}"
        )
    messages.append(
        f"schedule: {schedule_path} date={schedule.get('date')} games={len(schedule['games'])}"
    )
    messages.append(
        f"predictions: {prediction_path} date={predictions.get('date')} games={len(predictions['games'])}"
    )

    bet_path = data_dir / "bet_records.json"
    bets = read_json(bet_path)
    if not isinstance(bets, list):
        raise ValueError(f"{bet_path} must contain a list")
    messages.append(f"bets: {bet_path} records={len(bets)}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data"))
    parser.add_argument("--shared-data-dir", type=Path, default=Path("/app/shared-data"))
    parser.add_argument("--today", default=datetime.now(JST).date().isoformat())
    args = parser.parse_args()
    try:
        messages = validate(args.data_dir, args.shared_data_dir, args.today)
    except ValueError as exc:
        print(f"[data-check] ERROR: {exc}")
        return 1
    for message in messages:
        print(f"[data-check] {message}")
    print("[data-check] production page data is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
