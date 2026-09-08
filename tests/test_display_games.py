from datetime import datetime
from zoneinfo import ZoneInfo

from display_games import select_display_games


JST = ZoneInfo("Asia/Tokyo")


def test_completed_games_remain_visible_until_midnight():
    payload = {
        "date": "2026-08-28",
        "games": [
            {"date": "2026-08-28", "status": "final", "home": "DeNA"},
        ],
    }
    games = select_display_games(
        payload,
        datetime(2026, 8, 28, 23, 59, tzinfo=JST),
    )
    assert [game["home"] for game in games] == ["DeNA"]


def test_next_slate_is_selected_after_midnight():
    payload = {
        "games": [
            {"date": "2026-08-28", "status": "final", "home": "DeNA"},
            {"date": "2026-08-29", "status": "scheduled", "home": "阪神"},
        ],
    }
    games = select_display_games(
        payload,
        datetime(2026, 8, 29, 0, 0, tzinfo=JST),
    )
    assert [game["home"] for game in games] == ["阪神"]


def test_stale_past_only_data_is_not_displayed():
    payload = {
        "date": "2026-08-27",
        "games": [{"status": "final", "home": "巨人"}],
    }
    assert select_display_games(
        payload,
        datetime(2026, 8, 28, 12, 0, tzinfo=JST),
    ) == []
