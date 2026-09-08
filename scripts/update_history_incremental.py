#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handenomori_client import fetch_member_page

JST = ZoneInfo("Asia/Tokyo")

BASE_URL = "https://handenomori.com/jpb/{:%Y%m%d}/"

TEAMS = {
    "ソフトバンク",
    "楽天",
    "西武",
    "日本ハム",
    "オリックス",
    "ロッテ",
    "巨人",
    "阪神",
    "DeNA",
    "広島",
    "ヤクルト",
    "中日",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/151 Safari/537.36"
    )
}


def clean(value):
    return re.sub(r"\s+", " ", str(value)).strip()


def fetch_day(target_date):
    url = BASE_URL.format(target_date)

    try:
        html = fetch_member_page(url, timeout=15)
    except Exception:
        print("FETCH ERROR", target_date, "authenticated source unavailable")
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    lines = [
        clean(x)
        for x in soup.get_text(
            "\n",
            strip=True,
        ).splitlines()
        if clean(x)
    ]

    games = []

    for i in range(1, len(lines) - 4):
        home = lines[i]

        if home not in TEAMS:
            continue

        if not lines[i + 1].isdigit():
            continue

        if lines[i + 2] != "-":
            continue

        if not lines[i + 3].isdigit():
            continue

        away = lines[i + 4]

        if away not in TEAMS:
            continue

        venue = lines[i - 1]

        games.append(
            {
                "date": target_date.isoformat(),
                "home": home,
                "away": away,
                "home_score": int(lines[i + 1]),
                "away_score": int(lines[i + 3]),
                "venue": venue,
                "source_url": url,
                "season": target_date.year,
            }
        )

    # ページ内重複除去
    unique = {}

    for game in games:
        key = (
            game["date"],
            game["home"],
            game["away"],
        )
        unique[key] = game

    return list(unique.values())


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--history",
        default="/app/data/historical_games_2017_2026.json",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
    )

    args = parser.parse_args()

    path = Path(args.history)

    rows = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(rows, list):
        raise SystemExit("ERROR: history must be a list")

    existing = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        key = (
            str(row.get("date") or ""),
            str(row.get("home") or ""),
            str(row.get("away") or ""),
        )

        if all(key):
            existing[key] = row

    dates = [
        date.fromisoformat(str(row["date"]))
        for row in rows
        if row.get("date")
    ]

    if not dates:
        raise SystemExit("ERROR: history has no dates")

    latest = max(dates)

    # 予測リーク防止:
    # 当日試合は絶対に学習履歴へ追加しない。
    yesterday = (
        datetime.now(JST).date()
        - timedelta(days=1)
    )

    print("HISTORY LATEST:", latest)
    print("UPDATE THROUGH:", yesterday)

    if latest >= yesterday:
        print("HISTORY ALREADY CURRENT")
        return

    current = latest + timedelta(days=1)

    added = 0
    checked = 0

    while current <= yesterday:
        checked += 1

        games = fetch_day(current)

        print(
            current,
            "games=",
            len(games),
        )

        for game in games:
            key = (
                game["date"],
                game["home"],
                game["away"],
            )

            if key not in existing:
                added += 1

            existing[key] = game

        current += timedelta(days=1)

        if args.sleep > 0:
            time.sleep(args.sleep)

    merged = sorted(
        existing.values(),
        key=lambda x: (
            str(x.get("date") or ""),
            str(x.get("home") or ""),
            str(x.get("away") or ""),
        ),
    )

    temp = path.with_suffix(
        path.suffix + ".tmp"
    )

    temp.write_text(
        json.dumps(
            merged,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # 書き込み前最終検証
    verify = json.loads(
        temp.read_text(encoding="utf-8")
    )

    max_date = max(
        str(x.get("date") or "")
        for x in verify
    )

    if max_date > yesterday.isoformat():
        raise SystemExit(
            "ERROR: current-day/future data detected"
        )

    temp.replace(path)

    print("CHECKED DAYS:", checked)
    print("ADDED GAMES:", added)
    print("TOTAL GAMES:", len(merged))
    print("MAX DATE:", max_date)
    print("OUTPUT:", path)


if __name__ == "__main__":
    main()
