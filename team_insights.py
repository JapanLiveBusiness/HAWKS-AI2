"""Team-level summaries derived from the shared NPB game history."""

from __future__ import annotations

from typing import Any

from result_sources import merge_final_games


def merge_team_history(history: list[dict], results: list[dict]) -> list[dict]:
    """Add cached finals to historical records without counting a game twice."""
    historical = [dict(row, status=row.get("status") or "final")
                  for row in history if isinstance(row, dict)]
    return merge_final_games(historical, results)


TEAMS = (
    "ソフトバンク", "日本ハム", "楽天", "西武", "ロッテ", "オリックス",
    "巨人", "阪神", "DeNA", "広島", "ヤクルト", "中日",
)

TEAM_META = {
    "ソフトバンク": {"abbr": "H", "league": "パ・リーグ", "logo": "hawks.png"},
    "日本ハム": {"abbr": "F", "league": "パ・リーグ", "logo": "fighters.png"},
    "楽天": {"abbr": "E", "league": "パ・リーグ", "logo": "eagles.png"},
    "西武": {"abbr": "L", "league": "パ・リーグ", "logo": "lions.png"},
    "ロッテ": {"abbr": "M", "league": "パ・リーグ", "logo": "marines.png"},
    "オリックス": {"abbr": "B", "league": "パ・リーグ", "logo": "buffaloes.png"},
    "巨人": {"abbr": "G", "league": "セ・リーグ", "logo": "giants.png"},
    "阪神": {"abbr": "T", "league": "セ・リーグ", "logo": "hanshin.png"},
    "DeNA": {"abbr": "DB", "league": "セ・リーグ", "logo": "baystars.png"},
    "広島": {"abbr": "C", "league": "セ・リーグ", "logo": "carp.png"},
    "ヤクルト": {"abbr": "S", "league": "セ・リーグ", "logo": "swallows.png"},
    "中日": {"abbr": "D", "league": "セ・リーグ", "logo": "dragons.png"},
}


def _team_game(row: dict[str, Any], team: str) -> dict[str, Any] | None:
    home, away = str(row.get("home") or ""), str(row.get("away") or "")
    if team not in {home, away}:
        return None
    try:
        home_score, away_score = int(row["home_score"]), int(row["away_score"])
    except (KeyError, TypeError, ValueError):
        return None
    is_home = home == team
    runs_for, runs_against = (home_score, away_score) if is_home else (away_score, home_score)
    return {
        "date": str(row.get("date") or ""),
        "opponent": away if is_home else home,
        "home_away": "ホーム" if is_home else "ビジター",
        "runs_for": runs_for,
        "runs_against": runs_against,
        "result": "勝" if runs_for > runs_against else ("敗" if runs_for < runs_against else "分"),
        "venue": row.get("venue") or "--",
        "starter": row.get("home_starter" if is_home else "away_starter"),
    }


def team_games(history: list[dict[str, Any]], team: str, season: int | None = None) -> list[dict[str, Any]]:
    games = []
    for row in history:
        if not isinstance(row, dict):
            continue
        if season is not None and int(row.get("season") or 0) != season:
            continue
        game = _team_game(row, team)
        if game:
            games.append(game)
    return sorted(games, key=lambda game: game["date"], reverse=True)


def team_summary(history: list[dict[str, Any]], team: str, season: int | None = None) -> dict[str, Any]:
    games = team_games(history, team, season)
    wins = sum(game["result"] == "勝" for game in games)
    losses = sum(game["result"] == "敗" for game in games)
    draws = sum(game["result"] == "分" for game in games)
    recent = games[:10]
    recent_wins = sum(game["result"] == "勝" for game in recent)
    return {
        "team": team,
        "season": season,
        "games": games,
        "played": len(games),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": wins / (wins + losses) * 100 if wins + losses else None,
        "runs_for": sum(game["runs_for"] for game in games),
        "runs_against": sum(game["runs_against"] for game in games),
        "run_diff": sum(game["runs_for"] - game["runs_against"] for game in games),
        "recent_wins": recent_wins,
        "recent_played": len(recent),
    }


def league_standings(history: list[dict[str, Any]], league: str, season: int) -> list[dict[str, Any]]:
    rows = []
    for team in TEAMS:
        if TEAM_META[team]["league"] != league:
            continue
        summary = team_summary(history, team, season)
        rows.append(summary)
    rows.sort(key=lambda row: (row["win_rate"] if row["win_rate"] is not None else -1, row["run_diff"]), reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def upcoming_team_game(schedule: dict[str, Any], predictions: dict[str, Any], team: str) -> dict[str, Any] | None:
    prediction_index = {
        (str(row.get("home") or ""), str(row.get("away") or "")): row
        for row in predictions.get("games") or []
        if isinstance(row, dict)
    }
    for game in schedule.get("games") or []:
        if not isinstance(game, dict) or team not in {game.get("home"), game.get("away")}:
            continue
        result = dict(game)
        result.update(prediction_index.get((str(game.get("home") or ""), str(game.get("away") or "")), {}))
        is_home = game.get("home") == team
        result["opponent"] = game.get("away") if is_home else game.get("home")
        result["team_starter"] = game.get("home_starter" if is_home else "away_starter")
        result["opponent_starter"] = game.get("away_starter" if is_home else "home_starter")
        return result
    return None
