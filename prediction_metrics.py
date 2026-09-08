from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_RESULTS = {"勝": 1, "敗": 0}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _merge_rows(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {}
    for source in sources:
        for row in source or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("game_id") or "")
            if not key:
                key = "|".join(str(row.get(field) or "") for field in ("date", "opponent"))
            if key.strip("|"):
                merged[key] = row
    return list(merged.values())


def build_prediction_metrics(
    data_dir: Path,
    shared_data_dir: Path | None = None,
) -> dict[str, Any]:
    """Build verification metrics from the locally mounted production data.

    game_history is authoritative for completed games. Pregame probability is
    read from each history row first, then matched against pregame_predictions
    by date/opponent as a fallback. Draws and unfinished games are excluded.
    """
    history = _load_json(data_dir / "game_history.json")
    predictions = _load_json(data_dir / "pregame_predictions.json")

    if not isinstance(history, list):
        history = []
    if not isinstance(predictions, list):
        predictions = []

    shared_count = 0
    if shared_data_dir is not None and shared_data_dir.exists():
        shared_history = _load_json(shared_data_dir / "game_history.json")
        shared_predictions = _load_json(shared_data_dir / "pregame_predictions.json")
        if isinstance(shared_history, list):
            shared_count = len(shared_history)
            history = _merge_rows(history, shared_history)
        if isinstance(shared_predictions, list):
            predictions = _merge_rows(predictions, shared_predictions)

    prediction_index: dict[tuple[str, str], float] = {}
    for row in predictions:
        if not isinstance(row, dict):
            continue
        date = str(row.get("date") or "")
        opponent = str(row.get("opponent") or "")
        if not date or not opponent or opponent == "取得中":
            continue
        try:
            probability = float(row.get("probability"))
        except (TypeError, ValueError):
            continue
        prediction_index[(date, opponent)] = probability

    verified: list[dict[str, Any]] = []
    for game in history:
        if not isinstance(game, dict):
            continue
        result = str(game.get("result") or "")
        if result not in VALID_RESULTS:
            continue

        probability = game.get("pregame_probability")
        if probability is None:
            probability = prediction_index.get(
                (str(game.get("date") or ""), str(game.get("opponent") or ""))
            )
        try:
            probability = float(probability)
        except (TypeError, ValueError):
            continue
        if not 0 <= probability <= 100:
            continue

        actual = VALID_RESULTS[result]
        predicted_win = probability >= 50.0
        hit = predicted_win == bool(actual)
        p = probability / 100.0
        verified.append(
            {
                "game_id": game.get("game_id"),
                "date": game.get("date"),
                "opponent": game.get("opponent"),
                "probability": round(probability, 1),
                "result": result,
                "hit": hit,
                "brier": (p - actual) ** 2,
            }
        )

    count = len(verified)
    hits = sum(1 for row in verified if row["hit"])
    hit_rate = (hits / count * 100.0) if count else None
    brier_score = (
        sum(float(row["brier"]) for row in verified) / count if count else None
    )

    return {
        "status": "ready" if count else "waiting",
        "source": "research-shared-data" if shared_count else "local-production-data",
        "shared_count": shared_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_count": count,
        "hits": hits,
        "hit_rate": round(hit_rate, 1) if hit_rate is not None else None,
        "brier_score": round(brier_score, 6) if brier_score is not None else None,
        "games": verified,
    }


def write_prediction_metrics(
    data_dir: Path = Path("/app/data"),
    output_path: Path = Path("/app/static/prediction_metrics.json"),
) -> dict[str, Any]:
    payload = build_prediction_metrics(data_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp_path.replace(output_path)
    return payload


if __name__ == "__main__":
    write_prediction_metrics()
