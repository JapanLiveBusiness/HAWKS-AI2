from __future__ import annotations


def game_key(row: dict) -> tuple[str, str]:
    return str(row.get("home") or ""), str(row.get("away") or "")


def merge_daily_board(schedule: dict, predictions: dict) -> list[dict]:
    prediction_index = {
        game_key(row): row
        for row in predictions.get("games") or []
        if all(game_key(row))
    }
    merged = []
    for game in schedule.get("games") or []:
        row = dict(game)
        row.update(prediction_index.get(game_key(game), {}))
        home_score, away_score = game.get("home_score"), game.get("away_score")
        if home_score is not None and away_score is not None:
            if home_score == away_score:
                row["actual_result"] = "引分"
            else:
                row["actual_result"] = game.get("home") if home_score > away_score else game.get("away")
        else:
            row["actual_result"] = "未確定"
        pick = row.get("pick")
        row["verified"] = None if row["actual_result"] in {"未確定", "引分"} or not pick else pick == row["actual_result"]
        merged.append(row)
    return sorted(merged, key=lambda row: (str(row.get("time") or "99:99"), game_key(row)))


def coverage(board: list[dict]) -> dict:
    predicted = sum(1 for row in board if row.get("pick"))
    return {"games": len(board), "predicted": predicted, "complete": bool(board) and predicted == len(board)}
