import unittest
from copy import deepcopy
from virtual_dashboard import summarize, month_options, calendar_html, history_rows


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"date": "2026-09-02", "status": "calculated", "points_delta": 100},
                     {"date": "2026-09-01", "status": "calculated", "points_delta": -30},
                     {"date": "2026-09-02", "status": "calculated", "points_delta": -20},
                     {"date": "2026-09-02", "status": "review", "points_delta": 99999},
                     {"date": "2026-09-03", "status": "pending", "points_delta": None},
                     {"date": "2026-08-31", "status": "cancelled", "points_delta": None}]

    def test_daily_and_cumulative_exclude_unresolved(self):
        before = deepcopy(self.rows)
        s = summarize(self.rows)
        self.assertEqual(s["points"], 50)
        self.assertEqual([r["累積ポイント"] for r in s["series"]], [-30, 50])
        self.assertEqual((s["calculated"], s["review"], s["pending"], s["cancelled"]), (3, 1, 1, 1))
        self.assertEqual(self.rows, before)

    def test_empty(self):
        self.assertEqual(summarize([])["points"], 0)
        self.assertEqual(month_options([]), [])
        self.assertEqual(history_rows([]), [])

    def test_months_and_invalid_date(self):
        self.assertEqual(month_options(self.rows + [{"date": "bad"}]), ["2026-09", "2026-08"])

    def test_calendar_marks_unresolved_without_zero_fallback(self):
        rendered = calendar_html(self.rows, "2026-09")
        self.assertIn("+80", rendered)
        self.assertIn("要確認 1", rendered)
        self.assertIn("未確定 1", rendered)
        self.assertIn("—", rendered)
        self.assertEqual(rendered.count('class="vp-cell'), 30)

    def test_history_and_leap_year(self):
        self.assertEqual(history_rows(self.rows)[0]["日付"], "2026-09-03")
        self.assertIn("<b>29</b>", calendar_html([], "2024-02"))
        self.assertNotIn("<b>30</b>", calendar_html([], "2024-02"))


if __name__ == "__main__":
    unittest.main()
