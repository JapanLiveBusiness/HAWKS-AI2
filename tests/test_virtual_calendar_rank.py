import unittest
from copy import deepcopy
from virtual_calendar_rank import probability, ranked_bets
from virtual_dashboard import calendar_html


class CalendarRankTests(unittest.TestCase):
    def prediction(self, **updates):
        return dict(dict(date='2026-09-03', time='18:00', home='中日', away='広島',
                         home_win_probability=65, locked=True, saved_at='2026-09-03T08:00:00+09:00'), **updates)

    def test_probability_requires_unique_pregame_evidence(self):
        row = dict(date='2026-09-03', team='中日', opponent='広島')
        p = self.prediction()
        self.assertEqual(probability(row, [p, p]), 65)
        self.assertEqual(probability(dict(row, team='広島', opponent='中日'), [p]), 35)
        self.assertIsNone(probability(row, [p, self.prediction(home_win_probability=70)]))
        for change in [dict(locked=False), dict(saved_at='2026-09-03T19:00:00+09:00'),
                       dict(home_win_probability='NaN'), dict(home_win_probability=101),
                       dict(date='2026-09-04'), dict(saved_at='2026-09-03T08:00:00')]:
            self.assertIsNone(probability(row, [self.prediction(**change)]))

    def test_rank_manual_and_unknown(self):
        rows = [dict(id='m', date='2026-09-03', team='中日', opponent='広島', source='manual'),
                dict(id='low', date='2026-09-03', team='広島', opponent='中日'),
                dict(id='high', date='2026-09-03', team='中日', opponent='広島'),
                dict(id='edit', date='2026-09-03', team='中日', opponent='広島', virtual_edited=True),
                dict(id='unknown', date='2026-09-02', team='中日', opponent='広島')]
        original = deepcopy(rows)
        result = ranked_bets(rows, [self.prediction()])
        self.assertEqual([(r['id'], rank, prob) for r, rank, prob in result],
                         [('high','1',65), ('low','2',35), ('m','M',None), ('edit','M',None), ('unknown','—',None)])
        self.assertEqual(rows, original)
        tied = ranked_bets([rows[2], dict(rows[2], id='tie')], [self.prediction()])
        self.assertEqual([r[1] for r in tied], ['1','1'])

    def test_square_layout_and_manual_lotte(self):
        html = calendar_html([dict(date='2026-09-03',team='ロッテ',source='manual',bet_amount=200000,status='pending')], '2026-09')
        self.assertIn('ﾛｯﾃ', html)
        self.assertIn('vp-rank">M', html)
        self.assertIn('aspect-ratio:1', html)
        self.assertIn('border-top:0;border-bottom:', html)
