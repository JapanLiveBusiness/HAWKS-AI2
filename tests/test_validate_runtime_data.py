import json
from pathlib import Path

import pytest

from scripts.validate_runtime_data import validate


def _write(directory: Path, name: str, payload) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def _valid_runtime(tmp_path: Path):
    data = tmp_path / "data"
    shared = tmp_path / "shared"
    _write(data, "bet_records.json", [])
    _write(shared, "npb_today.json", {"date": "2026-09-06", "games": [{"id": 1}]})
    _write(shared, "today_ai_predictions.json", {"date": "2026-09-06", "games": [{"rank": 1}]})
    return data, shared


def test_accepts_current_shared_daily_data_and_runtime_bets(tmp_path):
    data, shared = _valid_runtime(tmp_path)
    messages = validate(data, shared, "2026-09-06")
    assert any("games=1" in message for message in messages)
    assert any("records=0" in message for message in messages)


def test_rejects_stale_daily_data(tmp_path):
    data, shared = _valid_runtime(tmp_path)
    _write(shared, "npb_today.json", {"date": "2026-09-05", "games": []})
    with pytest.raises(ValueError, match="no current data"):
        validate(data, shared, "2026-09-06")


def test_rejects_mismatched_schedule_and_prediction_dates(tmp_path):
    data, shared = _valid_runtime(tmp_path)
    _write(shared, "today_ai_predictions.json", {"date": "2026-09-07", "games": []})
    with pytest.raises(ValueError, match="dates differ"):
        validate(data, shared, "2026-09-06")


def test_rejects_invalid_bet_store(tmp_path):
    data, shared = _valid_runtime(tmp_path)
    _write(data, "bet_records.json", {"records": []})
    with pytest.raises(ValueError, match="must contain a list"):
        validate(data, shared, "2026-09-06")
