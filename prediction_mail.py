"""Explicit-plan email delivery. Preview by default; no implicit scheduler."""
from datetime import date, datetime, timezone, timedelta
from email.message import EmailMessage
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import smtplib
import ssl
import tempfile

RECIPIENT = 'tsutsumi41@gmail.com'
WEEKDAYS = '月火水木金土日'


def build_message(day, picks, sender):
    day = date.fromisoformat(day)
    if not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+', sender):
        raise ValueError('送信元メールアドレスを設定してください')
    if not 1 <= len(picks) <= 3:
        raise ValueError('対象は1〜3チームです')
    lines = [f'{day.month}月{day.day}日（{WEEKDAYS[day.weekday()]}曜日）']
    seen = set()
    for index, pick in enumerate(picks, 1):
        team, opponent = pick['team'], pick['opponent']
        if not all(isinstance(v, str) and v and not any(c in v for c in '\r\n<>') for v in (team, opponent)) or team == opponent:
            raise ValueError('対戦チームが不正です')
        game = tuple(sorted((team, opponent)))
        if game in seen:
            raise ValueError('同じ対戦を重複して送信できません')
        seen.add(game)
        amount = pick['amount']
        if type(amount) is not int or amount <= 0 or amount % 10000:
            raise ValueError('仮想BET額は1万単位の正の整数です')
        # Explicit giving side avoids interpreting ambiguous signed half tokens.
        giving = pick.get('giving_team')
        handicap = str(pick.get('handicap') or '').strip()
        if handicap:
            if giving not in (team, opponent) or not re.fullmatch(r'(?:\d+(?:\.\d+)?|\d+半[357]?)', handicap):
                raise ValueError('ハンデの出し側と元表記を確認してください')
        elif giving:
            raise ValueError('出し側のみでハンデがありません')
        first = f'{team}<{handicap}>' if handicap and giving == team else team
        second = f'{opponent}<{handicap}>' if handicap and giving == opponent else opponent
        lines.extend(['', str(index), f'{first}{amount // 10000}', second])
    if sum(p['amount'] for p in picks) > 1000000:
        raise ValueError('仮想BET合計は100万以下にしてください')
    message = EmailMessage()
    message['From'] = sender
    message['To'] = RECIPIENT
    message['Subject'] = f'{day.month}月{day.day}日 当日予想（仮想ゲーム）'
    message['X-Prediction-Date'] = day.isoformat()
    message.set_content('\n'.join(lines) + '\n')
    return message


def smtp_deliver(message, settings):
    mode = settings.get('SMTP_SECURITY', 'ssl')
    if mode not in {'ssl', 'starttls'}:
        raise ValueError('SMTPはTLS接続が必要です')
    host, user, password = (settings.get(k) for k in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD'))
    if not all((host, user, password)):
        raise ValueError('SMTP接続設定が不足しています')
    port = int(settings.get('SMTP_PORT', 465 if mode == 'ssl' else 587))
    context = ssl.create_default_context()
    if mode == 'ssl':
        client = smtplib.SMTP_SSL(host, port, timeout=30, context=context)
    else:
        client = smtplib.SMTP(host, port, timeout=30)
    with client:
        if mode == 'starttls':
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        client.login(user, password)
        refused = client.send_message(message)
        if refused:
            raise RuntimeError('宛先が受け付けられませんでした')


def _save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
        temporary = stream.name
    os.replace(temporary, path)


def deliver_once(message, delivery_key, ledger_path, settings, *, confirmed=False, transport=None):
    """At-most-once automatic attempt. Uncertain results require manual review.

    SMTP cannot guarantee exactly-once delivery: a disconnect after acceptance
    may be ambiguous. Persist 'sending' before network IO and never auto-retry it.
    """
    if not confirmed or settings.get('PREDICTION_MAIL_ENABLED') != 'true':
        raise ValueError('送信の有効化と明示確認が必要です')
    if message['To'] != RECIPIENT or message.get('Cc') or message.get('Bcc'):
        raise ValueError('承認された宛先以外には送信できません')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?', delivery_key):
        raise ValueError('送信キーは日付または日付と送信時刻です')
    today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    if delivery_key[:10] != today or message.get('X-Prediction-Date') != today:
        raise ValueError('当日以外の予想は送信できません')
    from filelock import FileLock
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path) + '.lock', timeout=10):
        ledger = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(ledger, dict):
            raise ValueError('送信履歴が不正です')
        if delivery_key in ledger:
            return {'status': 'blocked', 'previous': ledger[delivery_key]['status']}
        event = dict(status='sending', recipient=RECIPIENT,
                     body_sha256=sha256(message.as_bytes()).hexdigest(),
                     attempted_at=datetime.now(timezone.utc).isoformat())
        ledger[delivery_key] = event
        _save(path, ledger)
        try:
            (transport or smtp_deliver)(message, settings)
        except Exception:
            event['status'] = 'uncertain'
            _save(path, ledger)
            raise RuntimeError('送信結果が未確認です。自動再送せず送信履歴を確認してください。') from None
        event['status'] = 'sent'
        event['sent_at'] = datetime.now(timezone.utc).isoformat()
        _save(path, ledger)
        return dict(event)
