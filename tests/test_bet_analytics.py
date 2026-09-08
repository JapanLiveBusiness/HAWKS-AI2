import unittest
from datetime import date

from bet_analytics import (
    bet_amount,
    calculate_hit_rate,
    profit_for_record,
    profit_for_result,
    settle_bet,
    sort_bets,
    weekly_bet_summary,
)


class BetAnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"date": "2026-08-30", "time": "18:00", "status": "final", "result": "win", "profit": 270000, "bet_amount": 300000},
            {"date": "2026-08-29", "time": "18:00", "status": "final", "result": "loss", "profit": -100000, "bet_units": 10},
            {"date": "2026-08-28", "time": "18:00", "status": "final", "result": "push", "profit": 0, "bet_amount": 200000},
            {"date": "2026-08-31", "time": "18:00", "status": "pending", "result": None, "profit": 0, "bet_amount": 500000},
        ]

    def test_hit_rate_excludes_pushes_and_pending_bets(self):
        wins, decided, rate = calculate_hit_rate(self.records)
        self.assertEqual((wins, decided), (1, 2))
        self.assertEqual(rate, 50.0)

    def test_hit_rate_is_unavailable_without_decided_bets(self):
        self.assertEqual(calculate_hit_rate([self.records[2], self.records[3]]), (0, 0, None))

    def test_sort_options(self):
        newest = sort_bets(self.records, "新しい日付順")
        highest_profit = sort_bets(self.records, "収支が高い順")
        lowest_profit = sort_bets(self.records, "収支が低い順")
        highest_stake = sort_bets(self.records, "BET額が高い順")

        self.assertEqual(newest[0]["date"], "2026-08-31")
        self.assertEqual(highest_profit[0]["profit"], 270000)
        self.assertEqual(lowest_profit[0]["profit"], -100000)
        self.assertEqual(highest_stake[0]["bet_amount"], 500000)

    def test_legacy_units_are_converted_to_yen(self):
        self.assertEqual(bet_amount({"bet_units": -25}), 250000)

    def test_settlement_subtracts_handicap_from_selected_team(self):
        self.assertEqual(settle_bet(5, 3, 1.5), (3.5, "win"))
        self.assertEqual(settle_bet(4, 3, 1.0), (3.0, "push"))
        self.assertEqual(settle_bet(3, 3, 0.5), (2.5, "loss"))

    def test_negative_handicap_adds_to_selected_team(self):
        self.assertEqual(settle_bet(2, 3, -1.5), (3.5, "win"))

    def test_profit_uses_ninety_percent_win_rule(self):
        self.assertEqual(profit_for_result("win", 10000), 9000)
        self.assertEqual(profit_for_result("loss", 10000), -10000)
        self.assertEqual(profit_for_result("push", 10000), 0)

    def test_record_profit_recalculates_legacy_settled_value(self):
        record = {
            "status": "final",
            "result": "win",
            "bet_amount": 10000,
            "profit": 10000,
        }

        self.assertEqual(profit_for_record(record), 9000)

    def test_weekly_summary_uses_monday_to_sunday(self):
        summary = weekly_bet_summary(self.records, date(2026, 8, 30))

        self.assertEqual(summary["week_start"], date(2026, 8, 24))
        self.assertEqual(summary["week_end"], date(2026, 8, 30))
        self.assertEqual(summary["profit"], 170000)
        self.assertEqual(summary["final_count"], 3)
        self.assertEqual((summary["wins"], summary["losses"]), (1, 1))
        self.assertEqual(summary["pushes"], 1)
        self.assertEqual(summary["hit_rate"], 50.0)
        self.assertAlmostEqual(summary["roi"], 170000 / 600000 * 100)

    def test_weekly_summary_separates_pending_exposure(self):
        summary = weekly_bet_summary(self.records, date(2026, 8, 31))

        self.assertEqual(summary["profit"], 0)
        self.assertEqual(summary["final_count"], 0)
        self.assertIsNone(summary["roi"])
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(summary["pending_amount"], 500000)


if __name__ == "__main__":
    unittest.main()
