import json

from result_sources import final_game, load_final_results, merge_final_games
from team_insights import merge_team_history, team_summary


def game(**changes):
    return {"date": "2026-09-05", "home": "ソフトバンク", "away": "西武",
            "home_score": 2, "away_score": 0, "status": "final", **changes}


def test_only_completed_valid_scores_are_admitted():
    for invalid in (None, {}, game(status="live"), game(status="scheduled"),
                    game(home_score=None), game(home_score=-1),
                    game(home_score=1.5), game(home_score=True),
                    game(date="invalid"), game(away="ソフトバンク")):
        assert final_game(invalid) is None
    assert final_game(game(home_score="2"))["home_score"] == 2
    assert final_game(game())["season"] == 2026


def test_cache_reader_keeps_per_game_dates_and_runtime_corrections(tmp_path):
    production = tmp_path / "production"
    research = tmp_path / "research"
    production.mkdir()
    research.mkdir()
    (tmp_path / "npb_results_fallback.json").write_text(
        json.dumps({"games": [game(home_score=1)]}), encoding="utf-8")
    (research / "npb_results_cache.json").write_text(
        json.dumps({"games": [game(home_score=3)]}), encoding="utf-8")
    (production / "npb_results_cache.json").write_text(
        json.dumps({"date": "2026-09-06", "games": [game(), game(date="2026-09-06", status="live")]}),
        encoding="utf-8")
    (production / "npb_today.json").write_text("broken JSON", encoding="utf-8")

    rows = load_final_results(production, research, repo_root=tmp_path)

    assert len(rows) == 1
    assert rows[0]["date"] == "2026-09-05"
    assert rows[0]["home_score"] == 2


def test_reversed_team_order_preserves_team_scores_and_metadata():
    original = game(venue="球場", home_starter="投手A", away_starter="投手B")
    reversed_row = game(home="西武", away="ソフトバンク", home_score=0,
                        away_score=2, away_starter="投手C")
    rows = merge_final_games([original], [reversed_row])
    assert len(rows) == 1
    assert rows[0]["home"] == "ソフトバンク"
    assert rows[0]["home_score"] == 2
    assert rows[0]["away_score"] == 0
    assert rows[0]["home_starter"] == "投手C"
    assert rows[0]["away_starter"] == "投手B"


def test_team_history_includes_new_results_once_without_mutating_history():
    historical = [game(date="2026-09-01", season=2026, home_score=1, away_score=2)]
    historical[0].pop("status")
    cached = [game(), game(), game(date="2026-09-06", status="live")]

    merged = merge_team_history(historical, cached)
    summary = team_summary(merged, "ソフトバンク", 2026)

    assert summary["played"] == 2
    assert (summary["wins"], summary["losses"]) == (1, 1)
    assert summary["games"][0]["date"] == "2026-09-05"
    assert "status" not in historical[0]
    assert merge_team_history(merged, cached) == merged
