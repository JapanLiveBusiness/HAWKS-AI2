from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import requests
from handenomori_client import fetch_member_page
from bs4 import BeautifulSoup


NPB_SCHEDULE_URL = "https://npb.jp/games/{year}/schedule_{month:02d}_detail.html"
HANDICAP_URL = "https://handenomori.com/jpb/{ymd}/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/151 Safari/537.36"
    )
}
TEAM_NAMES = (
    "ソフトバンク",
    "日本ハム",
    "オリックス",
    "ヤクルト",
    "DeNA",
    "ロッテ",
    "巨人",
    "阪神",
    "広島",
    "中日",
    "楽天",
    "西武",
)
TEAM_ALIASES = {
    "福岡ソフトバンク": "ソフトバンク",
    "横浜DeNA": "DeNA",
}
TEAM_CODE_NAMES = {
    "g": "巨人",
    "s": "ヤクルト",
    "db": "DeNA",
    "d": "中日",
    "t": "阪神",
    "c": "広島",
    "f": "日本ハム",
    "e": "楽天",
    "l": "西武",
    "m": "ロッテ",
    "b": "オリックス",
    "h": "ソフトバンク",
}
LIVE_INNING_PATTERN = re.compile(r"(?:^|\s)(?:[1-9]|1[0-2])回(?:表|裏)?(?:\s|$)")
FINAL_SCORE_PATTERN = re.compile(r"(?:試合終了|終了)")


def pending_status_label(game: dict, now: datetime | None = None) -> str:
    """A missing score is not a pending result before the scheduled start."""
    jst = ZoneInfo("Asia/Tokyo")
    current = now.astimezone(jst) if now is not None else datetime.now(jst)
    try:
        start = datetime.fromisoformat(f"{game['date']}T{game['time']}").replace(tzinfo=jst)
    except (KeyError, TypeError, ValueError):
        return "結果確認中"
    return "開始前" if current < start else "結果確認中"


def clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_team(value) -> str:
    text = clean_text(value)
    for alias, canonical in TEAM_ALIASES.items():
        text = text.replace(alias, canonical)
    return text


def _teams_in_text(text: str) -> list[str]:
    normalized = normalize_team(text)
    found = []
    for team in TEAM_NAMES:
        position = normalized.find(team)
        if position >= 0:
            found.append((position, team))
    return [team for _, team in sorted(found)[:2]]


def parse_npb_schedule_html(content, year: int, month: int) -> list[dict]:
    """Parse one official NPB monthly schedule into normalized game rows."""
    soup = BeautifulSoup(content, "html.parser")
    current_date = None
    games = []
    source_url = NPB_SCHEDULE_URL.format(year=year, month=month)

    for row in soup.find_all("tr"):
        cells = [clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        text = clean_text(row.get_text(" ", strip=True))
        date_match = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", text)
        if date_match:
            try:
                current_date = date(year, int(date_match.group(1)), int(date_match.group(2)))
            except ValueError:
                current_date = None
        if current_date is None or current_date.month != month:
            continue

        teams = _teams_in_text(text)
        if len(teams) != 2:
            continue

        matchup_cell = next((cell for cell in cells if len(_teams_in_text(cell)) == 2), text)
        score_match = re.search(r"(?<!\d)(\d{1,2})\s*-\s*(\d{1,2})(?!\d)", matchup_cell)
        time_match = re.search(r"(?<!\d)(\d{1,2}:\d{2})(?!\d)", text)
        venue = "会場未定"
        if time_match:
            venue_cell = next((cell for cell in cells if time_match.group(1) in cell), "")
            candidate = clean_text(venue_cell.split(time_match.group(1), 1)[0])
            if candidate:
                venue = candidate

        status = "scheduled"
        if score_match and LIVE_INNING_PATTERN.search(text):
            status = "live"
        elif score_match:
            status = "final"
        elif any(token in text for token in ("中止", "ノーゲーム")):
            status = "cancelled"

        games.append(
            {
                "date": current_date.isoformat(),
                "time": time_match.group(1) if time_match else "--:--",
                "status": status,
                "home": teams[0],
                "away": teams[1],
                "home_score": int(score_match.group(1)) if score_match else None,
                "away_score": int(score_match.group(2)) if score_match else None,
                "venue": venue,
                "source_url": source_url,
                "official_url": source_url,
                "result_source": "NPB公式",
            }
        )

    unique = {}
    for game in games:
        unique[(game["date"], game["home"], game["away"])] = game

    # The official monthly page updates scores inside a linked compact view,
    # while its detail row can remain as the original pre-game schedule.
    # Merge those live link values over the corresponding detail row.
    score_path = re.compile(
        rf"/scores/{year}/(\d{{4}})/([a-z]+)-([a-z]+)-\d+/?(?:box\.html)?$"
    )
    for anchor in soup.find_all("a", href=True):
        path_match = score_path.search(str(anchor.get("href") or ""))
        anchor_text = clean_text(anchor.get_text(" ", strip=True))
        score_match = re.search(r"(?<!\d)(\d{1,2})\s*-\s*(\d{1,2})(?!\d)", anchor_text)
        is_live_score = bool(LIVE_INNING_PATTERN.search(anchor_text))
        is_final_score = bool(FINAL_SCORE_PATTERN.search(anchor_text))
        if not path_match or not score_match or not (is_live_score or is_final_score):
            continue
        mmdd, home_code, away_code = path_match.groups()
        try:
            game_date = date(year, int(mmdd[:2]), int(mmdd[2:]))
        except ValueError:
            continue
        key = (game_date.isoformat(), TEAM_CODE_NAMES.get(home_code, ""), TEAM_CODE_NAMES.get(away_code, ""))
        if key in unique:
            unique[key].update({
                "status": "final" if is_final_score else "live",
                "home_score": int(score_match.group(1)),
                "away_score": int(score_match.group(2)),
                "result_source": "NPB公式速報",
            })
    return list(unique.values())


def fetch_npb_schedule_day(target_date: date, timeout: int = 12) -> list[dict]:
    url = NPB_SCHEDULE_URL.format(year=target_date.year, month=target_date.month)
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        games = parse_npb_schedule_html(response.content, target_date.year, target_date.month)
    except Exception:
        return []
    return [game for game in games if game.get("date") == target_date.isoformat()]


def load_npb_schedule_day(
    target_date: date,
    cache_paths: Iterable[Path],
    *,
    timeout: int = 6,
) -> list[dict]:
    """Load a day from persisted schedules, falling back to the official site."""
    target_iso = target_date.isoformat()
    for path in cache_paths:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        games = [
            dict(game)
            for game in payload.get("games") or []
            if isinstance(game, dict) and str(game.get("date") or "") == target_iso
        ]
        if games:
            return games
    return fetch_npb_schedule_day(target_date, timeout=timeout)


def parse_handicap_html(content, target_date: date) -> list[dict]:
    """Parse every published handicap from a Handenomori daily page."""
    soup = BeautifulSoup(content, "html.parser")
    games = []
    source_url = HANDICAP_URL.format(ymd=target_date.strftime("%Y%m%d"))

    for card in soup.select(".game-detail2"):
        teams = [normalize_team(node.get_text(" ", strip=True)) for node in card.select(".detail-card-team")]
        teams = [team for team in teams if team]
        if len(teams) < 2:
            continue

        handicap_cells = [clean_text(node.get_text(" ", strip=True)) for node in card.select("td.single-handi-handi")]
        handicap_cells += [""] * max(0, 2 - len(handicap_cells))
        score_match = re.search(r"(?<!\d)(\d{1,2})\s*-\s*(\d{1,2})(?!\d)", clean_text(card.get_text(" ", strip=True)))
        info = [clean_text(node.get_text(" ", strip=True)) for node in card.select(".detail-single-studium-time span")]

        games.append(
            {
                "date": target_date.isoformat(),
                "home": teams[0],
                "away": teams[1],
                "home_score": int(score_match.group(1)) if score_match else None,
                "away_score": int(score_match.group(2)) if score_match else None,
                "status": "final" if score_match else "result_pending",
                "home_handicap": handicap_cells[0] or None,
                "away_handicap": handicap_cells[1] or None,
                "time": info[0] if info else None,
                "venue": info[1] if len(info) > 1 else None,
                "handicap_source_url": source_url,
                "result_source": "ハンデの森",
            }
        )
    return games


def fetch_daily_handicaps(target_date: date, timeout: int = 12, *, strict: bool = False) -> list[dict]:
    url = HANDICAP_URL.format(ymd=target_date.strftime("%Y%m%d"))
    try:
        return parse_handicap_html(fetch_member_page(url, timeout=timeout), target_date)
    except Exception:
        if strict:
            raise
        return []


def same_match(left: dict, right: dict) -> bool:
    left_teams = {normalize_team(left.get("home")), normalize_team(left.get("away"))}
    right_teams = {normalize_team(right.get("home")), normalize_team(right.get("away"))}
    return "" not in left_teams and left_teams == right_teams


def _status_phase(value) -> int:
    status = clean_text(value).lower()
    if status in {"final", "finished", "completed", "終了", "試合終了", "cancelled", "中止"}:
        return 2
    if status in {"live", "in_progress", "playing", "試合中", "開催中"} or any(
        token in status for token in ("live", "progress", "試合中")
    ):
        return 1
    return 0


def merge_game_sources(*sources: list[dict]) -> list[dict]:
    """Merge schedule/result sources without downgrading confirmed results."""
    merged = []
    for source in sources:
        for incoming in source or []:
            existing = next((game for game in merged if same_match(game, incoming)), None)
            if existing is None:
                merged.append(dict(incoming))
                continue
            existing_phase = _status_phase(existing.get("status"))
            incoming_phase = _status_phase(incoming.get("status"))
            for key, value in incoming.items():
                if value not in (None, "", "--:--", "会場未定"):
                    if existing_phase > incoming_phase and key in {
                        "status", "home_score", "away_score", "result_source",
                    }:
                        continue
                    existing[key] = value
    return merged


def attach_handicaps(games: list[dict], handicaps: list[dict]) -> list[dict]:
    output = [dict(game) for game in games]
    for game in output:
        row = next((item for item in handicaps if same_match(game, item)), None)
        if row:
            for key in ("home_handicap", "away_handicap", "handicap_source_url"):
                game[key] = row.get(key)
    return output


def attach_hawks_history_results(
    games: list[dict],
    history: list[dict],
) -> list[dict]:
    """Restore persisted Hawks finals when the schedule source regresses."""
    output = [dict(game) for game in games]
    for record in history or []:
        if not isinstance(record, dict):
            continue
        opponent = normalize_team(record.get("opponent"))
        record_date = str(record.get("date") or "")
        game = next(
            (
                row
                for row in output
                if str(row.get("date") or "") == record_date
                and {normalize_team(row.get("home")), normalize_team(row.get("away"))}
                == {"ソフトバンク", opponent}
            ),
            None,
        )
        if game is None:
            continue
        hawks_score = record.get("hawks_score")
        opponent_score = record.get("opponent_score")
        if hawks_score is None or opponent_score is None:
            continue
        game["status"] = "final"
        game["result_source"] = record.get("source") or "保存済み試合結果"
        if normalize_team(game.get("home")) == "ソフトバンク":
            game["home_score"], game["away_score"] = hawks_score, opponent_score
        else:
            game["home_score"], game["away_score"] = opponent_score, hawks_score
    return output
