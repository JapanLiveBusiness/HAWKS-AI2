"""Game data for manual entry; never infer a final score from the date alone."""
from datetime import date
import json
import math
from pathlib import Path
import re
import unicodedata

from game_calendar import (
    fetch_daily_handicaps, fetch_npb_schedule_day, load_npb_schedule_day,
    normalize_team, same_match,
)


def _oriented(row, home, away):
    if normalize_team(row.get("home")) == normalize_team(home):
        return dict(row)
    result = dict(row, home=home, away=away)
    for suffix in ("score", "handicap"):
        result[f"home_{suffix}"] = row.get(f"away_{suffix}")
        result[f"away_{suffix}"] = row.get(f"home_{suffix}")
    return result


def load_entry_games(target_date, cache_paths, *, today=None):
    cache_paths = tuple(cache_paths)
    games = load_npb_schedule_day(target_date, cache_paths, timeout=6)
    today = today or date.today()
    # Reuse the result caches used by the game calendar during source outages.
    result_paths = []
    for path in cache_paths:
        path = Path(path)
        if path.name == "npb_schedule_fallback.json":
            result_paths.append(path.with_name("npb_results_fallback.json"))
        else:
            result_paths.extend(path.with_name(name) for name in (
                "npb_results_cache.json", "historical_games_2017_2026.json",
            ))
    for path in dict.fromkeys(result_paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = payload.get("games", []) if isinstance(payload, dict) else payload
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or row.get("date") != target_date.isoformat():
                continue
            if not row.get("home") or not row.get("away"):
                continue
            row = dict(row)
            if path.name == "historical_games_2017_2026.json":
                row["status"] = "final"
            game = next((g for g in games if same_match(g, row)), None)
            if game is None:
                games.append(row)
            else:
                row = _oriented(row, game["home"], game["away"])
                was_final = game.get("status") in {"final", "cancelled"}
                for key, value in row.items():
                    if value is None or value in ("", "--:--", "会場未定"):
                        continue
                    if was_final and key in {"status", "home_score", "away_score", "result_source"}:
                        continue
                    game[key] = value
    if target_date <= today and any(g.get("status") not in {"final", "cancelled"} for g in games):
        fresh = fetch_npb_schedule_day(target_date, timeout=6)
        for game in games:
            row = next((r for r in fresh if same_match(game, r)), None)
            if row:
                row = _oriented(row, game["home"], game["away"])
                for key, value in row.items():
                    if value not in (None, "", "--:--", "会場未定"):
                        if game.get("status") in {"final", "cancelled"} and row.get("status") not in {"final", "cancelled"} and key in {"status", "home_score", "away_score", "result_source"}:
                            continue
                        game[key] = value
    handicaps = fetch_daily_handicaps(target_date, timeout=6)
    # The handicap source is also a fallback when official schedules are unavailable.
    if not games:
        games = [dict(row) for row in handicaps]
    for game in games:
        row = next((r for r in handicaps if same_match(game, r)), None)
        if row:
            row = _oriented(row, game["home"], game["away"])
            for key in ("home_handicap", "away_handicap", "handicap_source_url"):
                if row.get(key) is not None:
                    game[key] = row[key]
    return games


def _handicap_number(value):
    if value is None or str(value).strip() == "":
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip().strip("<>")
    if re.fullmatch(r"\d*半", text):
        return float(text[:-1] or 0) + 0.5
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def entry_defaults(game, team):
    game = game or {}
    side = "home" if normalize_team(team) == normalize_team(game.get("home")) else "away"
    other = "away" if side == "home" else "home"
    handicap = _handicap_number(game.get(f"{side}_handicap"))
    if handicap is None:
        opposing = _handicap_number(game.get(f"{other}_handicap"))
        handicap = -opposing if opposing is not None else None
    final = str(game.get("status") or "").lower() in {"final", "finished", "completed", "終了", "試合終了"}
    def score(key):
        value = game.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None
    return {
        "team": team,
        "opponent": game.get(other, ""),
        "time": game.get("time") or "18:00",
        "handicap": handicap,
        "status": "確定" if final else "未確定",
        "team_score": score(f"{side}_score") if final else None,
        "opponent_score": score(f"{other}_score") if final else None,
    }
