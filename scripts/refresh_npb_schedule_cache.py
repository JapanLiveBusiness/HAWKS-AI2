#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game_calendar import HEADERS, NPB_SCHEDULE_URL, parse_npb_schedule_html  # noqa: E402


JST = ZoneInfo("Asia/Tokyo")


def month_pairs(now: datetime) -> list[tuple[int, int]]:
    pairs = [(now.year, now.month)]
    if now.month == 12:
        pairs.append((now.year + 1, 1))
    else:
        pairs.append((now.year, now.month + 1))
    return pairs


def fetch_schedule(now: datetime, timeout: int) -> dict:
    games = []
    source_urls = []
    for year, month in month_pairs(now):
        url = NPB_SCHEDULE_URL.format(year=year, month=month)
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        games.extend(parse_npb_schedule_html(response.content, year, month))
        source_urls.append(url)
    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "source_urls": source_urls,
        "games": games,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/app/data/npb_schedule_cache.json")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    payload = fetch_schedule(datetime.now(JST), args.timeout)
    if not payload["games"]:
        raise SystemExit("No NPB schedule rows were returned; existing cache was preserved.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"Saved {len(payload['games'])} games to {output}")


if __name__ == "__main__":
    main()
