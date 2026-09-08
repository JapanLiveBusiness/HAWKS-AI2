import unittest
from virtual_dashboard import calendar_html, bet_amount_label
from virtual_replay import replay_records, load_verified_scores


class CalendarStakesTests(unittest.TestCase):
    def test_day_left_and_totals_right_share_header(self):
        html = calendar_html([dict(date='2026-09-03', status='calculated', points_delta=-400000)], '2026-09')
        self.assertIn('<span class="vp-day-header"><b>3</b><span class="vp-day-totals"><strong>-400,000</strong><span class="vp-cumulative">累積 -400,000</span></span></span>', html)
        self.assertIn('.vp-calendar .vp-day-header{justify-content:space-between}', html)
        self.assertIn('.vp-calendar .vp-day-totals{margin-left:auto;text-align:right}', html)

    def test_cumulative_includes_hidden_monday_and_excludes_review(self):
        rows = [dict(date='2026-09-07', status='calculated', points_delta=9000),
                dict(date='2026-09-08', status='calculated', points_delta=-4000),
                dict(date='2026-09-08', status='review', points_delta=99999)]
        html = calendar_html(rows, '2026-09')
        self.assertIn('累積 +5,000', html)
        self.assertNotIn('+104,999', html)
        self.assertIn('累積 —', calendar_html([dict(date='2026-09-01', status='review')], '2026-09'))

    def test_six_columns_hide_monday_without_changing_totals(self):
        from virtual_dashboard import summarize
        rows = [dict(date='2026-09-07', team='月曜記録', bet_amount=10000,
                     status='calculated', points_delta=9000)]
        html = calendar_html(rows, '2026-09')
        self.assertNotIn('vp-weekday">月', html)
        self.assertNotIn('edit_date=2026-09-07', html)
        self.assertIn('edit_date=2026-09-08', html)
        self.assertIn('repeat(6,minmax(0,1fr))', html)
        self.assertEqual(summarize(rows)['points'], 9000)

    def test_labels(self):
        self.assertEqual(bet_amount_label({'bet_amount':200000}), '20万')
        self.assertEqual(bet_amount_label({'bet_units':-40}), '40万')
        self.assertEqual(bet_amount_label({'bet_amount':12500}), '12,500')
        for value in [None, 0, -1, 'NaN', 'Infinity', 'bad']:
            self.assertEqual(bet_amount_label({'bet_amount':value}), '金額要確認')

    def test_edits_reviews_deleted_and_escaping(self):
        records = [dict(id='a', date='2026-09-03', team='中日', opponent='広島',
                        bet_amount=100000, handicap=0, status='final',
                        virtual_edit={'bet_amount':200000}),
                   dict(id='b', date='2026-09-03', team='<script>x</script>',
                        opponent='阪神', bet_amount=400000),
                   dict(id='c', date='2026-09-03', team='削除対象', virtual_deleted=True)]
        result = replay_records(records, load_verified_scores())['results']
        html = calendar_html(result, '2026-09')
        self.assertIn('20万', html)
        self.assertIn('40万', html)
        self.assertIn('-200,000', html)
        self.assertIn('要確認 1', html)
        self.assertNotIn('削除対象', html)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertEqual(html.count('class="vp-bet"'), 2)

    def test_two_character_names_inline_without_pt(self):
        from virtual_dashboard import TEAM_SHORT
        self.assertTrue(all(len(name) == 2 for team, name in TEAM_SHORT.items() if team != 'ロッテ'))
        self.assertEqual(TEAM_SHORT['ロッテ'], 'ﾛｯﾃ')
        html = calendar_html([dict(date='2026-09-03', team='ヤクルト', bet_amount=200000,
                                   status='calculated', points_delta=-200000)], '2026-09')
        self.assertIn('<span>ヤク</span> <span class="vp-stake">20万</span>', html)
        self.assertNotIn(' pt', html)
        self.assertIn('white-space:nowrap', html)
