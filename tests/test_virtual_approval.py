from copy import deepcopy
from datetime import datetime, timezone
import unittest
from virtual_approval import validate_approval, fingerprint, apply_approval
from virtual_replay import replay_records


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.record = dict(id='a', date='2026-08-14', team='ソフトバンク', opponent='楽天',
                           bet_amount=100000, status='final', handicap=1.6)
        self.values = dict(team_score_9=2, opponent_score_9=5, handicap_raw='1半5',
                           fraction='-1', evidence='確認資料の9回得点・ハンデ表')

    def approved(self):
        r = deepcopy(self.record)
        r['virtual_approval'] = dict(validate_approval(r, self.values, []),
            source_fingerprint=fingerprint(r), saved_at=datetime.now(timezone.utc).isoformat())
        return r

    def test_manual_approval_replays_without_mutating_original(self):
        record = self.approved()
        before = deepcopy(record)
        row = replay_records([record], [])['results'][0]
        self.assertEqual(row['points_delta'], -100000)
        self.assertTrue(row['manual_approved'])
        self.assertEqual(record, before)

    def test_missing_and_invalid_inputs(self):
        for changes in [dict(evidence=''), dict(fraction='NaN'), dict(fraction='1.1'),
                        dict(fraction='.25'), dict(team_score_9=None), dict(team_score_9=True),
                        dict(handicap_raw='x'), dict(fraction='1')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_approval(self.record, dict(self.values, **changes), [])

    def test_undefined_rule_is_explicit_and_positive_rate(self):
        v = dict(self.values, handicap_raw='-0.4', fraction='.4')
        result = validate_approval(self.record, v, [])
        self.assertTrue(result['manual_rule'])
        self.assertEqual(result['points_delta'], 36000)

    def test_score_conflict_cancellation_and_pending_blocked(self):
        g = dict(date='2026-08-14', home='ソフトバンク', away='楽天', home_9=3, away_9=5, status='final')
        for game in [g, dict(g, status='cancelled')]:
            with self.assertRaises(ValueError):
                validate_approval(self.record, self.values, [game])
        with self.assertRaises(ValueError):
            validate_approval(dict(self.record, status='pending'), self.values, [])

    def test_edit_invalidates_approval_and_new_official_conflict(self):
        r = self.approved()
        r['bet_amount'] = 200000
        result = replay_records([r], [])['results'][0]
        self.assertEqual(result['status'], 'review')
        self.assertIsNone(result['points_delta'])
        r = self.approved()
        g = dict(date='2026-08-14', home='ソフトバンク', away='楽天', home_9=3, away_9=5, status='final', source='official')
        self.assertEqual(replay_records([r], [g])['results'][0]['status'], 'review')

    def test_unapproved_unchanged_and_deleted_excluded(self):
        self.assertEqual(replay_records([self.record], [])['results'][0]['status'], 'review')
        self.assertEqual(replay_records([dict(self.approved(), virtual_deleted=True)], [])['results'], [])
