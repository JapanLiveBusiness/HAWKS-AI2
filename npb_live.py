"""Lightweight NPB official live-game enrichment for the games page."""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from game_calendar import HEADERS, NPB_SCHEDULE_URL, normalize_team


TEAM_CODES = {
    "巨人": "g",
    "ヤクルト": "s",
    "DeNA": "db",
    "中日": "d",
    "阪神": "t",
    "広島": "c",
    "日本ハム": "f",
    "楽天": "e",
    "西武": "l",
    "ロッテ": "m",
    "オリックス": "b",
    "ソフトバンク": "h",
}
FINAL_MARKERS = ("試合終了", "終了")
PREGAME_MARKERS = ("試合開始前", "試合前")


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def find_score_url(content: bytes | str, target_date: date, home: str, away: str) -> str | None:
    """Find the official box-score URL for one matchup in a monthly schedule."""
    schedule_url = NPB_SCHEDULE_URL.format(year=target_date.year, month=target_date.month)
    path_token = f"/scores/{target_date.year}/{target_date.strftime('%m%d')}/"
    expected_codes = {TEAM_CODES.get(normalize_team(home)), TEAM_CODES.get(normalize_team(away))}
    expected_codes.discard(None)
    soup = BeautifulSoup(content, "html.parser")

    fallback = None
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        if path_token not in href:
            continue
        absolute = urljoin(schedule_url, href)
        box_url = absolute if absolute.endswith("box.html") else absolute.rstrip("/") + "/box.html"
        if fallback is None:
            fallback = box_url

        game_code = href.strip("/").split("/")[-1].replace("box.html", "").strip("/")
        link_codes = set(game_code.split("-"))
        context_parent = anchor.find_parent(["tr", "li", "div"])
        context = normalize_team(context_parent.get_text(" ", strip=True) if context_parent else "")
        teams_match = home in context and away in context
        codes_match = len(expected_codes) == 2 and expected_codes.issubset(link_codes)
        if teams_match or codes_match:
            return box_url
    return fallback if len(expected_codes) < 2 else None


def _score_from_cells(cells: list[str], total_index: int | None) -> int | None:
    index = total_index if total_index is not None and total_index < len(cells) else 10
    if index >= len(cells):
        return None
    match = re.fullmatch(r"\d{1,2}", cells[index])
    return int(cells[index]) if match else None


def parse_box_score(content: bytes | str, home: str, away: str) -> dict[str, Any]:
    """Parse status and team-oriented totals from an NPB box-score page."""
    soup = BeautifulSoup(content, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True))
    status = "final" if any(marker in page_text for marker in FINAL_MARKERS) else (
        "scheduled" if any(marker in page_text for marker in PREGAME_MARKERS) else "live"
    )
    result: dict[str, Any] = {"status": status}

    wanted = {normalize_team(home): "home_score", normalize_team(away): "away_score"}
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        headers = [_text(cell.get_text(" ", strip=True)) for cell in rows[0].find_all(["th", "td"])] if rows else []
        total_index = next((index for index, value in enumerate(headers) if value in {"計", "R"}), None)
        found: dict[str, int] = {}
        for row in rows[1:]:
            cells = [_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
            if not cells:
                continue
            team = normalize_team(cells[0])
            for expected, key in wanted.items():
                if expected and expected in team:
                    score = _score_from_cells(cells, total_index)
                    if score is not None:
                        found[key] = score
        if len(found) == 2:
            result.update(found)
            break
    return result


def _parse_count(value: str) -> tuple[int | None, int | None]:
    match = re.search(r"([0-3])\s*[-－]\s*([0-2])", value)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_play_by_play(content: bytes | str) -> dict[str, Any]:
    """Parse the latest inning and active plate appearance from NPB play-by-play."""
    soup = BeautifulSoup(content, "html.parser")
    inning_pattern = re.compile(r"(\d+)回(表|裏)（([^）]+)の攻撃）")
    headings = []
    for tag in soup.find_all(["h3", "h4", "h5", "h6"]):
        match = inning_pattern.search(_text(tag.get_text(" ", strip=True)))
        if match:
            headings.append((tag, match))
    if not headings:
        return {}

    # NPB renders headings for later innings before those innings begin. Walk
    # backwards and use the newest section that contains an actual play row.
    selected = None
    rows: list[list[str]] = []
    for heading, match in reversed(headings):
        section_rows: list[list[str]] = []
        cursor = heading.find_next()
        while cursor is not None:
            if cursor.name in {"h3", "h4", "h5", "h6"} and inning_pattern.search(
                _text(cursor.get_text(" ", strip=True))
            ):
                break
            if cursor.name == "tr":
                cells = [_text(cell.get_text(" ", strip=True)) for cell in cursor.find_all(["th", "td"])]
                if len(cells) >= 5 and re.match(r"^[0-2]アウト$", cells[0]):
                    section_rows.append(cells)
            cursor = cursor.find_next()
        if section_rows:
            selected = (heading, match)
            rows = section_rows
            break

    if selected is None:
        return {}

    heading, match = selected
    result: dict[str, Any] = {
        "inning": int(match.group(1)),
        "inning_half": match.group(2),
        "batting_team": normalize_team(match.group(3)),
    }

    current = next((cells for cells in reversed(rows) if cells[2] and not cells[4]), None)
    if current is None:
        return result
    result["outs"] = int(current[0][0])
    base_text = current[1]
    result["bases"] = {
        1: "満塁" in base_text or "1塁" in base_text,
        2: "満塁" in base_text or "2塁" in base_text,
        3: "満塁" in base_text or "3塁" in base_text,
    }
    result["current_batter"] = current[2]
    balls, strikes = _parse_count(current[3])
    if balls is not None:
        result["balls"] = balls
    if strikes is not None:
        result["strikes"] = strikes
    return result


def fetch_npb_live_game(target_date: date, home: str, away: str, timeout: int = 8) -> dict[str, Any]:
    """Fetch one official game; return an empty mapping on any unavailable stage."""
    schedule_url = NPB_SCHEDULE_URL.format(year=target_date.year, month=target_date.month)
    try:
        schedule = requests.get(schedule_url, headers=HEADERS, timeout=timeout)
        schedule.raise_for_status()
        score_url = find_score_url(schedule.content, target_date, home, away)
        if not score_url:
            return {}
        box = requests.get(score_url, headers=HEADERS, timeout=timeout)
        box.raise_for_status()
        result = parse_box_score(box.content, home, away)
        result.update(
            {
                "date": target_date.isoformat(),
                "home": home,
                "away": away,
                "official_url": score_url,
                "live_source_url": score_url,
                "result_source": "NPB公式速報",
            }
        )
        if result.get("status") in {"live", "final"}:
            play_url = score_url.replace("/box.html", "/playbyplay.html")
            try:
                play = requests.get(play_url, headers=HEADERS, timeout=timeout)
                play.raise_for_status()
                result.update(parse_play_by_play(play.content))
                result["play_url"] = play_url
            except requests.RequestException:
                pass
        return result
    except requests.RequestException:
        return {}
