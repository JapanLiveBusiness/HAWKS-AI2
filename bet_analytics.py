"""Pure helpers for BET summary metrics and history ordering."""

from datetime import date, datetime, timedelta


SORT_OPTIONS = (
    "新しい日付順",
    "古い日付順",
    "収支が高い順",
    "収支が低い順",
    "BET額が高い順",
)
WIN_PROFIT_RATE = 0.90


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def bet_amount(record):
    """Return the explicit stake or derive it from legacy bet units."""
    if record.get("bet_amount") is not None:
        return _number(record.get("bet_amount"))
    return abs(_number(record.get("bet_units"))) * 10000


def settle_bet(team_score, opponent_score, handicap=0):
    """Settle a bet after subtracting the handicap from the selected team."""
    adjusted_score = _number(team_score) - _number(handicap)
    opponent = _number(opponent_score)
    margin = adjusted_score - opponent

    if abs(margin) < 1e-9:
        result = "push"
    elif margin > 0:
        result = "win"
    else:
        result = "loss"

    return round(adjusted_score, 3), result


def profit_for_result(result, amount):
    """Return profit using the configured 90% win settlement rule."""
    stake = abs(_number(amount))
    if result == "win":
        return int(round(stake * WIN_PROFIT_RATE))
    if result == "loss":
        return -int(round(stake))
    return 0


def profit_for_record(record):
    """Return canonical profit, recalculating settled legacy records."""
    if record.get("status") == "final" and record.get("result") in {
        "win", "loss", "push",
    }:
        return profit_for_result(record.get("result"), bet_amount(record))
    return int(round(_number(record.get("profit"))))


def calculate_hit_rate(records):
    """Return wins, decided bets and hit rate; pushes/pending are excluded."""
    results = [
        record.get("result")
        for record in records
        if record.get("status") == "final"
        and record.get("result") in {"win", "loss"}
    ]
    wins = results.count("win")
    decided = len(results)
    rate = (wins / decided * 100.0) if decided else None
    return wins, decided, rate


def weekly_bet_summary(records, reference_date=None):
    """Calculate the current Monday-Sunday BET summary from live records."""
    if reference_date is None:
        reference_date = date.today()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    week_start = reference_date - timedelta(days=reference_date.weekday())
    week_end = week_start + timedelta(days=6)
    weekly = []
    for record in records:
        try:
            record_date = date.fromisoformat(str(record.get("date") or ""))
        except ValueError:
            continue
        if week_start <= record_date <= week_end:
            weekly.append(record)

    final = [record for record in weekly if record.get("status") == "final"]
    pending = [record for record in weekly if record.get("status") != "final"]
    wins, decided, hit_rate = calculate_hit_rate(final)
    total_profit = sum(profit_for_record(record) for record in final)
    total_stake = sum(bet_amount(record) for record in final)

    return {
        "week_start": week_start,
        "week_end": week_end,
        "profit": total_profit,
        "final_count": len(final),
        "wins": wins,
        "losses": sum(record.get("result") == "loss" for record in final),
        "pushes": sum(record.get("result") == "push" for record in final),
        "hit_rate": hit_rate,
        "roi": (total_profit / total_stake * 100.0) if total_stake else None,
        "pending_count": len(pending),
        "pending_amount": int(sum(bet_amount(record) for record in pending)),
        "decided_count": decided,
    }


def sort_bets(records, option):
    """Return a new list ordered by the selected history sort option."""
    bets = list(records)
    date_key = lambda bet: (
        str(bet.get("date", "")),
        str(bet.get("time", "")),
        str(bet.get("created_at", "")),
    )

    if option == "古い日付順":
        return sorted(bets, key=date_key)
    if option == "収支が高い順":
        return sorted(bets, key=profit_for_record, reverse=True)
    if option == "収支が低い順":
        return sorted(bets, key=profit_for_record)
    if option == "BET額が高い順":
        return sorted(bets, key=bet_amount, reverse=True)
    return sorted(bets, key=date_key, reverse=True)
