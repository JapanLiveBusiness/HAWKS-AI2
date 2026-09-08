from team_insights import league_standings, team_summary, upcoming_team_game


HISTORY = [
    {"date": "2026-04-01", "season": 2026, "home": "阪神", "away": "巨人", "home_score": 4, "away_score": 2},
    {"date": "2026-04-02", "season": 2026, "home": "巨人", "away": "阪神", "home_score": 3, "away_score": 3},
    {"date": "2026-04-03", "season": 2026, "home": "阪神", "away": "中日", "home_score": 1, "away_score": 2},
]


def test_team_summary_handles_home_away_draws_and_run_difference():
    summary = team_summary(HISTORY, "阪神", 2026)
    assert summary["played"] == 3
    assert (summary["wins"], summary["losses"], summary["draws"]) == (1, 1, 1)
    assert summary["run_diff"] == 1
    assert summary["games"][0]["opponent"] == "中日"


def test_league_standings_and_upcoming_prediction():
    standings = league_standings(HISTORY, "セ・リーグ", 2026)
    assert standings[0]["team"] == "中日"
    schedule = {"games": [{"date": "2026-09-04", "home": "阪神", "away": "巨人", "time": "18:00"}]}
    predictions = {"games": [{"home": "阪神", "away": "巨人", "pick": "阪神", "win_probability": 62}]}
    upcoming = upcoming_team_game(schedule, predictions, "巨人")
    assert upcoming["opponent"] == "阪神"
    assert upcoming["pick"] == "阪神"
