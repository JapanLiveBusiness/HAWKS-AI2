"""Non-cash game replay. Never mutate the source records or financial fields."""

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re
from pathlib import Path
import unicodedata

RULE_VERSION = "virtual-nine-innings-image-v3"
# Columns: tie, win by one, win by two, win by three (giving side).
TABLE = {
    # Refetched values, using the user's proportional partial-result rule.
    "0.8": ("-.8", ".2", "1", "1"),
    "1.1": ("-1", "-.1", "1", "1"),
    "1.6": ("-1", "-.6", "1", "1"),
    "0.3": ("-.3", ".7", "1", "1"),
    "0.5": ("-.5", ".5", "1", "1"),
    "0.7": ("-.7", ".3", "1", "1"),
    "1": ("-1", "0", "1", "1"),
    "1.3": ("-1", "-.3", "1", "1"),
    "1.5": ("-1", "-.5", "1", "1"),
    "1.7": ("-1", "-.7", "1", "1"),
    "1半": ("-1", "-1", "1", "1"),
    "1半3": ("-1", "-1", ".7", "1"),
    "1半5": ("-1", "-1", ".5", "1"),
    "1半7": ("-1", "-1", ".3", "1"),
    "2": ("-1", "-1", "0", "1"),
}
ALIASES = {
    "読売ジャイアンツ": "巨人", "横浜DeNAベイスターズ": "DeNA",
    "横浜DeNA": "DeNA", "東京ヤクルトスワローズ": "ヤクルト",
    "阪神タイガース": "阪神", "中日ドラゴンズ": "中日",
    "広島東洋カープ": "広島", "北海道日本ハムファイターズ": "日本ハム",
    "北海道日本ハム": "日本ハム", "福岡ソフトバンクホークス": "ソフトバンク",
    "福岡ソフトバンク": "ソフトバンク", "ホークス": "ソフトバンク",
    "東北楽天ゴールデンイーグルス": "楽天", "東北楽天": "楽天",
    "オリックス・バファローズ": "オリックス", "千葉ロッテマリーンズ": "ロッテ",
    "千葉ロッテ": "ロッテ", "埼玉西武ライオンズ": "西武", "埼玉西武": "西武",
}


def team_name(value):
    value = unicodedata.normalize("NFKC", str(value or "")).strip()
    return ALIASES.get(value, value)


def raw_handicap(record):
    raw = record.get("handicap_raw")
    if raw is not None and str(raw).strip():
        return str(raw)
    value = record.get("handicap")
    if value is None or isinstance(value, bool):
        raise ValueError("元のハンデ表記がありません")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        # Legacy strings with 半 retain the original distinction.
        return str(value)
    if not number.is_finite():
        raise ValueError("ハンデが不正です")
    if abs(number) % 1 == Decimal(".5"):
        raise ValueError("小数の.5と半を区別できません。元表記の確認が必要です")
    return str(value)


def outcome_fraction(team_score, opponent_score, token):
    """Return a signed fraction from the supplied image, not decimal subtraction."""
    for score in (team_score, opponent_score):
        if isinstance(score, bool) or not isinstance(score, int) or score < 0:
            raise ValueError("得点は非負の整数が必要です")
    token = unicodedata.normalize("NFKC", str(token)).strip().strip("<>")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\d+半[357]?)", token):
        raise ValueError("ハンデ表記が不正です")
    receiving = token.startswith("-")
    token = token[1:] if token.startswith(("+", "-")) else token
    if "半" not in token:
        try:
            number = Decimal(token)
            if not number.is_finite() or number < 0:
                raise ValueError("ハンデ表記が不正です")
            token = format(number.normalize(), "f")
        except InvalidOperation as exc:
            raise ValueError("ハンデ表記が不正です") from exc
    margin = team_score - opponent_score
    # User-confirmed supplement: a tied game with 0.2 received is
    # a 20% partial win (90% credit is applied in replay_records).
    # Non-tie 0.2 outcomes remain unconfirmed, not interpolated.
    if token == "0.2" and margin == 0:
        return Decimal(".2") if receiving else Decimal("-.2")
    if token == "0":
        return Decimal((margin > 0) - (margin < 0))
    if token not in TABLE:
        raise ValueError("画像にないハンデ表記のため要確認です")
    if receiving:
        margin = -margin
    fraction = Decimal("-1") if margin < 0 else Decimal(TABLE[token][min(margin, 3)])
    return -fraction if receiving else fraction


def load_verified_scores(path=None):
    path = path or Path(__file__).with_name("virtual_nine_inning_scores.json")
    return json.loads(Path(path).read_text(encoding="utf-8"))["games"]


def load_verified_handicaps(path=None):
    path = path or Path(__file__).with_name("virtual_verified_handicaps.json")
    return json.loads(Path(path).read_text(encoding="utf-8"))["records"]


def replay_records(records, games, *, positive_rate="0.90", handicaps=()):
    """Replay all dates; missing evidence stays review-only, with no zero fallback."""
    rate = Decimal(str(positive_rate))
    if not rate.is_finite() or not 0 <= rate <= 1:
        raise ValueError("ポイント付与率が不正です")
    results = []
    for source_record in records:
        if source_record.get("virtual_deleted"):
            continue
        original = {**source_record, **{k: v for k, v in source_record.get("virtual_edit", {}).items()
                    if k in {"team", "opponent", "bet_amount", "handicap_raw", "status", "memo"}}}
        row = {"id": original.get("id"), "date": original.get("date"),
               "team": original.get("team"), "opponent": original.get("opponent"),
               "bet_amount": original.get("bet_amount"), "bet_units": original.get("bet_units"),
               "source": original.get("source"),
               "rule_version": RULE_VERSION, "status": "review", "points_delta": None,
               "virtual_edited": bool(source_record.get("virtual_edit"))}
        try:
            day = date.fromisoformat(str(original.get("date"))).isoformat()
            team, opponent = team_name(row["team"]), team_name(row["opponent"])
            if not team or not opponent or team == opponent:
                raise ValueError("対戦チームを確認してください")
            matches = [g for g in games if g.get("date") == day
                       and {team_name(g.get("home")), team_name(g.get("away"))} == {team, opponent}]
            if len(matches) != 1:
                raise ValueError("9回時点の公式記録が未確認、または試合を一意に特定できません")
            game = matches[0]
            row["score_source"] = game["source"]
            if game.get("status") == "cancelled":
                row.update(status="cancelled", reason="中止。得点・ポイント判定なし")
            elif original.get("status") != "final":
                row.update(status="pending", reason="元記録が未確定のため変更しません")
            else:
                if game.get("status") != "final":
                    raise ValueError("試合終了を確認できません")
                home_side = team == team_name(game["home"])
                own = game["home_9"] if home_side else game["away_9"]
                other = game["away_9"] if home_side else game["home_9"]
                evidence = [h for h in handicaps if h.get("date") == day
                            and team_name(h.get("team")) == team
                            and team_name(h.get("opponent")) == opponent]
                if len(evidence) > 1:
                    raise ValueError("再取得ハンデを一意に特定できません")
                row["stored_handicap"] = source_record.get("handicap_raw") or source_record.get("handicap")
                if source_record.get("virtual_edit", {}).get("handicap_raw"):
                    token = raw_handicap(original)
                    row["handicap_source"] = "日付別編集で指定"
                elif evidence:
                    token = str(evidence[0]["handicap_raw"])
                    row["handicap_source"] = evidence[0]["source_url"]
                    row["handicap_refetched"] = True
                else:
                    token = raw_handicap(original)
                row.update(handicap_raw=token, team_score_9=own, opponent_score_9=other)
                fraction = outcome_fraction(own, other, token)
                amount = original.get("bet_amount")
                if amount is None:
                    units = original.get("bet_units")
                    if units is None:
                        raise ValueError("仮想ポイント数がありません")
                    amount = abs(Decimal(str(units))) * 10000
                points = Decimal(str(amount))
                if not points.is_finite() or points <= 0:
                    raise ValueError("仮想ポイント数が不正です")
                delta = points * fraction * (rate if fraction > 0 else 1)
                row.update(status="calculated", handicap_raw=token, team_score_9=own,
                           opponent_score_9=other, fraction=str(fraction), positive_rate=str(rate),
                           points_delta=int(delta.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
        except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
            row["reason"] = str(exc)
        from virtual_approval import apply_approval
        results.append(apply_approval(source_record, row, games))
    return {"rule_version": RULE_VERSION, "virtual_only": True,
            "handicap_evidence": deepcopy(list(handicaps)),
            "source_sha256": hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            "original_records": deepcopy(records), "results": results}
