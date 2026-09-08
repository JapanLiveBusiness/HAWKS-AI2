#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_atomic(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def parse_score(value):
    text = str(value or "")

    if "-" not in text:
        return None

    left, right = text.split("-", 1)

    try:
        return int(left), int(right)
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--archive",
        default="/app/data/ai_prediction_history.json",
    )

    parser.add_argument(
        "--schedule",
        default="/app/data/npb_today.json",
    )

    parser.add_argument(
        "--performance",
        default="/app/data/ai_prediction_performance.json",
    )

    args = parser.parse_args()

    archive_path = Path(args.archive)
    schedule_path = Path(args.schedule)
    performance_path = Path(args.performance)

    archive = load_json(
        archive_path,
        [],
    )

    schedule = load_json(
        schedule_path,
        {},
    )

    if not isinstance(archive, list):
        raise SystemExit("ERROR: archive invalid")

    schedule_date = str(
        schedule.get("date") or ""
    )

    final_index = {}

    for game in schedule.get("games") or []:
        if not isinstance(game, dict):
            continue

        if str(game.get("status") or "") != "final":
            continue

        home = str(game.get("home") or "")
        away = str(game.get("away") or "")

        if not home or not away:
            continue

        if (
            game.get("home_score") is None
            or game.get("away_score") is None
        ):
            continue

        final_index[
            (
                schedule_date,
                home,
                away,
            )
        ] = game

    settled_now = 0

    for row in archive:
        if not isinstance(row, dict):
            continue

        if row.get("status") == "final":
            continue

        key = (
            str(row.get("date") or ""),
            str(row.get("home") or ""),
            str(row.get("away") or ""),
        )

        game = final_index.get(key)

        if game is None:
            continue

        home_score = int(game["home_score"])
        away_score = int(game["away_score"])

        if home_score > away_score:
            actual_winner = row["home"]
            actual_home_win = 1
        elif home_score < away_score:
            actual_winner = row["away"]
            actual_home_win = 0
        else:
            # 引き分けは勝敗/Brierの評価対象外
            row["status"] = "draw"
            row["actual_home_score"] = home_score
            row["actual_away_score"] = away_score
            row["actual_winner"] = None
            row["settled_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            settled_now += 1
            continue

        try:
            home_probability = (
                float(
                    row.get(
                        "home_win_probability"
                    )
                )
                / 100.0
            )
        except (TypeError, ValueError):
            home_probability = None

        hit = (
            str(row.get("pick") or "")
            == actual_winner
        )

        brier = None

        if (
            home_probability is not None
            and 0 <= home_probability <= 1
        ):
            brier = (
                home_probability
                - actual_home_win
            ) ** 2

        predicted_score = parse_score(
            row.get("predicted_score")
        )

        score_error = None

        if predicted_score is not None:
            predicted_home, predicted_away = (
                predicted_score
            )

            # 両チームの絶対得点誤差の平均
            score_error = (
                abs(predicted_home - home_score)
                + abs(predicted_away - away_score)
            ) / 2.0

        row["status"] = "final"
        row["actual_home_score"] = home_score
        row["actual_away_score"] = away_score
        row["actual_winner"] = actual_winner
        row["hit"] = bool(hit)
        row["brier"] = (
            round(float(brier), 6)
            if brier is not None
            else None
        )
        row["score_error"] = (
            round(float(score_error), 2)
            if score_error is not None
            else None
        )
        row["settled_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        settled_now += 1

    save_atomic(
        archive_path,
        archive,
    )

    finals = [
        row
        for row in archive
        if isinstance(row, dict)
        and row.get("status") == "final"
    ]

    draws = [
        row
        for row in archive
        if isinstance(row, dict)
        and row.get("status") == "draw"
    ]

    hits = sum(
        1
        for row in finals
        if row.get("hit") is True
    )

    hit_rate = (
        hits / len(finals) * 100.0
        if finals
        else None
    )

    briers = [
        float(row["brier"])
        for row in finals
        if row.get("brier") is not None
    ]

    score_errors = [
        float(row["score_error"])
        for row in finals
        if row.get("score_error") is not None
    ]

    confidence_stats = {}

    for level in (
        "HIGH",
        "MEDIUM",
        "LOW",
    ):
        rows = [
            row
            for row in finals
            if row.get("confidence") == level
        ]

        level_hits = sum(
            1
            for row in rows
            if row.get("hit") is True
        )

        confidence_stats[level] = {
            "games": len(rows),
            "hits": level_hits,
            "hit_rate": (
                round(
                    level_hits
                    / len(rows)
                    * 100.0,
                    1,
                )
                if rows
                else None
            ),
        }

    performance = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "model": (
            finals[-1].get("model")
            if finals
            else None
        ),
        "settled_games": len(finals),
        "draws": len(draws),
        "hits": hits,
        "hit_rate": (
            round(hit_rate, 1)
            if hit_rate is not None
            else None
        ),
        "brier_score": (
            round(
                sum(briers) / len(briers),
                6,
            )
            if briers
            else None
        ),
        "score_mae": (
            round(
                sum(score_errors)
                / len(score_errors),
                2,
            )
            if score_errors
            else None
        ),
        "confidence": confidence_stats,
        "games": finals,
    }

    save_atomic(
        performance_path,
        performance,
    )

    print("SETTLED NOW:", settled_now)
    print("TOTAL FINALS:", len(finals))
    print("DRAWS:", len(draws))
    print("HITS:", hits)
    print(
        "HIT RATE:",
        performance["hit_rate"],
    )
    print(
        "BRIER:",
        performance["brier_score"],
    )
    print(
        "SCORE MAE:",
        performance["score_mae"],
    )
    print(
        "OUTPUT:",
        performance_path,
    )


if __name__ == "__main__":
    main()
