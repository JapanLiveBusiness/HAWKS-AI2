from copy import deepcopy
from decimal import Decimal
import unittest

from virtual_replay import load_verified_handicaps, load_verified_scores, outcome_fraction, replay_records


class RefetchedHandicapTests(unittest.TestCase):
    def test_additional_partial_fractions_and_reverse_sides(self):
        for token, values in {"0.8": ["-.8", ".2", "1", "1"],
                              "1.1": ["-1", "-.1", "1", "1"],
                              "1.6": ["-1", "-.6", "1", "1"]}.items():
            for margin, value in enumerate(values):
                with self.subTest(token=token, margin=margin):
                    self.assertEqual(outcome_fraction(3 + margin, 3, token), Decimal(value))
                    self.assertEqual(outcome_fraction(3, 3 + margin, "-" + token), -Decimal(value))

    def test_seven_refetched_values_and_source_preservation(self):
        evidence = load_verified_handicaps()
        self.assertEqual(len(evidence), 7)
        amounts = [200000, 200000, 300000, 300000, 200000, 200000, 100000]
        expected = [-200000, -160000, 270000, 270000, -200000, -200000, -100000]
        records = [dict(id=str(i), date=h["date"], team=h["team"], opponent=h["opponent"],
                        status="final", handicap=1.5, profit=999, bet_amount=amounts[i])
                   for i, h in enumerate(evidence)]
        before = deepcopy(records)
        report = replay_records(records, load_verified_scores(), handicaps=evidence)
        self.assertEqual([r["points_delta"] for r in report["results"]], expected)
        self.assertTrue(all(r["status"] == "calculated" for r in report["results"]))
        for row, h in zip(report["results"], evidence):
            self.assertEqual(row["stored_handicap"], 1.5)
            self.assertEqual(row["handicap_raw"], h["handicap_raw"])
            self.assertEqual(row["handicap_source"], h["source_url"])
        self.assertEqual(records, before)
        self.assertEqual(report["original_records"], before)
        self.assertEqual(report["handicap_evidence"], evidence)

    def test_duplicate_evidence_fails_closed_and_pending_not_finalized(self):
        h = load_verified_handicaps()[0]
        record = dict(h, status="final", handicap=-.8, bet_amount=100000)
        result = replay_records([record], load_verified_scores(), handicaps=[h, h])["results"][0]
        self.assertEqual(result["status"], "review")
        record["status"] = "pending"
        result = replay_records([record], load_verified_scores(), handicaps=[h])["results"][0]
        self.assertEqual(result["status"], "pending")

    def test_evidence_requires_exact_date_and_ordered_teams(self):
        h = load_verified_handicaps()[1]
        record = dict(h, status="final", handicap_raw="0.3", bet_amount=100000)
        changed = dict(h, date="2026-09-06")
        row = replay_records([record], load_verified_scores(), handicaps=[changed])["results"][0]
        self.assertFalse(row.get("handicap_refetched", False))
        self.assertEqual(row["points_delta"], -30000)
        changed = dict(h, team=h["opponent"], opponent=h["team"])
        row = replay_records([record], load_verified_scores(), handicaps=[changed])["results"][0]
        self.assertFalse(row.get("handicap_refetched", False))


if __name__ == "__main__":
    unittest.main()
