#!/usr/bin/env python3
"""Leakage-safe, season-by-season NPB model comparison.

Every season is evaluated with models trained only on earlier seasons.  The
generated JSON is small enough for the Streamlit app to read at runtime, while
the full prediction CSV remains available for audits.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

NUMERIC = [
    "elo_diff", "prev_win_diff", "prev_run_diff", "rest_diff",
    "win5_diff", "win10_diff", "run5_diff", "run10_diff",
    "off10_diff", "def10_diff", "h2h_diff", "home_adv",
]
CATEGORICAL = ["home", "away", "venue", "month"]
FEATURES = NUMERIC + CATEGORICAL
OFFICIAL_TYPES = {"regular", "interleague", "climax", "japan_series"}


def _mean(values, size, default):
    values = list(values)[-size:]
    return float(np.mean(values)) if values else float(default)


def official_ranges(path: Path | None) -> dict[int, tuple[pd.Timestamp, pd.Timestamp]]:
    if path is None or not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    ranges = {}
    for season in sorted({int(row.get("season", 0)) for row in rows if row.get("season")}):
        dates = [
            pd.Timestamp(row["date"])
            for row in rows
            if int(row.get("season", 0)) == season
            and row.get("game_type") in {"regular", "interleague"}
            and row.get("date")
        ]
        if dates:
            ranges[season] = (min(dates), max(dates))
    return ranges


def load_games(path: Path, range_path: Path | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(json.loads(path.read_text(encoding="utf-8")))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    game_type = frame.get(
        "game_type",
        pd.Series(index=frame.index, dtype="object"),
    )

    has_type = game_type.notna()

    typed_official = (
        has_type
        & game_type.isin(OFFICIAL_TYPES)
    )

    # historical_games_2017_2026.json には、
    # game_type 未設定の正式なNPB試合も含まれる。
    # ホークス専用の context 期間で全12球団を切らない。
    untyped_official = ~has_type

    frame = frame[
        typed_official | untyped_official
    ].copy()
    frame = frame.dropna(subset=["date", "home", "away", "home_score", "away_score"])
    frame = frame.sort_values(["date", "home", "away"]).drop_duplicates(
        ["date", "home", "away"], keep="last"
    )
    frame["season"] = frame["date"].dt.year
    frame["margin"] = frame["home_score"].astype(float) - frame["away_score"].astype(float)
    frame = frame[frame["margin"] != 0].copy()
    frame["target"] = (frame["margin"] > 0).astype(int)
    return frame.reset_index(drop=True)


def build_point_in_time_features(games: pd.DataFrame) -> pd.DataFrame:
    history = defaultdict(list)
    all_history = defaultdict(list)
    h2h = defaultdict(list)
    elo = defaultdict(lambda: 1500.0)
    prior_season = {}
    output = []

    for season in sorted(games["season"].unique()):
        previous = games[games["season"] == season - 1]
        if not previous.empty:
            team_rows = pd.concat(
                [
                    previous[["home", "home_score", "away_score"]].rename(
                        columns={"home": "team", "home_score": "rf", "away_score": "ra"}
                    ),
                    previous[["away", "away_score", "home_score"]].rename(
                        columns={"away": "team", "away_score": "rf", "home_score": "ra"}
                    ),
                ],
                ignore_index=True,
            )
            for team, rows in team_rows.groupby("team"):
                prior_season[(season, team)] = (
                    float((rows["rf"] > rows["ra"]).mean()),
                    float((rows["rf"] - rows["ra"]).mean()),
                )

    for row in games.itertuples(index=False):
        home, away, season = row.home, row.away, int(row.season)
        home_history = history[(season, home)]
        away_history = history[(season, away)]
        home_prior = prior_season.get((season, home), (0.5, 0.0))
        away_prior = prior_season.get((season, away), (0.5, 0.0))
        home_last = all_history[home][-1]["date"] if all_history[home] else None
        away_last = all_history[away][-1]["date"] if all_history[away] else None
        home_rest = min(max((row.date - home_last).days - 1, 0), 14) if home_last is not None else 3
        away_rest = min(max((row.date - away_last).days - 1, 0), 14) if away_last is not None else 3
        pair = h2h[(home, away)]

        values = row._asdict()
        values.update(
            {
                "month": str(row.date.month),
                "home_adv": 1.0,
                "elo_diff": elo[home] - elo[away],
                "prev_win_diff": home_prior[0] - away_prior[0],
                "prev_run_diff": home_prior[1] - away_prior[1],
                "rest_diff": home_rest - away_rest,
                "win5_diff": _mean((x["win"] for x in home_history), 5, 0.5)
                - _mean((x["win"] for x in away_history), 5, 0.5),
                "win10_diff": _mean((x["win"] for x in home_history), 10, 0.5)
                - _mean((x["win"] for x in away_history), 10, 0.5),
                "run5_diff": _mean((x["margin"] for x in home_history), 5, 0.0)
                - _mean((x["margin"] for x in away_history), 5, 0.0),
                "run10_diff": _mean((x["margin"] for x in home_history), 10, 0.0)
                - _mean((x["margin"] for x in away_history), 10, 0.0),
                "off10_diff": _mean((x["rf"] for x in home_history), 10, 3.5)
                - _mean((x["rf"] for x in away_history), 10, 3.5),
                "def10_diff": _mean((x["ra"] for x in away_history), 10, 3.5)
                - _mean((x["ra"] for x in home_history), 10, 3.5),
                "h2h_diff": _mean(pair, 10, 0.5) - 0.5,
            }
        )
        output.append(values)

        win = float(row.margin > 0)
        home_record = {"date": row.date, "win": win, "margin": row.margin, "rf": row.home_score, "ra": row.away_score}
        away_record = {"date": row.date, "win": 1 - win, "margin": -row.margin, "rf": row.away_score, "ra": row.home_score}
        home_history.append(home_record)
        away_history.append(away_record)
        all_history[home].append(home_record)
        all_history[away].append(away_record)
        h2h[(home, away)].append(win)
        h2h[(away, home)].append(1 - win)
        expected = 1 / (1 + 10 ** ((elo[away] - elo[home] - 35) / 400))
        change = 20 * (win - expected)
        elo[home] += change
        elo[away] -= change

    return pd.DataFrame(output)


def logistic_model():
    prep = ColumnTransformer(
        [
            ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC),
            ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
        ]
    )
    return Pipeline([("prepare", prep), ("model", LogisticRegression(C=0.3, max_iter=3000))])


def gradient_model():
    prep = ColumnTransformer(
        [
            ("numeric", SimpleImputer(strategy="median"), NUMERIC),
            ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1))]), CATEGORICAL),
        ]
    )
    return Pipeline(
        [
            ("prepare", prep),
            ("model", HistGradientBoostingClassifier(max_iter=180, max_leaf_nodes=15, min_samples_leaf=25, l2_regularization=2, random_state=42)),
        ]
    )


def metrics(target, probability):
    probability = np.asarray(probability, dtype=float)
    prediction = (probability >= 0.5).astype(int)
    return {
        "games": int(len(target)),
        "accuracy": round(float(accuracy_score(target, prediction) * 100), 2),
        "brier": round(float(brier_score_loss(target, probability)), 4),
        "log_loss": round(float(log_loss(target, probability, labels=[0, 1])), 4),
    }


def run(features: pd.DataFrame):
    summaries = []
    predictions = []
    seasons = sorted(int(value) for value in features["season"].unique())
    for season in seasons[1:]:
        train = features[features["season"] < season]
        test = features[features["season"] == season].copy()
        if train.empty or test.empty:
            continue

        baseline_probability = np.full(len(test), float(train["target"].mean()))
        model_probabilities = {"historical_baseline": baseline_probability}
        for name, model in (("logistic_rolling", logistic_model()), ("gradient_rolling", gradient_model())):
            model.fit(train[FEATURES], train["target"].astype(int))
            model_probabilities[name] = model.predict_proba(test[FEATURES])[:, 1]

        for name, probability in model_probabilities.items():
            score = metrics(test["target"].astype(int), probability)
            summaries.append({"season": season, "model": name, "train_through": season - 1, **score})
            for game, prob in zip(test.itertuples(index=False), probability):
                predictions.append(
                    {
                        "date": game.date.strftime("%Y-%m-%d"),
                        "season": season,
                        "home": game.home,
                        "away": game.away,
                        "actual_home_win": int(game.target),
                        "model": name,
                        "home_win_probability": round(float(prob), 6),
                        "correct": bool((prob >= 0.5) == bool(game.target)),
                    }
                )
    return summaries, predictions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", default="data/historical_games_2017_2026.json")
    parser.add_argument("--official-ranges", default="data/hawks_games_context.json")
    parser.add_argument("--report", default="data/historical_backtest_report.json")
    parser.add_argument("--predictions", default="data/historical_backtest_predictions.csv")
    args = parser.parse_args()

    raw_games = json.loads(Path(args.games).read_text(encoding="utf-8"))
    games = load_games(Path(args.games), Path(args.official_ranges))
    features = build_point_in_time_features(games)
    summaries, predictions = run(features)
    summary_frame = pd.DataFrame(summaries)
    overall = []
    for model, rows in summary_frame.groupby("model"):
        weights = rows["games"].to_numpy()
        overall.append(
            {
                "model": model,
                "games": int(weights.sum()),
                "accuracy": round(float(np.average(rows["accuracy"], weights=weights)), 2),
                "brier": round(float(np.average(rows["brier"], weights=weights)), 4),
                "log_loss": round(float(np.average(rows["log_loss"], weights=weights)), 4),
            }
        )
    recommended = min(overall, key=lambda row: (row["brier"], -row["accuracy"]))["model"]
    payload = {
        "method": "season_walk_forward",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": Path(args.games).name,
        "source_games": int(len(raw_games)),
        "evaluated_games": int(len(games)),
        "source_start": games["date"].min().strftime("%Y-%m-%d"),
        "source_end": games["date"].max().strftime("%Y-%m-%d"),
        "evaluated_seasons": sorted(summary_frame["season"].unique().astype(int).tolist()),
        "recommended_model": recommended,
        "overall": sorted(overall, key=lambda row: row["model"]),
        "by_season": summaries,
        "notes": [
            "Each season is tested using only earlier seasons for training.",
            "Draws are excluded from binary win/loss metrics.",
            "Future-season and final-season aggregate features are not used.",
        ],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(predictions).to_csv(args.predictions, index=False, encoding="utf-8-sig")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
