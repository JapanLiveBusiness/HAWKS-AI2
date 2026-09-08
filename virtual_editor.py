"""Validated virtual-only edits with atomic, optimistic persistence."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from bet_store import BetStoreError, BetNotFoundError, _locked, _atomic_write, load_bets
from virtual_replay import outcome_fraction

TEAMS = ["巨人", "阪神", "DeNA", "広島", "ヤクルト", "中日", "ソフトバンク", "日本ハム", "ロッテ", "楽天", "オリックス", "西武"]


def save_virtual_approval(path, expected, values, *, confirmed=False):
    from virtual_approval import validate_approval, fingerprint
    from virtual_replay import load_verified_scores
    if confirmed is not True:
        raise ValueError('得点・ハンデ・判定内容と重複の有無を確認してください')
    with _locked(path):
        records = load_bets(path)
        for index, record in enumerate(records):
            if record['id'] != expected.get('id'):
                continue
            if record != expected:
                raise BetStoreError('別の画面で変更されています。再読み込みしてください。')
            checked = validate_approval(record, values, load_verified_scores())
            checked.update(saved_at=datetime.now(timezone.utc).isoformat(), source_fingerprint=fingerprint(record))
            updated = deepcopy(record)
            updated.setdefault('virtual_approval_history', []).append(dict(
                saved_at=checked['saved_at'], before=deepcopy(record.get('virtual_approval')), after=deepcopy(checked)))
            updated['virtual_approval'] = checked
            records[index] = updated
            _atomic_write(path, records)
            return deepcopy(updated)
    raise BetNotFoundError('この記録は見つかりません。')


def validate_edit(values):
    try:
        points = Decimal(str(values.get("bet_amount")))
    except InvalidOperation as exc:
        raise ValueError("ポイント数を入力してください") from exc
    if not points.is_finite() or points <= 0 or points != points.to_integral_value() or points > 10**12:
        raise ValueError("ポイント数は1〜1兆の整数で入力してください")
    team, opponent = values.get("team"), values.get("opponent")
    if team not in TEAMS or opponent not in TEAMS or team == opponent:
        raise ValueError("異なる2チームを指定してください")
    token = str(values.get("handicap_raw") or "").strip()
    outcome_fraction(0, 0, token)
    status = values.get("status")
    if status not in {"pending", "final"}:
        raise ValueError("状態が不正です")
    memo = str(values.get("memo") or "")
    if len(memo) > 2000:
        raise ValueError("メモは2000文字以内です")
    return dict(team=team, opponent=opponent, bet_amount=int(points),
                handicap_raw=token, status=status, memo=memo)


def save_virtual_edit(path, expected, values):
    changes = validate_edit(values)
    with _locked(path):
        records = load_bets(path)
        for index, record in enumerate(records):
            if record["id"] != expected.get("id"):
                continue
            if record != expected:
                raise BetStoreError("別の画面で変更されています。再読み込みして編集し直してください。")
            updated = deepcopy(record)
            updated.setdefault("virtual_edit_history", []).append({
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "before": deepcopy(record.get("virtual_edit")), "after": deepcopy(changes)})
            updated["virtual_edit"] = changes
            records[index] = updated
            _atomic_write(path, records)
            return deepcopy(updated)
    raise BetNotFoundError("この記録は削除されたか、見つかりません。")


def set_virtual_deleted(path, expected, deleted):
    """Recoverable removal from virtual views; retain source and audit atomically."""
    if type(deleted) is not bool:
        raise ValueError("削除状態が不正です")
    with _locked(path):
        records = load_bets(path)
        for index, record in enumerate(records):
            if record["id"] != expected.get("id"):
                continue
            if record != expected:
                raise BetStoreError("別の画面で変更されています。再読み込みしてください。")
            if bool(record.get("virtual_deleted")) == deleted:
                return deepcopy(record)
            updated = deepcopy(record)
            updated["virtual_deleted"] = deleted
            updated.setdefault("virtual_deletion_history", []).append({
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "action": "delete" if deleted else "restore"})
            records[index] = updated
            _atomic_write(path, records)
            return deepcopy(updated)
    raise BetNotFoundError("この記録は見つかりません。")
