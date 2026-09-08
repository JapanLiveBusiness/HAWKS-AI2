from datetime import datetime
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")


def select_display_games(payload, now=None):
    """Return today's games, or the nearest future slate, in Japan time.

    A game's status is deliberately ignored: completed games remain visible
    until the Japanese calendar day changes.
    """
    now = now or datetime.now(JST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)

    today = now.date().isoformat()
    games = list((payload or {}).get("games", []) or [])
    dated_games = {}

    for game in games:
        game_date = str(game.get("date") or (payload or {}).get("date") or "")
        if game_date:
            dated_games.setdefault(game_date, []).append(game)

    if today in dated_games:
        return dated_games[today]

    future_dates = sorted(date for date in dated_games if date > today)
    if future_dates:
        return dated_games[future_dates[0]]

    return []
