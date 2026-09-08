"""Read-only ranking from locked, pregame prediction history; no backfilling."""
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation


def load_calendar_predictions(*directories):
    rows = []
    for directory in directories:
        try:
            data = json.loads((directory / 'ai_prediction_history.json').read_text(encoding='utf-8'))
            if isinstance(data, list):
                rows.extend(r for r in data if isinstance(r, dict))
        except (OSError, ValueError):
            continue
    return rows


def probability(row, predictions):
    values = set()
    for p in predictions:
        if p.get('date') != row.get('date') or p.get('locked') is not True:
            continue
        if {p.get('home'), p.get('away')} != {row.get('team'), row.get('opponent')}:
            continue
        try:
            # Do not rank using predictions archived only after the game started.
            saved = datetime.fromisoformat(p['saved_at'])
            start = datetime.fromisoformat(f"{p['date']}T{p['time']}+09:00")
            if saved.tzinfo is None or saved >= start:
                continue
            home = p.get('home_win_probability')
            if home is not None:
                value = Decimal(str(home))
                if row['team'] != p['home']:
                    value = 100 - value
            elif p.get('pick') in (p.get('home'), p.get('away')):
                value = Decimal(str(p['win_probability']))
                if row['team'] != p['pick']:
                    value = 100 - value
            else:
                continue
            if value.is_finite() and 0 <= value <= 100:
                values.add(value)
        except (ValueError, TypeError, KeyError, InvalidOperation):
            continue
    return float(next(iter(values))) if len(values) == 1 else None


def ranked_bets(rows, predictions):
    ai, manual, unknown = [], [], []
    for row in rows:
        if row.get('virtual_edited') or row.get('source') in {'manual', 'manual-page'} or str(row.get('id') or '').startswith('manual-'):
            manual.append((row, 'M', None))
            continue
        prob = probability(row, predictions)
        if prob is None:
            unknown.append((row, '—', None))
        else:
            ai.append((row, prob))
    ai.sort(key=lambda pair: -pair[1])
    result = []
    rank, previous = 0, None
    for index, (row, prob) in enumerate(ai, 1):
        if prob != previous:
            rank = index
        result.append((row, str(rank), prob))
        previous = prob
    return result + manual + unknown
