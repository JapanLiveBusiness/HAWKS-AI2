from copy import deepcopy
from decimal import Decimal
import unittest

from virtual_replay import load_verified_scores, outcome_fraction, raw_handicap, replay_records


class VirtualReplayTests(unittest.TestCase):
    def test_image_cells(self):
        expected = {
            "0.3": [-.3, .7, 1, 1], "0.5": [-.5, .5, 1, 1], "0.7": [-.7, .3, 1, 1],
            "1": [-1, 0, 1, 1], "1.3": [-1, -.3, 1, 1], "1.5": [-1, -.5, 1, 1],
            "1.7": [-1, -.7, 1, 1], "1半": [-1, -1, 1, 1], "1半3": [-1, -1, .7, 1],
            "1半5": [-1, -1, .5, 1], "1半7": [-1, -1, .3, 1], "2": [-1, -1, 0, 1],
        }
        for token, values in expected.items():
            for margin, expected_value in enumerate(values):
                with self.subTest(token=token, margin=margin):
                    self.assertEqual(outcome_fraction(3 + margin, 3, token), Decimal(str(expected_value)))
                    self.assertEqual(outcome_fraction(3, 3 + margin, "-" + token), -Decimal(str(expected_value)))

    def test_input_validation_and_unlisted_values(self):
        for token in ("0.6", "1半8", "nan", "Infinity", "", "--1"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                outcome_fraction(1, 1, token)
        for score in (-1, True, 1.5, None):
            with self.assertRaises(ValueError):
                outcome_fraction(score, 1, "1")

    def test_original_notation_is_required_for_legacy_half(self):
        for value in (1.5, "1.5", -1.5, .5):
            with self.assertRaises(ValueError):
                raw_handicap({"handicap": value})
        self.assertEqual(raw_handicap({"handicap": 1.5, "handicap_raw": "1半"}), "1半")
        self.assertEqual(raw_handicap({"handicap": 1.5, "handicap_raw": "1.5"}), "1.5")

    def record(self, **overrides):
        return dict({"id": "one", "date": "2026-09-05", "team": "オリックス", "opponent": "ロッテ",
                     "status": "final", "handicap": .3, "bet_amount": 10000,
                     "team_score": 7, "opponent_score": 6, "profit": 9000}, **overrides)

    def test_ninth_inning_used_without_mutation(self):
        records = [self.record()]
        original = deepcopy(records)
        report = replay_records(records, load_verified_scores())
        row = report["results"][0]
        self.assertEqual((row["team_score_9"], row["opponent_score_9"]), (6, 6))
        self.assertEqual(row["points_delta"], -3000)
        self.assertEqual(records, original)
        self.assertEqual(report["original_records"], original)
        self.assertTrue(report["virtual_only"])
        self.assertEqual(report, replay_records(records, load_verified_scores()))

    def test_receiving_side_and_positive_rate(self):
        row = replay_records([self.record(team="ロッテ", opponent="オリックス", handicap=-.3)], load_verified_scores())["results"][0]
        self.assertEqual(row["points_delta"], 2700)

    def test_giants_receiving_two_tenths_tied_after_nine(self):
        original = self.record(team="巨人", opponent="広島", handicap=-.2,
                               bet_amount=100000, team_score=10, opponent_score=5, profit=90000)
        row = replay_records([original], load_verified_scores())["results"][0]
        self.assertEqual((row["team_score_9"], row["opponent_score_9"]), (5, 5))
        self.assertEqual(row["points_delta"], 18000)
        self.assertEqual(original["profit"], 90000)
        giving = self.record(team="広島", opponent="巨人", handicap=.2, bet_amount=100000)
        self.assertEqual(replay_records([giving], load_verified_scores())["results"][0]["points_delta"], -20000)

    def test_partial_credit_for_other_confirmed_handicaps(self):
        for token, amount in [("-0.3",27000),("-0.5",45000),("-0.7",63000),
                              ("0.3",-30000),("0.5",-50000),("0.7",-70000)]:
            with self.subTest(token=token):
                row = replay_records([self.record(handicap_raw=token, bet_amount=100000)], load_verified_scores())["results"][0]
                self.assertEqual(row["points_delta"], amount)

    def test_missing_ambiguous_pending_cancelled(self):
        records = [self.record(date="2026-08-01"), self.record(handicap=1.5),
                   self.record(status="pending"), self.record(date="2026-09-06", team="ヤクルト", opponent="中日")]
        rows = replay_records(records, load_verified_scores())["results"]
        self.assertEqual([r["status"] for r in rows], ["review", "review", "pending", "cancelled"])
        self.assertTrue(all(r["points_delta"] is None for r in rows))

    def test_no_missing_score_or_amount_zero_fallback(self):
        for changes in ({"bet_amount": None}, {"bet_amount": -1}, {"bet_amount": "NaN"}):
            row = replay_records([self.record(**changes)], load_verified_scores())["results"][0]
            self.assertEqual(row["status"], "review")
        games = deepcopy(load_verified_scores())
        for game in games:
            game.pop("home_9", None)
        self.assertEqual(replay_records([self.record()], games)["results"][0]["status"], "review")

    def test_duplicate_match_not_guessed(self):
        games = load_verified_scores()
        self.assertEqual(replay_records([self.record()], games + games)["results"][0]["status"], "review")

    def test_snapshot_count_and_changed_games(self):
        games = load_verified_scores()
        self.assertEqual(len(games), 30)
        self.assertEqual(sum(g["status"] == "cancelled" for g in games), 1)
        for day, home, away, score in [("2026-09-02", "巨人", "DeNA", 1), ("2026-09-05", "広島", "巨人", 5)]:
            row = replay_records([self.record(date=day, team=home, opponent=away)], games)["results"][0]
            self.assertEqual((row["team_score_9"], row["opponent_score_9"]), (score, score))


if __name__ == "__main__":
    unittest.main()
