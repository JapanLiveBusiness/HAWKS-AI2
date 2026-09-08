"""Explicit, record-bound manual approvals for virtual points only."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re
import unicodedata


def fingerprint(record):
    source = {k: v for k, v in record.items() if k not in {'virtual_approval', 'virtual_approval_history'}}
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_approval(record, values, games):
    from virtual_replay import outcome_fraction, team_name
    active = {**record, **record.get('virtual_edit', {})}
    if record.get('virtual_deleted') or active.get('status') != 'final':
        raise ValueError('未確定・削除済みの記録は承認できません')
    day = date.fromisoformat(str(active.get('date'))).isoformat()
    team, opponent = team_name(active.get('team')), team_name(active.get('opponent'))
    if not team or not opponent or team == opponent:
        raise ValueError('対戦チームを確認してください')
    own, other = values.get('team_score_9'), values.get('opponent_score_9')
    if not all(type(s) is int and 0 <= s <= 999 for s in (own, other)):
        raise ValueError('9回までの両チーム得点を入力してください')
    token = unicodedata.normalize('NFKC', str(values.get('handicap_raw') or '')).strip()
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\d+半[357]?)', token):
        raise ValueError('元のハンデ表記を入力してください（出しは正、もらいは負）')
    try:
        fraction = Decimal(str(values.get('fraction')))
        amount = active.get('bet_amount')
        points = Decimal(str(amount)) if amount is not None else abs(Decimal(str(active['bet_units']))) * 10000
    except (InvalidOperation, KeyError) as exc:
        raise ValueError('判定割合・仮想ポイントを確認してください') from exc
    if not fraction.is_finite() or not -1 <= fraction <= 1 or fraction * 10 != (fraction * 10).to_integral_value():
        raise ValueError('判定割合は−1〜1の0.1刻みです')
    if not points.is_finite() or not 0 < points <= 10**12 or points != points.to_integral_value():
        raise ValueError('仮想ポイントは1〜1兆の整数です')
    evidence = str(values.get('evidence') or '').strip()
    if not evidence or len(evidence) > 2000:
        raise ValueError('得点・ハンデ・判定割合の確認根拠を入力してください（2000文字以内）')
    matches = [g for g in games if g.get('date') == day and
               {team_name(g.get('home')), team_name(g.get('away'))} == {team, opponent}]
    if len(matches) > 1:
        raise ValueError('公式試合を一意に特定できません')
    if matches:
        g = matches[0]
        if g.get('status') != 'final':
            raise ValueError('公式記録が未終了または中止です')
        expected = (g['home_9'], g['away_9']) if team_name(g['home']) == team else (g['away_9'], g['home_9'])
        if (own, other) != expected:
            raise ValueError('入力得点が確認済みの公式9回得点と異なります')
    try:
        known_fraction = outcome_fraction(own, other, token)
    except ValueError:
        known_fraction = None
    if known_fraction is not None and fraction != known_fraction:
        raise ValueError(f'現在のルールでは判定割合は{known_fraction}です')
    delta = points * fraction * (Decimal('.90') if fraction > 0 else 1)
    return dict(team_score_9=own, opponent_score_9=other, handicap_raw=token,
                fraction=str(fraction), evidence=evidence, manual_rule=known_fraction is None,
                points_delta=int(delta.quantize(Decimal('1'), rounding=ROUND_HALF_UP)))


def apply_approval(record, row, games):
    approval = record.get('virtual_approval')
    if not approval:
        return row
    result = deepcopy(row)
    try:
        if approval.get('source_fingerprint') != fingerprint(record):
            raise ValueError('承認後に記録が変更されています。再承認してください')
        checked = validate_approval(record, approval, games)
        result.update(checked, status='calculated', virtual_edited=True,
                      manual_approved=True, approved_at=approval['saved_at'],
                      positive_rate='0.90', score_source='手動承認：' + checked['evidence'],
                      handicap_source='手動承認', reason='')
    except (ValueError, KeyError, TypeError) as exc:
        result.update(status='review', points_delta=None, reason=str(exc))
    return result
