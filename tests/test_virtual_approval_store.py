from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from bet_store import save_bets, load_bets, BetStoreError
from virtual_editor import save_virtual_approval


class ApprovalStoreTests(unittest.TestCase):
    def test_confirmation_atomic_history_and_conflict(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'own.json'
            record = dict(id='a', date='2026-08-14', team='ソフトバンク', opponent='楽天',
                          status='final', bet_amount=100000, handicap=1.6, profit=123)
            save_bets(path, [record])
            record = load_bets(path)[0]
            values = dict(team_score_9=2, opponent_score_9=5, handicap_raw='1半5', fraction='-1', evidence='資料確認済み')
            with self.assertRaises(ValueError):
                save_virtual_approval(path, record, values)
            changed = save_virtual_approval(path, record, values, confirmed=True)
            self.assertEqual(changed['profit'], 123)
            self.assertEqual(len(changed['virtual_approval_history']), 1)
            self.assertEqual(load_bets(path)[0], changed)
            with self.assertRaises(BetStoreError):
                save_virtual_approval(path, record, values, confirmed=True)
