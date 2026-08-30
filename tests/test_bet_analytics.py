import unittest

from bet_analytics import bet_amount, calculate_hit_rate, sort_bets


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


if __name__ == "__main__":
    unittest.main()
