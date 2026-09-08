from datetime import date
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from bet_store import append_bet, load_bets, DuplicateBetError
from manual_bet_defaults import entry_defaults, load_entry_games


GAME = {"date": "2026-08-20", "home": "阪神", "away": "ヤクルト", "time": "18:00",
        "status": "final", "home_score": 1, "away_score": 4, "home_handicap": "0.6"}
RECORD = {"date": "2026-08-20", "time": "18:00", "team": "阪神", "opponent": "ヤクルト",
          "bet_amount": 250000, "handicap": 0.6, "status": "final", "team_score": 1,
          "opponent_score": 4, "memo": "", "source": "manual"}


def _append_worker(args):
    path, i = args
    try:
        append_bet(Path(path), dict(RECORD, id=f"retry-{i}"))
        return True
    except DuplicateBetError:
        return False


def test_concurrent_resubmission_only_writes_one_record(tmp_path):
    path = tmp_path / "bets.json"
    with ProcessPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(_append_worker, [(str(path), i) for i in range(8)]))
    assert sum(results) == 1
    assert len(load_bets(path)) == 1


def test_duplicate_across_entry_pages_and_user_isolation(tmp_path):
    path = tmp_path / "one.json"
    append_bet(path, dict(RECORD, id="one"))
    with pytest.raises(DuplicateBetError):
        append_bet(path, dict(RECORD, id="two", source="manual-page", created_at="later"))
    append_bet(path, dict(RECORD, id="different", bet_amount=10000))
    append_bet(tmp_path / "other.json", dict(RECORD, id="other"))
    assert len(load_bets(path)) == 2


def test_final_defaults_follow_selected_team_and_handicap_sign():
    home = entry_defaults(GAME, "阪神")
    away = entry_defaults(GAME, "ヤクルト")
    assert (home["team_score"], home["opponent_score"], home["handicap"]) == (1, 4, 0.6)
    assert (away["team_score"], away["opponent_score"], away["handicap"]) == (4, 1, -0.6)
    assert home["status"] == away["status"] == "確定"


def test_missing_values_and_live_scores_are_not_confirmed_zeros():
    missing = entry_defaults(dict(GAME, home_score=None, home_handicap=None), "阪神")
    assert missing["team_score"] is None and missing["handicap"] is None
    live = entry_defaults(dict(GAME, status="live"), "阪神")
    assert live["status"] == "未確定" and live["team_score"] is None
    zero = entry_defaults(dict(GAME, home_score=0, home_handicap=0), "阪神")
    assert zero["team_score"] == 0 and zero["handicap"] == 0


def test_stale_past_cache_refresh_and_reversed_handicap_source(monkeypatch):
    monkeypatch.setattr("manual_bet_defaults.load_npb_schedule_day", lambda *a, **k: [dict(GAME, status="scheduled", home_score=None, away_score=None, home_handicap=None)])
    monkeypatch.setattr("manual_bet_defaults.fetch_npb_schedule_day", lambda *a, **k: [dict(GAME)])
    monkeypatch.setattr("manual_bet_defaults.fetch_daily_handicaps", lambda *a, **k: [dict(GAME, home="ヤクルト", away="阪神", home_handicap=None, away_handicap="1.2")])
    games = load_entry_games(date(2026, 8, 20), (), today=date(2026, 9, 6))
    assert games[0]["status"] == "final"
    assert games[0]["home_score"] == 1
    assert games[0]["home_handicap"] == "1.2"


def test_persisted_final_autofills_during_network_outage(tmp_path, monkeypatch):
    import json
    (tmp_path / "npb_results_cache.json").write_text(json.dumps({"games": [GAME]}), encoding="utf-8")
    monkeypatch.setattr("manual_bet_defaults.load_npb_schedule_day", lambda *a, **k: [dict(GAME, status="scheduled", home_score=None, away_score=None, home_handicap=None)])
    monkeypatch.setattr("manual_bet_defaults.fetch_npb_schedule_day", lambda *a, **k: [])
    monkeypatch.setattr("manual_bet_defaults.fetch_daily_handicaps", lambda *a, **k: [])
    games = load_entry_games(date(2026, 8, 20), [tmp_path / "npb_today.json"], today=date(2026, 9, 6))
    defaults = entry_defaults(games[0], "阪神")
    assert (defaults["status"], defaults["team_score"], defaults["opponent_score"], defaults["handicap"]) == ("確定", 1, 4, 0.6)


def make_app(tmp_path, monkeypatch, games=None):
    import manual_bet_form
    monkeypatch.setattr(manual_bet_form, "_games", lambda *a: deepcopy(games if games is not None else [GAME]))
    path = tmp_path / "ui.json"
    source = f'''from pathlib import Path
from manual_bet_form import render_manual_bet_form
render_manual_bet_form(Path({str(path)!r}), (), prefix="test")
'''
    app = AppTest.from_string(source).run()
    assert not app.exception
    return app, path


def test_form_autofill_switch_sides_and_repeat_submission(tmp_path, monkeypatch):
    app, path = make_app(tmp_path, monkeypatch)
    assert app.number_input(key="test_team_score").value == 1
    assert app.number_input(key="test_opponent_score").value == 4
    assert app.number_input(key="test_handicap").value == 0.6
    assert app.selectbox(key="test_status").value == "確定"
    [x for x in app.selectbox if x.label == "BET先 / チーム"][0].select("ヤクルト").run()
    assert app.number_input(key="test_team_score").value == 4
    assert app.number_input(key="test_handicap").value == -0.6
    app.button[0].click().run()
    assert not app.exception
    assert len(load_bets(path)) == 1
    app.button[0].click().run()
    assert not app.exception
    assert len(load_bets(path)) == 1
    assert any("登録済み" in e.value for e in app.error)


def test_changing_match_clears_stale_scores_and_handicap(tmp_path, monkeypatch):
    games = [GAME, {"home": "巨人", "away": "中日", "time": "14:00", "status": "scheduled"}]
    app, path = make_app(tmp_path, monkeypatch, games)
    [x for x in app.selectbox if x.label == "開催試合"][0].select(1).run()
    assert not app.exception
    assert app.number_input(key="test_team_score").value is None
    assert app.number_input(key="test_opponent_score").value is None
    assert app.number_input(key="test_handicap").value is None
    assert app.selectbox(key="test_status").value == "未確定"
    app.button[0].click().run()
    assert load_bets(path) == []


def test_final_without_scores_cannot_be_saved(tmp_path, monkeypatch):
    app, path = make_app(tmp_path, monkeypatch, [dict(GAME, home_score=None)])
    app.button[0].click().run()
    assert not app.exception
    assert load_bets(path) == []
    assert any("得点が必要" in e.value for e in app.error)
