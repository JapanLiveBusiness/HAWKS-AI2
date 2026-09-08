from io import BytesIO
import unittest

import pandas as pd

from bet_transfer import BetSpreadsheetError, bets_to_xlsx, normalize_import_frame, read_bet_spreadsheet


class BetTransferTest(unittest.TestCase):
    def test_excel_round_trip_recalculates_settlement_values(self):
        original = [
            {
                "id": "bet-1",
                "date": "2026-09-05",
                "time": "18:00",
                "team": "ソフトバンク",
                "opponent": "西武",
                "handicap": 1.5,
                "bet_amount": 10000,
                "status": "final",
                "team_score": 5,
                "opponent_score": 3,
                "result": "loss",
                "profit": -999999,
                "memo": "通常BET",
            }
        ]
        payload = bets_to_xlsx(original)
        imported = read_bet_spreadsheet(payload, "history.xlsx")
        self.assertEqual(imported[0]["result"], "win")
        self.assertEqual(imported[0]["profit"], 9000)
        self.assertEqual(imported[0]["adjusted_score"], 3.5)

    def test_formula_like_text_is_exported_as_text_and_restored(self):
        payload = bets_to_xlsx(
            [
                {
                    "id": "bet-formula",
                    "date": "2026-09-05",
                    "time": "18:00",
                    "team": "ソフトバンク",
                    "opponent": "西武",
                    "bet_amount": 1000,
                    "status": "pending",
                    "memo": "=HYPERLINK(\"https://invalid.example\")",
                }
            ]
        )
        workbook_frame = pd.read_excel(BytesIO(payload), sheet_name="BET履歴")
        self.assertTrue(str(workbook_frame.loc[0, "メモ"]).startswith("'="))
        imported = read_bet_spreadsheet(payload, "history.xlsx")
        self.assertTrue(imported[0]["memo"].startswith("=HYPERLINK"))

    def test_invalid_final_record_is_rejected(self):
        frame = pd.DataFrame(
            [
                {
                    "試合日": "2026-09-05",
                    "BET先": "ソフトバンク",
                    "対戦相手": "西武",
                    "BET金額（円）": 10000,
                    "状態": "確定",
                    "BET先得点": "",
                    "対戦相手得点": 3,
                }
            ]
        )
        with self.assertRaises(BetSpreadsheetError):
            normalize_import_frame(frame)

    def test_legacy_bet_units_are_exported_as_yen(self):
        payload = bets_to_xlsx(
            [
                {
                    "id": "legacy-bet",
                    "date": "2026-09-05",
                    "team": "ソフトバンク",
                    "opponent": "西武",
                    "bet_units": 2.5,
                    "status": "pending",
                }
            ]
        )
        imported = read_bet_spreadsheet(payload, "history.xlsx")
        self.assertEqual(imported[0]["bet_amount"], 25000)


if __name__ == "__main__":
    unittest.main()
