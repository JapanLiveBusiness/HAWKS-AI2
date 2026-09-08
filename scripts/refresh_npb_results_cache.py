#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game_calendar import (  # noqa: E402
    attach_handicaps,
    fetch_daily_handicaps,
    fetch_npb_schedule_day,
    merge_game_sources,
)


JST = ZoneInfo("Asia/Tokyo")


def load_existing(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"games": []}
    except Exception:
        return {"games": []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/app/data/npb_results_cache.json")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()

    output = Path(args.output)
    existing = load_existing(output)
    rows = list(existing.get("games") or [])
    today = datetime.now(JST).date()
    refreshed_dates = []

    for offset in range(1, max(args.days, 1) + 1):
        target_date = today - timedelta(days=offset)
        official = fetch_npb_schedule_day(target_date, timeout=args.timeout)
        handicaps = fetch_daily_handicaps(target_date, timeout=args.timeout)
        fetched = attach_handicaps(
            merge_game_sources(official, handicaps),
            handicaps,
        )
        if not fetched:
            continue
        target_iso = target_date.isoformat()
        rows = [row for row in rows if str(row.get("date") or "") != target_iso]
        rows.extend(fetched)
        refreshed_dates.append(target_iso)

    if not refreshed_dates:
        raise SystemExit("No daily result rows were returned; existing cache was preserved.")

    rows.sort(key=lambda row: (str(row.get("date") or ""), str(row.get("home") or "")))
    payload = {
        "updated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "refreshed_dates": refreshed_dates,
        "games": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"Saved {len(rows)} result rows to {output}")


if __name__ == "__main__":
    main()
