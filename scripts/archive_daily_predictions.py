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


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--predictions",
        default="/app/data/today_ai_predictions.json",
    )

    parser.add_argument(
        "--schedule",
        default="/app/data/npb_today.json",
    )

    parser.add_argument(
        "--archive",
        default="/app/data/ai_prediction_history.json",
    )

    args = parser.parse_args()

    prediction_path = Path(args.predictions)
    schedule_path = Path(args.schedule)
    archive_path = Path(args.archive)

    predictions = load_json(prediction_path, {})
    schedule = load_json(schedule_path, {})
    archive = load_json(archive_path, [])

    if not isinstance(archive, list):
        archive = []

    target_date = str(predictions.get("date") or "")

    if not target_date:
        raise SystemExit("ERROR: prediction date missing")

    if target_date != str(schedule.get("date") or ""):
        raise SystemExit("ERROR: schedule/prediction date mismatch")

    schedule_index = {}

    for game in schedule.get("games") or []:
        if not isinstance(game, dict):
            continue

        home = str(game.get("home") or "")
        away = str(game.get("away") or "")

        if home and away:
            schedule_index[(home, away)] = game

    existing_ids = {
        str(row.get("game_id"))
        for row in archive
        if isinstance(row, dict)
    }

    added = 0

    for pred in predictions.get("games") or []:
        if not isinstance(pred, dict):
            continue

        home = str(pred.get("home") or "")
        away = str(pred.get("away") or "")

        if not home or not away:
            continue

        game_id = f"{target_date}_{home}_{away}"

        # 最初の試合前予測を固定保存し、後から上書きしない
        if game_id in existing_ids:
            continue

        schedule_game = schedule_index.get(
            (home, away),
            {},
        )

        archive.append(
            {
                "game_id": game_id,
                "date": target_date,
                "time": schedule_game.get("time"),
                "venue": schedule_game.get("venue"),
                "home": home,
                "away": away,
                "pick": pred.get("pick"),
                "win_probability": pred.get(
                    "win_probability"
                ),
                "home_win_probability": pred.get(
                    "home_win_probability"
                ),
                "raw_home_win_probability": pred.get(
                    "raw_home_win_probability"
                ),
                "calibration_adjustment": pred.get(
                    "calibration_adjustment"
                ),
                "validation_sample_size": pred.get(
                    "validation_sample_size"
                ),
                "validation_home_win_rate": pred.get(
                    "validation_home_win_rate"
                ),
                "calibration_method": pred.get(
                    "calibration_method"
                ),
                "predicted_score": pred.get(
                    "predicted_score"
                ),
                "confidence": pred.get("confidence"),
                "model": pred.get("model")
                or predictions.get("model"),
                "training_games": predictions.get(
                    "training_games"
                ),
                "training_latest_date":
                    predictions.get(
                        "training_latest_date"
                    ),
                "locked": True,
                "saved_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
                "status": "pending",
                "actual_home_score": None,
                "actual_away_score": None,
                "actual_winner": None,
                "hit": None,
                "brier": None,
                "score_error": None,
                "settled_at": None,
            }
        )

        existing_ids.add(game_id)
        added += 1

    archive.sort(
        key=lambda row: (
            str(row.get("date") or ""),
            str(row.get("time") or ""),
            str(row.get("home") or ""),
            str(row.get("away") or ""),
        )
    )

    save_atomic(
        archive_path,
        archive,
    )

    print("DATE:", target_date)
    print("MODEL:", predictions.get("model"))
    print("ADDED:", added)
    print("TOTAL:", len(archive))
    print("OUTPUT:", archive_path)


if __name__ == "__main__":
    main()
