import unittest
from copy import deepcopy
from virtual_accuracy import compare_accuracy, is_manual


class AccuracyTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(id='one', date='2026-09-03', team='巨人', opponent='阪神',
                        status='calculated', team_score_9=3, opponent_score_9=5)
        self.original = dict(id='one', source='manual', team='巨人', opponent='阪神')
        self.pred = dict(date='2026-09-03', time='18:00', saved_at='2026-09-03T17:00:00+09:00',
                         locked=True, home='巨人', away='阪神', home_win_probability=40)

    def run_comparison(self, rows=None, predictions=None):
        return compare_accuracy(rows or [self.row], [self.original], [self.pred] if predictions is None else predictions)

    def test_paired_difference_and_no_mutation(self):
        before = deepcopy(self.row)
        result = self.run_comparison()
        self.assertEqual((result['paired_manual_rate'], result['ai_rate'], result['difference']), (0, 100, 100))
        self.assertEqual(self.row, before)

    def test_missing_late_conflicting_or_even_predictions(self):
        for predictions in ([], [dict(self.pred, saved_at='2026-09-03T18:00:00+09:00')],
                            [self.pred, dict(self.pred, home_win_probability=70)],
                            [dict(self.pred, home_win_probability=50)]):
            result = self.run_comparison(predictions=predictions)
            self.assertIsNone(result['difference'])
            self.assertEqual(result['losses'], 1)

    def test_draw_pending_review_cancel_and_duplicate(self):
        self.assertEqual(self.run_comparison([self.row, self.row])['paired'], 1)
        self.assertEqual(self.run_comparison([dict(self.row, team_score_9=5)])['draws'], 1)
        for status in ('review', 'pending', 'cancelled'):
            self.assertEqual(self.run_comparison([dict(self.row, status=status)])['paired'], 0)

    def test_approval_and_amount_edit_do_not_make_manual(self):
        original = dict(id='legacy', team='巨人', opponent='阪神', virtual_approval={'fraction': 1},
                        virtual_edit={'team': '巨人', 'opponent': '阪神', 'bet_amount': 500000})
        self.assertFalse(is_manual(original))
        original['virtual_edit']['team'] = '阪神'
        self.assertTrue(is_manual(original))

    def test_deleted_excluded_and_score_conflict(self):
        self.original['virtual_deleted'] = True
        self.assertEqual(self.run_comparison()['paired'], 0)
        self.original.pop('virtual_deleted')
        result = self.run_comparison([self.row, dict(self.row, team_score_9=8)])
        self.assertEqual(result['excluded'], 1)


if __name__ == '__main__':
    unittest.main()
