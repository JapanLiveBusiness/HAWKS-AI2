import json
from datetime import date

from daily_data import load_current_daily_json


def _write(directory, name, payload):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_prefers_current_shared_data_over_stale_production(tmp_path):
    shared = tmp_path / "shared"
    production = tmp_path / "production"
    _write(shared, "today.json", {"date": "2026-09-05", "source": "shared"})
    _write(production, "today.json", {"date": "2026-09-04", "source": "production"})

    payload = load_current_daily_json(
        "today.json",
        {},
        today=date(2026, 9, 5),
        directories=(shared, production),
    )

    assert payload["source"] == "shared"


def test_never_returns_a_past_daily_slate(tmp_path):
    production = tmp_path / "production"
    _write(production, "today.json", {"date": "2026-09-04", "games": [1]})

    payload = load_current_daily_json(
        "today.json",
        {"games": []},
        today=date(2026, 9, 5),
        directories=(production,),
    )

    assert payload == {"games": []}


def test_prefers_configured_order_when_dates_match(tmp_path):
    shared = tmp_path / "shared"
    production = tmp_path / "production"
    _write(shared, "today.json", {"date": "2026-09-05", "source": "shared"})
    _write(production, "today.json", {"date": "2026-09-05", "source": "production"})

    payload = load_current_daily_json(
        "today.json",
        {},
        today=date(2026, 9, 5),
        directories=(shared, production),
    )

    assert payload["source"] == "shared"
