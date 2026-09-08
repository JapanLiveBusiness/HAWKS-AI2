from datetime import date
import re

from handenomori_client import fetch_member_page
from bs4 import BeautifulSoup


SOURCE_BASE = "https://handenomori.com/jpb"


def handicap_token_to_value(token):
    """Convert Handenomori notation to an approximate run-line value.

    The source uses private-handicap notation such as 0.3, 1.5, 1半,
    1半3, 1半5 and 1半7.  The fractional '半' steps are mapped to the
    corresponding quarter-run line only for the prediction adjustment.
    The original token is preserved separately for display.
    """
    if token is None:
        return None

    text = str(token).strip().replace(" ", "")
    if not text:
        return None

    half_match = re.fullmatch(r"(\d+)半([357])?", text)
    if half_match:
        base = float(half_match.group(1)) + 0.5
        suffix = half_match.group(2)
        if suffix == "3":
            return base + 0.15
        if suffix == "5":
            return base + 0.25
        if suffix == "7":
            return base + 0.35
        return base

    try:
        return float(text)
    except ValueError:
        return None


def _game_blocks(soup):
    """Yield text blocks likely to represent one listed game."""
    seen = set()
    for tag in soup.find_all(["article", "section", "li", "tr", "div"]):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if not text or text in seen:
            continue
        if "ソフトバンク" not in text:
            continue
        if not any(team in text for team in ("オリックス", "日本ハム", "楽天", "西武", "ロッテ")):
            continue
        seen.add(text)
        yield text


def _parse_from_text(text, team_name="ソフトバンク"):
    """Parse the team carrying the handicap and its source token."""
    compact = " ".join(str(text).split())
    teams = ["ソフトバンク", "日本ハム", "楽天", "西武", "ロッテ", "オリックス"]
    opponent = next((team for team in teams if team != team_name and team in compact), None)
    if not opponent or team_name not in compact:
        return None

    # Extract source handicap tokens while excluding scores/times/years.
    tokens = re.findall(r"(?<!\d)(?:\d+半[357]?|\d+(?:\.[357])?)(?![\d:])", compact)
    parsed = [(token, handicap_token_to_value(token)) for token in tokens]
    parsed = [(token, value) for token, value in parsed if value is not None and 0 <= value <= 5]
    if not parsed:
        return None

    # Handenomori shows one handicap in either the home or visitor column.
    # Choose the last plausible handicap token in the game block, because
    # times and scores appear before the handicap table in page text.
    token, value = parsed[-1]

    team_pos = compact.rfind(team_name)
    opponent_pos = compact.rfind(opponent)
    token_pos = compact.rfind(token)

    # In flattened table text the handicap value follows the team whose
    # column owns it. Prefer proximity; if ambiguous return unpublished.
    team_distance = abs(token_pos - team_pos)
    opponent_distance = abs(token_pos - opponent_pos)
    favored_team = team_name if team_distance <= opponent_distance else opponent

    signed_value = -value if favored_team == team_name else value
    return {
        "published": True,
        "team": team_name,
        "opponent": opponent,
        "favored_team": favored_team,
        "token": token,
        "value": value,
        "handicap_score": signed_value,
    }


def fetch_hawks_handicap(target_date=None, timeout=10):
    """Fetch the published Hawks handicap for target_date.

    Returns published=False when the source has not posted a handicap yet,
    parsing fails, or the request is unavailable. No fabricated fallback is
    returned; callers should apply no handicap adjustment in that case.
    """
    target_date = target_date or date.today()
    ymd = target_date.strftime("%Y%m%d")
    url = f"{SOURCE_BASE}/{ymd}/"

    result = {
        "published": False,
        "source_url": url,
        "token": None,
        "value": None,
        "handicap_score": None,
        "favored_team": None,
        "opponent": None,
    }

    try:
        from game_calendar import parse_handicap_html
        games = parse_handicap_html(fetch_member_page(url, timeout=timeout), target_date)
        for game in games:
            if "ソフトバンク" not in (game["home"], game["away"]):
                continue
            for side in ("home", "away"):
                token = game.get(f"{side}_handicap")
                value = handicap_token_to_value(token)
                if value is None:
                    continue
                favored = game[side]
                result.update({
                    "published": True, "team": "ソフトバンク",
                    "opponent": game["away"] if game["home"] == "ソフトバンク" else game["home"],
                    "favored_team": favored, "token": token, "value": value,
                    "handicap_score": -value if favored == "ソフトバンク" else value,
                })
                return result
    except Exception:
        return result

    return result
