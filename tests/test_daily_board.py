from daily_board import coverage, merge_daily_board


def test_daily_board_covers_every_scheduled_game_and_verifies_results():
    schedule = {
        "games": [
            {"home": "A", "away": "B", "time": "18:00", "home_score": 3, "away_score": 1},
            {"home": "C", "away": "D", "time": "18:00", "home_score": None, "away_score": None},
        ]
    }
    predictions = {
        "games": [
            {"home": "A", "away": "B", "pick": "A", "win_probability": 61},
            {"home": "C", "away": "D", "pick": "D", "win_probability": 55},
        ]
    }
    board = merge_daily_board(schedule, predictions)
    assert coverage(board) == {"games": 2, "predicted": 2, "complete": True}
    assert board[0]["actual_result"] == "A"
    assert board[0]["verified"] is True
    assert board[1]["verified"] is None
