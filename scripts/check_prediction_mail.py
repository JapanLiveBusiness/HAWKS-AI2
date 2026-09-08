"""Check private Gmail SMTP credentials without sending or printing secrets."""
import argparse
from pathlib import Path
import smtplib
import ssl
import stat


def load_settings(path):
    path = Path(path)
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o077:
        raise ValueError('設定ファイルは所有者のみアクセス可能にしてください')
    settings = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or key in settings:
            raise ValueError('設定形式または重複項目を確認してください')
        settings[key] = value.strip()
    sender = 'tsutsumi@japanlivebusiness.com'
    if settings.get('SMTP_USER') != sender or settings.get('SMTP_FROM') != sender:
        raise ValueError('送信元とSMTPユーザーを確認してください')
    password = settings.get('SMTP_PASSWORD', '').replace(' ', '')
    if len(password) != 16 or not password.isascii() or not password.isalpha():
        raise ValueError('Googleアプリパスワードの形式を確認してください')
    return sender, password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    try:
        sender, password = load_settings(args.config)
        # Host is fixed: never transmit the secret to a host from an edited file.
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20,
                              context=ssl.create_default_context()) as client:
            client.login(sender, password)
        print('OK: Google SMTP認証成功。メールは送信していません。')
    except smtplib.SMTPAuthenticationError:
        print('NG: Google認証失敗。アカウントとアプリパスワードを確認してください。')
        return 1
    except ValueError as exc:
        print(f'NG: {exc}')
        return 1
    except Exception:
        # Do not print exception payloads, configuration or SMTP responses.
        print('NG: 接続または設定ファイルの読み取りを確認してください。秘密情報は非表示です。')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
