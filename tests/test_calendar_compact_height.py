import unittest
from virtual_dashboard import calendar_html


class CalendarCompactHeightTests(unittest.TestCase):
    def test_dense_days_grow_from_content_not_fixed_extra_height(self):
        rows = [dict(date=f'2026-09-{day:02}', team='巨人', bet_amount=100000,
                     status='calculated', points_delta=18000,
                     team_score_9=5, opponent_score_9=5)
                for day, count in [(5, 5), (6, 4)] for _ in range(count)]
        html = calendar_html(rows, '2026-09')
        self.assertEqual(html.count('class="vp-bet"'), 9)
        self.assertIn('aspect-ratio:auto;min-height:calc((100cqw - 30px)/6);height:auto', html)
        self.assertNotIn(':has(.vp-bet:nth-child(4))', html)
        self.assertIn('累積 +162,000', html)
        self.assertEqual(html.count('>分</span>'), 9)
