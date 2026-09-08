#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from backtest_historical_models import (
    FEATURES,
    build_point_in_time_features,
    load_games,
    logistic_model,
)
from prediction_results import calibrate_home_probability, load_historical_validation

MODEL = "logistic_rolling_v1"


def mean(values, size, default):
    values = list(values)[-size:]
    return float(np.mean(values)) if values else float(default)


def confidence_label(probability):
    if probability >= 65:
        return "HIGH"
    if probability >= 58:
        return "MEDIUM"
    return "LOW"


def score_prediction(
    home_history,
    away_history,
    pick,
    home,
    away,
):
    home_for = mean((x["rf"] for x in home_history), 10, 3.5)
    home_against = mean((x["ra"] for x in home_history), 10, 3.5)

    away_for = mean((x["rf"] for x in away_history), 10, 3.5)
    away_against = mean((x["ra"] for x in away_history), 10, 3.5)

    expected_home = (home_for + away_against) / 2
    expected_away = (away_for + home_against) / 2

    home_score = max(0, int(round(expected_home)))
    away_score = max(0, int(round(expected_away)))

    # 勝敗予測と予想スコアの矛盾を避ける
    if pick == home and home_score <= away_score:
        home_score = away_score + 1

    if pick == away and away_score <= home_score:
        away_score = home_score + 1

    return f"{home_score}-{away_score}"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--schedule",
        default="/app/data/npb_today.json",
    )

    parser.add_argument(
        "--history",
        default="/app/data/historical_games_2017_2026.json",
    )

    parser.add_argument(
        "--official-ranges",
        default="/app/data/hawks_games_context.json",
    )

    parser.add_argument(
        "--output",
        default="/app/data/today_ai_predictions.json",
    )

    parser.add_argument(
        "--validation",
        default="/app/data/historical_backtest_predictions.csv",
    )

    args = parser.parse_args()

    schedule_path = Path(args.schedule)
    history_path = Path(args.history)
    ranges_path = Path(args.official_ranges)
    output_path = Path(args.output)
    validation_path = Path(args.validation)

    today = json.loads(
        schedule_path.read_text(encoding="utf-8")
    )

    target_date_text = str(today.get("date") or "")

    if not target_date_text:
        raise SystemExit("ERROR: schedule has no date")

    target_date = pd.Timestamp(target_date_text)

    games = load_games(
        history_path,
        ranges_path,
    )

    features = build_point_in_time_features(games)

    train = features[
        features["date"] < target_date
    ].copy()

    if train.empty:
        raise SystemExit("ERROR: no training games")

    model = logistic_model()

    model.fit(
        train[FEATURES],
        train["target"].astype(int),
    )

    raw = games[
        games["date"] < target_date
    ].copy()

    raw = raw.sort_values(
        ["date", "home", "away"]
    )

    history = defaultdict(list)
    all_history = defaultdict(list)
    h2h = defaultdict(list)
    elo = defaultdict(lambda: 1500.0)

    prior_season = {}

    for season in sorted(raw["season"].unique()):
        previous = raw[
            raw["season"] == season - 1
        ]

        if previous.empty:
            continue

        team_rows = pd.concat(
            [
                previous[
                    ["home", "home_score", "away_score"]
                ].rename(
                    columns={
                        "home": "team",
                        "home_score": "rf",
                        "away_score": "ra",
                    }
                ),
                previous[
                    ["away", "away_score", "home_score"]
                ].rename(
                    columns={
                        "away": "team",
                        "away_score": "rf",
                        "home_score": "ra",
                    }
                ),
            ],
            ignore_index=True,
        )

        for team, rows in team_rows.groupby("team"):
            prior_season[(int(season), team)] = (
                float(
                    (
                        rows["rf"] > rows["ra"]
                    ).mean()
                ),
                float(
                    (
                        rows["rf"] - rows["ra"]
                    ).mean()
                ),
            )

    for row in raw.itertuples(index=False):
        home = row.home
        away = row.away
        season = int(row.season)

        win = float(
            row.home_score > row.away_score
        )

        margin = float(
            row.home_score - row.away_score
        )

        home_record = {
            "date": row.date,
            "win": win,
            "margin": margin,
            "rf": row.home_score,
            "ra": row.away_score,
        }

        away_record = {
            "date": row.date,
            "win": 1 - win,
            "margin": -margin,
            "rf": row.away_score,
            "ra": row.home_score,
        }

        history[(season, home)].append(
            home_record
        )

        history[(season, away)].append(
            away_record
        )

        all_history[home].append(
            home_record
        )

        all_history[away].append(
            away_record
        )

        h2h[(home, away)].append(win)
        h2h[(away, home)].append(1 - win)

        expected = (
            1
            / (
                1
                + 10
                ** (
                    (
                        elo[away]
                        - elo[home]
                        - 35
                    )
                    / 400
                )
            )
        )

        change = 20 * (win - expected)

        elo[home] += change
        elo[away] -= change

    rows_for_prediction = []
    state_for_scores = {}

    for game in today.get("games") or []:
        home = str(game.get("home") or "")
        away = str(game.get("away") or "")
        venue = str(game.get("venue") or "")

        if not home or not away:
            continue

        season = int(target_date.year)

        home_history = history[(season, home)]
        away_history = history[(season, away)]

        state_for_scores[
            (home, away)
        ] = (
            home_history,
            away_history,
        )

        home_prior = prior_season.get(
            (season, home),
            (0.5, 0.0),
        )

        away_prior = prior_season.get(
            (season, away),
            (0.5, 0.0),
        )

        home_last = (
            all_history[home][-1]["date"]
            if all_history[home]
            else None
        )

        away_last = (
            all_history[away][-1]["date"]
            if all_history[away]
            else None
        )

        home_rest = (
            min(
                max(
                    (target_date - home_last).days - 1,
                    0,
                ),
                14,
            )
            if home_last is not None
            else 3
        )

        away_rest = (
            min(
                max(
                    (target_date - away_last).days - 1,
                    0,
                ),
                14,
            )
            if away_last is not None
            else 3
        )

        pair = h2h[(home, away)]

        rows_for_prediction.append(
            {
                "home": home,
                "away": away,
                "venue": venue,
                "month": str(target_date.month),
                "home_adv": 1.0,
                "elo_diff":
                    elo[home] - elo[away],
                "prev_win_diff":
                    home_prior[0] - away_prior[0],
                "prev_run_diff":
                    home_prior[1] - away_prior[1],
                "rest_diff":
                    home_rest - away_rest,
                "win5_diff":
                    mean(
                        (
                            x["win"]
                            for x in home_history
                        ),
                        5,
                        0.5,
                    )
                    - mean(
                        (
                            x["win"]
                            for x in away_history
                        ),
                        5,
                        0.5,
                    ),
                "win10_diff":
                    mean(
                        (
                            x["win"]
                            for x in home_history
                        ),
                        10,
                        0.5,
                    )
                    - mean(
                        (
                            x["win"]
                            for x in away_history
                        ),
                        10,
                        0.5,
                    ),
                "run5_diff":
                    mean(
                        (
                            x["margin"]
                            for x in home_history
                        ),
                        5,
                        0.0,
                    )
                    - mean(
                        (
                            x["margin"]
                            for x in away_history
                        ),
                        5,
                        0.0,
                    ),
                "run10_diff":
                    mean(
                        (
                            x["margin"]
                            for x in home_history
                        ),
                        10,
                        0.0,
                    )
                    - mean(
                        (
                            x["margin"]
                            for x in away_history
                        ),
                        10,
                        0.0,
                    ),
                "off10_diff":
                    mean(
                        (
                            x["rf"]
                            for x in home_history
                        ),
                        10,
                        3.5,
                    )
                    - mean(
                        (
                            x["rf"]
                            for x in away_history
                        ),
                        10,
                        3.5,
                    ),
                "def10_diff":
                    mean(
                        (
                            x["ra"]
                            for x in away_history
                        ),
                        10,
                        3.5,
                    )
                    - mean(
                        (
                            x["ra"]
                            for x in home_history
                        ),
                        10,
                        3.5,
                    ),
                "h2h_diff":
                    mean(pair, 10, 0.5) - 0.5,
            }
        )

    if not rows_for_prediction:
        raise SystemExit(
            "ERROR: no prediction rows"
        )

    prediction_frame = pd.DataFrame(
        rows_for_prediction
    )

    home_probabilities = (
        model.predict_proba(
            prediction_frame[FEATURES]
        )[:, 1]
    )

    predictions = []
    validation = load_historical_validation(
        validation_path,
        season=int(target_date.year),
        model="logistic_rolling",
    )

    for row, home_probability in zip(
        rows_for_prediction,
        home_probabilities,
    ):
        home_probability = float(
            home_probability
        )

        calibration = calibrate_home_probability(
            home_probability * 100.0,
            validation,
            target_date_text,
        )
        calibrated_home_probability = (
            float(calibration["home_win_probability"])
            / 100.0
        )
        away_probability = 1.0 - calibrated_home_probability

        if calibrated_home_probability >= away_probability:
            pick = row["home"]
            probability = calibrated_home_probability * 100
        else:
            pick = row["away"]
            probability = away_probability * 100

        home_history, away_history = (
            state_for_scores[
                (row["home"], row["away"])
            ]
        )

        predictions.append(
            {
                "home": row["home"],
                "away": row["away"],
                "pick": pick,
                "win_probability":
                    round(probability, 1),
                "home_win_probability":
                    round(
                        calibrated_home_probability * 100,
                        1,
                    ),
                "raw_home_win_probability":
                    calibration["raw_home_win_probability"],
                "calibration_adjustment":
                    calibration["calibration_adjustment"],
                "validation_sample_size":
                    calibration["validation_sample_size"],
                "validation_home_win_rate":
                    calibration["validation_home_win_rate"],
                "calibration_method":
                    calibration["calibration_method"],
                "predicted_score":
                    score_prediction(
                        home_history,
                        away_history,
                        pick,
                        row["home"],
                        row["away"],
                    ),
                "confidence":
                    confidence_label(
                        probability
                    ),
                "model": MODEL,
            }
        )

    predictions.sort(
        key=lambda x: x["win_probability"],
        reverse=True,
    )

    for rank, game in enumerate(
        predictions,
        1,
    ):
        game["rank"] = rank

    payload = {
        "date": target_date_text,
        "updated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "model": MODEL,
        "training_games":
            int(len(train)),
        "training_latest_date":
            train["date"]
            .max()
            .strftime("%Y-%m-%d"),
        "validation_games": len(validation),
        "validation_start_date": (
            validation[0]["date"] if validation else None
        ),
        "validation_latest_date": (
            validation[-1]["date"] if validation else None
        ),
        "calibration": "season_10point_empirical_bayes",
        "games": predictions,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )

    temp.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    temp.replace(output_path)

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
