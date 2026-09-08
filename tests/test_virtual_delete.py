from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from bet_store import save_bets, load_bets, BetStoreError, BetNotFoundError
from virtual_editor import set_virtual_deleted
from virtual_replay import replay_records, load_verified_scores


class VirtualDeleteTests(unittest.TestCase):
    def test_delete_restore_isolated_audited_and_conflict_safe(self):
        with TemporaryDirectory() as tmp:
            path, other = Path(tmp)/'own.json', Path(tmp)/'other.json'
            records = [dict(id=str(i), date='2026-09-01', team=t, opponent=o,
                            bet_amount=a, handicap=0, status='final')
                       for i, (t, o, a) in enumerate([
                           ('オリックス', '楽天', 400000), ('西武', 'ロッテ', 200000),
                           ('DeNA', '巨人', 200000)])]
            save_bets(path, records)
            save_bets(other, records)
            updated = set_virtual_deleted(path, records[2], True)
            after = load_bets(path)
            self.assertEqual(after[:2], records[:2])
            self.assertEqual(load_bets(other), records)
            for k, v in records[2].items():
                self.assertEqual(updated[k], v)
            report = replay_records(after, load_verified_scores())
            self.assertEqual(len(report['results']), 2)
            self.assertEqual(len(report['original_records']), 3)
            self.assertEqual(sum(r['points_delta'] for r in report['results']), -600000)
            with self.assertRaises(BetStoreError):
                set_virtual_deleted(path, records[2], True)
            with self.assertRaises(BetNotFoundError):
                set_virtual_deleted(path, dict(id='missing'), True)
            self.assertEqual(set_virtual_deleted(path, updated, True), updated)
            restored = set_virtual_deleted(path, updated, False)
            self.assertEqual(len(restored['virtual_deletion_history']), 2)
            self.assertEqual(len(replay_records(load_bets(path), load_verified_scores())['results']), 3)

    def test_reject_non_boolean(self):
        with self.assertRaises(ValueError):
            set_virtual_deleted(Path('unused.json'), {}, 'false')
