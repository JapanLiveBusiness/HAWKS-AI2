import json
from pathlib import Path

from prediction_metrics import build_prediction_metrics


def _write(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_prediction_metrics_uses_history_and_prediction_fallback(tmp_path):
    _write(
        tmp_path / "pregame_predictions.json",
        [
            {"date": "2026-08-15", "opponent": "楽天", "probability": 63.4},
            {"date": "2026-08-18", "opponent": "日本ハム", "probability": 63.4},
        ],
    )
    _write(
        tmp_path / "game_history.json",
        [
            {
                "game_id": "loss",
                "date": "2026-08-15",
                "opponent": "楽天",
                "result": "敗",
                "pregame_probability": 63.4,
            },
            {
                "game_id": "win",
                "date": "2026-08-18",
                "opponent": "日本ハム",
                "result": "勝",
            },
            {
                "game_id": "draw",
                "date": "2026-08-20",
                "opponent": "日本ハム",
                "result": "分",
                "pregame_probability": 63.4,
            },
        ],
    )

    metrics = build_prediction_metrics(tmp_path)

    assert metrics["status"] == "ready"
    assert metrics["verified_count"] == 2
    assert metrics["hits"] == 1
    assert metrics["hit_rate"] == 50.0
    assert metrics["brier_score"] == 0.267956


def test_build_prediction_metrics_merges_research_data(tmp_path):
    production = tmp_path / "production"
    research = tmp_path / "research"
    production.mkdir()
    research.mkdir()
    _write(production / "game_history.json", [])
    _write(production / "pregame_predictions.json", [])
    _write(
        research / "game_history.json",
        [{"game_id": "shared-win", "date": "2026-09-01", "opponent": "西武", "result": "勝", "pregame_probability": 60}],
    )
    _write(research / "pregame_predictions.json", [])

    metrics = build_prediction_metrics(production, research)

    assert metrics["source"] == "research-shared-data"
    assert metrics["shared_count"] == 1
    assert metrics["verified_count"] == 1
