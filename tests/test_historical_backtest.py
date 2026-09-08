import json

from scripts.backtest_historical_models import build_point_in_time_features, load_games, run


def test_walk_forward_uses_only_earlier_seasons(tmp_path):
    rows = []
    for season in (2020, 2021, 2022):
        for index in range(12):
            rows.append(
                {
                    "date": f"{season}-04-{index + 1:02d}",
                    "home": "A" if index % 2 == 0 else "B",
                    "away": "B" if index % 2 == 0 else "A",
                    "home_score": 4 if index % 3 else 2,
                    "away_score": 2 if index % 3 else 4,
                    "venue": "Test",
                    "game_type": "regular",
                    "season": season,
                }
            )
    path = tmp_path / "games.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    features = build_point_in_time_features(load_games(path))
    summaries, predictions = run(features)
    assert {row["season"] for row in summaries} == {2021, 2022}
    assert all(row["train_through"] == row["season"] - 1 for row in summaries)
    assert len(predictions) == 24 * 3
