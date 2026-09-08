"""Read the persisted final scores shared by results and team pages."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


FINAL_STATUSES = {"final", "finished", "completed", "終了", "試合終了"}


def final_game(row: dict, fallback_date: str = "") -> dict | None:
    """Reject incomplete/live scores and retain each game's own date."""
    if not isinstance(row, dict) or row.get("status") not in FINAL_STATUSES:
        return None
    try:
        day = date.fromisoformat(str(row.get("date") or fallback_date))
        scores = [str(row[key]).strip() for key in ("home_score", "away_score")]
        if not all(score.isdecimal() for score in scores):
            return None
        home, away = str(row.get("home") or ""), str(row.get("away") or "")
        if not home or not away or home == away:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return dict(row, date=day.isoformat(), season=day.year, status="final",
                home_score=int(scores[0]), away_score=int(scores[1]))


def merge_final_games(*sources: list[dict]) -> list[dict]:
    """Deduplicate completed games; later sources can correct older scores."""
    merged = {}
    for source in sources:
        for row in source:
            game = final_game(row)
            if game is None:
                continue
            key = (game["date"], *sorted((game["home"], game["away"])))
            previous = merged.get(key, {})
            # Keep the original home/away orientation when a source lists teams
            # in reverse, including all side-specific metadata.
            if previous and previous["home"] != game["home"]:
                swapped = {k: v for k, v in game.items()
                           if not k.startswith(("home_", "away_"))}
                for field, value in game.items():
                    if field.startswith("home_"):
                        swapped["away_" + field[5:]] = value
                    elif field.startswith("away_"):
                        swapped["home_" + field[5:]] = value
                swapped["home"], swapped["away"] = game["away"], game["home"]
                game = swapped
            merged[key] = {**previous, **{k: v for k, v in game.items() if v is not None}}
    return sorted(merged.values(), key=lambda row: (row["date"], row["home"], row["away"]))


def load_final_results(data_dir: Path, shared_data_dir: Path | None = None,
                       *, repo_root: Path | None = None) -> list[dict]:
    """Read local caches only; never fetch or modify live production data."""
    root = repo_root if repo_root is not None else Path(__file__).resolve().parent
    paths = [root / "npb_schedule_fallback.json", root / "npb_results_fallback.json"]
    for directory in (shared_data_dir, data_dir):
        if directory is not None:
            paths.extend(directory / name for name in (
                "npb_schedule_cache.json", "npb_results_cache.json", "npb_today.json",
            ))
    sources = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
            continue
        rows = []
        for row in payload["games"]:
            game = final_game(row, str(payload.get("date") or ""))
            if game is not None:
                rows.append(game)
        sources.append(rows)
    return merge_final_games(*sources)
