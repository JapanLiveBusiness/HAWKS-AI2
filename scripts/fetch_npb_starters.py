#!/usr/bin/env python3
"""Fetch the current official NPB probable starters without importing Streamlit."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


JST = ZoneInfo("Asia/Tokyo")
SOURCE_URL = "https://npb.jp/announcement/starter/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; HAWKS-AI/1.0)"}
TEAM_ALIASES = {
    "ソフトバンク": ("福岡ソフトバンクホークス", "福岡ソフトバンク", "ソフトバンク"),
    "日本ハム": ("北海道日本ハムファイターズ", "北海道日本ハム", "日本ハム"),
    "オリックス": ("オリックス・バファローズ", "オリックス"),
    "ロッテ": ("千葉ロッテマリーンズ", "千葉ロッテ", "ロッテ"),
    "楽天": ("東北楽天ゴールデンイーグルス", "東北楽天", "楽天"),
    "西武": ("埼玉西武ライオンズ", "埼玉西武", "西武"),
    "巨人": ("読売ジャイアンツ", "巨人"),
    "ヤクルト": ("東京ヤクルトスワローズ", "東京ヤクルト", "ヤクルト"),
    "DeNA": ("横浜DeNAベイスターズ", "横浜DeNA", "DeNA"),
    "中日": ("中日ドラゴンズ", "中日"),
    "阪神": ("阪神タイガース", "阪神"),
    "広島": ("広島東洋カープ", "広島"),
}


def _team_in_node(node) -> str | None:
    text = node.get_text(" ", strip=True)
    image_text = " ".join(
        str(image.get("alt") or image.get("title") or "")
        for image in node.find_all("img")
    )
    context = f"{text} {image_text}"
    for canonical, aliases in TEAM_ALIASES.items():
        if any(alias in context for alias in aliases):
            return canonical
    return None


def parse_starters_html(content: bytes, now: datetime | None = None) -> dict:
    current = now.astimezone(JST) if now is not None else datetime.now(JST)
    soup = BeautifulSoup(content, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    date_match = re.search(r"(\d{1,2})月(\d{1,2})日の予告先発", page_text)
    if not date_match:
        date_match = re.search(r"(\d{1,2})月(\d{1,2})日", page_text)
    if not date_match:
        raise ValueError("official starter page did not contain a target date")

    month, day = map(int, date_match.groups())
    year = current.year
    if current.month == 12 and month == 1:
        year += 1
    elif current.month == 1 and month == 12:
        year -= 1

    starters: dict[str, str] = {}
    for player_link in soup.select('a[href*="/bis/players/"]'):
        player = player_link.get_text(" ", strip=True)
        if not player:
            continue
        team = None
        node = player_link
        for _ in range(6):
            team = _team_in_node(node)
            if team:
                break
            node = node.parent
            if node is None:
                break
        if team:
            starters.setdefault(team, player)

    if not starters:
        raise ValueError("official starter page did not contain any player/team pairs")
    return {
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "updated_at": current.isoformat(timespec="seconds"),
        "starters": starters,
        "source": "NPB公式 予告先発",
        "source_url": SOURCE_URL,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/npb_starters.json")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    response = requests.get(SOURCE_URL, headers=HEADERS, timeout=args.timeout)
    response.raise_for_status()
    payload = parse_starters_html(response.content)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(f"Saved {len(payload['starters'])} starters for {payload['date']} to {output}")


if __name__ == "__main__":
    main()
