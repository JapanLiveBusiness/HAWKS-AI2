import json

from prediction_results import (
    archive_predictions,
    backfill_season_predictions,
    build_performance,
    calibrate_home_probability,
    load_historical_validation,
    merge_prediction_archives,
    settle_predictions,
    sync_prediction_results,
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_settlement_uses_each_cached_game_date_and_not_envelope_date():
    predictions = {
        "date": "2026-09-05",
        "updated_at": "2026-09-05T17:00:00+09:00",
        "games": [{"home": "A", "away": "B", "pick": "A", "win_probability": 60}],
    }
    archive, _ = archive_predictions([], predictions, {
        "date": "2026-09-05",
        "games": [{"home": "A", "away": "B", "time": "18:00"}],
    })
    cache = {"date": "2026-09-06", "games": [
        {"date": "2026-09-05", "home": "A", "away": "B", "status": "final",
         "home_score": 2, "away_score": 0},
        {"date": "2026-09-06", "home": "A", "away": "B", "status": "live",
         "home_score": 0, "away_score": 1}]}
    settled, count = settle_predictions(archive, cache)
    assert count == 1
    assert settled[0]["hit"] is True
    assert settled[0]["actual_home_score"] == 2
    assert settled[0]["win_probability"] == 60
    assert archive[0]["status"] == "pending"
    assert settle_predictions(settled, cache)[1] == 0


def test_settlement_maps_scores_to_archived_home_away_order():
    archive = [{"date": "2026-09-05", "home": "A", "away": "B", "pick": "A",
                "home_win_probability": 60, "status": "pending"}]
    cache = {"games": [{"date": "2026-09-05", "home": "B", "away": "A",
                         "status": "final", "home_score": 0, "away_score": 2}]}
    settled, count = settle_predictions(archive, cache)
    assert count == 1
    assert settled[0]["hit"] is True
    assert settled[0]["actual_home_score"] == 2


def test_sync_settles_previous_day_from_results_cache(tmp_path):
    _write_json(tmp_path / "ai_prediction_history.json", [
        {"game_id": "2026-09-05_A_B", "date": "2026-09-05", "home": "A",
         "away": "B", "pick": "A", "win_probability": 60, "status": "pending"}])
    _write_json(tmp_path / "npb_today.json", {"date": "2026-09-06", "games": []})
    _write_json(tmp_path / "npb_results_cache.json", {"games": [
        {"date": "2026-09-05", "home": "A", "away": "B", "status": "final",
         "home_score": 2, "away_score": 0}]})
    result = sync_prediction_results(tmp_path, None)
    saved = json.loads((tmp_path / "ai_prediction_history.json").read_text(encoding="utf-8"))
    assert result["settled"] == 1
    assert saved[0]["status"] == "final"
    assert saved[0]["win_probability"] == 60


def test_all_predictions_are_locked_and_settled_from_final_schedule():
    predictions = {
        "date": "2026-09-04",
        "updated_at": "2026-09-04T10:00:00+09:00",
        "model": "test-model",
        "games": [
            {"home": "阪神", "away": "巨人", "pick": "阪神", "win_probability": 60, "predicted_score": "4-2", "confidence": "HIGH"},
            {"home": "西武", "away": "楽天", "pick": "楽天", "win_probability": 55, "predicted_score": "2-3", "confidence": "LOW"},
        ],
    }
    schedule = {
        "date": "2026-09-04",
        "games": [
            {"home": "阪神", "away": "巨人", "time": "18:00", "status": "final", "home_score": 5, "away_score": 1},
            {"home": "西武", "away": "楽天", "time": "18:00", "status": "final", "home_score": 4, "away_score": 3},
        ],
    }

    archive, added = archive_predictions([], predictions, schedule)
    assert added == 2
    assert archive[0]["home_win_probability"] == 45.0 or archive[1]["home_win_probability"] == 45.0
    settled, settled_count = settle_predictions(archive, schedule)
    performance = build_performance(settled)

    assert settled_count == 2
    assert performance["settled_games"] == 2
    assert performance["hits"] == 1
    assert performance["hit_rate"] == 50.0
    assert all(row["locked"] for row in settled)


def test_locked_prediction_is_not_overwritten_and_draw_is_excluded():
    predictions = {
        "date": "2026-09-04",
        "updated_at": "2026-09-04T10:00:00+09:00",
        "games": [{"home": "A", "away": "B", "pick": "A", "win_probability": 70}],
    }
    schedule = {"date": "2026-09-04", "games": [
        {"home": "A", "away": "B", "time": "18:00", "status": "final", "home_score": 2, "away_score": 2}
    ]}
    archive, _ = archive_predictions([], predictions, schedule)
    changed_predictions = {"date": "2026-09-04", "games": [{"home": "A", "away": "B", "pick": "B", "win_probability": 90}]}
    archive, added = archive_predictions(archive, changed_predictions, schedule)
    settled, _ = settle_predictions(archive, schedule)

    assert added == 0
    assert settled[0]["pick"] == "A"
    assert settled[0]["status"] == "draw"
    assert build_performance(settled)["settled_games"] == 0


def test_shared_final_prediction_replaces_local_pending_copy():
    local = [{"game_id": "g1", "date": "2026-09-04", "status": "pending", "pick": "A"}]
    shared = [
        {
            "game_id": "g1",
            "date": "2026-09-04",
            "status": "final",
            "pick": "A",
            "actual_winner": "A",
            "hit": True,
        },
        {"game_id": "g2", "date": "2026-09-05", "status": "pending", "pick": "B"},
    ]

    merged = merge_prediction_archives(local, shared)

    assert len(merged) == 2
    assert merged[0]["status"] == "final"
    assert merged[0]["hit"] is True


def test_sync_archives_current_research_prediction(tmp_path):
    production = tmp_path / "production"
    research = tmp_path / "research"
    production.mkdir()
    research.mkdir()
    _write_json(production / "today_ai_predictions.json", {})
    _write_json(production / "npb_today.json", {})
    _write_json(
        research / "today_ai_predictions.json",
        {
            "date": "2026-09-05",
            "updated_at": "2026-09-05T17:00:00+09:00",
            "games": [{"home": "A", "away": "B", "pick": "A", "win_probability": 60}],
        },
    )
    _write_json(
        research / "npb_today.json",
        {"date": "2026-09-05", "games": [{"home": "A", "away": "B", "status": "scheduled", "time": "18:00"}]},
    )

    result = sync_prediction_results(production, research)
    saved = json.loads((production / "ai_prediction_history.json").read_text(encoding="utf-8"))

    assert result["added"] == 1
    assert result["shared"] == 1
    assert saved[0]["game_id"] == "2026-09-05_A_B"


def test_backfill_starts_at_first_season_game_and_preserves_real_record(tmp_path):
    csv_path = tmp_path / "historical_backtest_predictions.csv"
    csv_path.write_text(
        "date,season,home,away,actual_home_win,model,home_win_probability,correct\n"
        "2026-03-28,A,B,C,1,logistic_rolling,0.60,True\n"
        "2026-03-29,2026,A,B,1,logistic_rolling,0.60,True\n"
        "2026-03-30,2026,C,D,0,logistic_rolling,0.45,True\n",
        encoding="utf-8",
    )
    real = [{
        "game_id": "2026-03-29_A_B", "date": "2026-03-29", "home": "A",
        "away": "B", "pick": "B", "status": "final", "hit": False,
        "model": "logistic_rolling_v1", "saved_at": "real",
    }]

    merged, added = backfill_season_predictions(real, csv_path, season=2026)

    assert added == 1
    assert merged[0]["date"] == "2026-03-29"
    assert merged[0]["saved_at"] == "real"
    assert merged[1]["actual_winner"] == "D"
    assert merged[1]["historical_validation"] is True


def test_calibration_uses_only_prior_games_in_same_probability_band():
    validation = []
    for index in range(20):
        validation.append({
            "date": f"2026-04-{index + 1:02d}", "status": "final",
            "home": "H", "away": "A", "actual_winner": "H",
            "home_win_probability": 55.0,
            "raw_home_win_probability": 55.0,
        })
    validation.append({
        "date": "2026-06-01", "status": "final", "home": "H", "away": "A",
        "actual_winner": "A", "home_win_probability": 55.0,
    })

    result = calibrate_home_probability(54.0, validation, "2026-05-01")

    assert result["validation_sample_size"] == 20
    assert result["home_win_probability"] > 54.0
    assert result["calibration_method"] == "season_10point_empirical_bayes"


def test_load_historical_validation_accepts_utf8_bom(tmp_path):
    csv_path = tmp_path / "history.csv"
    csv_path.write_text(
        "\ufeffdate,season,home,away,actual_home_win,model,home_win_probability,correct\n"
        "2026-03-28,A,B,C,1,logistic_rolling,0.60,True\n"
        "2026-03-28,2026,A,B,1,logistic_rolling,0.60,True\n",
        encoding="utf-8",
    )
    rows = load_historical_validation(csv_path, season=2026)
    assert len(rows) == 1
    assert rows[0]["win_probability"] == 60.0


def test_archive_rejects_prediction_captured_after_first_pitch():
    predictions = {
        "date": "2026-09-05",
        "updated_at": "2026-09-05T18:01:00+09:00",
        "games": [{"home": "A", "away": "B", "pick": "A", "win_probability": 60}],
    }
    schedule = {
        "date": "2026-09-05",
        "games": [{"home": "A", "away": "B", "time": "18:00", "status": "live"}],
    }

    archive, added = archive_predictions([], predictions, schedule)

    assert added == 0
    assert archive == []
