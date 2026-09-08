import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import importlib.util
from unittest.mock import patch, MagicMock
from prediction_mail import build_message, deliver_once


class MailTests(unittest.TestCase):
    def setUp(self):
        self.pick = dict(team='阪神', opponent='横浜', giving_team='阪神', handicap='1.0', amount=300000)

    def test_template(self):
        message = build_message('2026-09-06', [self.pick], 'owner@example.com')
        self.assertEqual(message.get_content(), '9月6日（日曜日）\n\n1\n阪神<1.0>30\n横浜\n')

    def test_opponent_handicap_only(self):
        message = build_message('2026-09-06', [dict(self.pick, giving_team='横浜', handicap='1半5')], 'owner@example.com')
        self.assertIn('阪神30\n横浜<1半5>', message.get_content())

    def test_validation(self):
        for picks in ([], [self.pick, self.pick], [dict(self.pick, amount=1100000)],
                      [dict(self.pick, team='阪神\nBcc: x')], [dict(self.pick, giving_team='巨人')]):
            with self.assertRaises(ValueError):
                build_message('2026-09-06', picks, 'owner@example.com')

    def test_sending_disabled_by_default(self):
        message = build_message('2026-09-06', [self.pick], 'owner@example.com')
        with self.assertRaises(ValueError):
            deliver_once(message, '2026-09-06', '/unused', {}, confirmed=True)

    @unittest.skipUnless(importlib.util.find_spec('filelock'), 'filelock needed')
    def test_ledger_prevents_duplicate_and_uncertain_retry(self):
        day = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        message = build_message(day, [self.pick], 'owner@example.com')
        for failure in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'mail.json'
                transport = MagicMock(side_effect=RuntimeError('private') if failure else None)
                kwargs = dict(confirmed=True, transport=transport)
                settings = {'PREDICTION_MAIL_ENABLED': 'true'}
                if failure:
                    with self.assertRaisesRegex(RuntimeError, '送信結果が未確認'):
                        deliver_once(message, day, path, settings, **kwargs)
                else:
                    self.assertEqual(deliver_once(message, day, path, settings, **kwargs)['status'], 'sent')
                self.assertEqual(deliver_once(message, day, path, settings, **kwargs)['status'], 'blocked')
                self.assertEqual(transport.call_count, 1)
                self.assertNotIn('private', path.read_text(encoding='utf-8'))

    def test_smtp_uses_tls_and_login(self):
        from prediction_mail import smtp_deliver
        message = build_message('2026-09-06', [self.pick], 'owner@example.com')
        settings = dict(SMTP_HOST='smtp.example.invalid', SMTP_USER='test', SMTP_PASSWORD='test-only')
        with patch('prediction_mail.smtplib.SMTP_SSL') as factory:
            client = factory.return_value
            client.send_message.return_value = {}
            smtp_deliver(message, settings)
            client.login.assert_called_once_with('test', 'test-only')
            client.send_message.assert_called_once_with(message)

    def test_old_message_cannot_use_today_key(self):
        day = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        message = build_message('2000-01-01', [self.pick], 'owner@example.com')
        with self.assertRaises(ValueError):
            deliver_once(message, day, '/unused', {'PREDICTION_MAIL_ENABLED': 'true'}, confirmed=True)


if __name__ == '__main__':
    unittest.main()

