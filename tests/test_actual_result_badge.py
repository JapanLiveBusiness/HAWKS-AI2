import unittest
from virtual_dashboard import handicap_side_badge, calendar_html


class ActualResultBadgeTests(unittest.TestCase):
    def test_score_not_profit(self):
        for own, other, mark in [(2, 1, '勝'), (0, 1, '負'), (5, 5, '分')]:
            self.assertIn(f'>{mark}</span>', handicap_side_badge(dict(
                team_score_9=own, opponent_score_9=other, points_delta=18000)))

    def test_unknown_and_cancelled(self):
        for value in [None, -1, True, '2']:
            self.assertIn('>?</span>', handicap_side_badge(dict(team_score_9=value, opponent_score_9=0)))
        self.assertIn('>中止</span>', handicap_side_badge(dict(status='cancelled')))

    def test_placement_and_no_mutation(self):
        row = dict(date='2026-09-05', team='巨人', bet_amount=100000,
                   status='calculated', points_delta=18000, team_score_9=5, opponent_score_9=5)
        before = dict(row)
        html = calendar_html([row], '2026-09')
        self.assertIn('10万</span> <span class="vp-game-result"', html)
        self.assertIn('>分</span>', html)
        self.assertIn('+18,000', html)
        self.assertNotIn('ハンデを出す側', html)
        self.assertEqual(before, row)
