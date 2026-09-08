from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bet_store import BetStoreError, BetNotFoundError, save_bets, load_bets, update_bet
from virtual_editor import validate_edit, save_virtual_edit
from virtual_dashboard import calendar_html
from virtual_replay import replay_records, load_verified_scores, load_verified_handicaps


class VirtualEditorTests(unittest.TestCase):
    def values(self, **changes):
        return dict(dict(team="巨人", opponent="広島", bet_amount=100000,
                         handicap_raw="-0.2", status="final", memo="test"), **changes)

    def test_validation(self):
        self.assertEqual(validate_edit(self.values())["bet_amount"], 100000)
        for change in [dict(bet_amount=0), dict(bet_amount="NaN"), dict(bet_amount=1.2),
                       dict(team="広島"), dict(team="bad"), dict(handicap_raw="abc"),
                       dict(status="bad"), dict(memo="x"*2001)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_edit(self.values(**change))

    def test_atomic_audit_preserves_original_and_other_users(self):
        with TemporaryDirectory() as tmp:
            own = Path(tmp)/"own.json"
            other = Path(tmp)/"other.json"
            record = dict(id="one", date="2026-09-05", team="巨人", opponent="広島",
                          bet_amount=100000, handicap=-.2, profit=90000, status="final")
            save_bets(own, [record])
            save_bets(other, [record])
            before = deepcopy(load_bets(own)[0])
            save_virtual_edit(own, before, self.values(bet_amount=200000))
            changed = load_bets(own)[0]
            for k, v in before.items():
                self.assertEqual(changed[k], v)
            self.assertEqual(load_bets(other)[0], before)
            self.assertEqual(changed["virtual_edit"]["bet_amount"], 200000)
            self.assertEqual(len(changed["virtual_edit_history"]), 1)
            replay = replay_records([changed], load_verified_scores())
            self.assertEqual(replay["results"][0]["points_delta"], 36000)
            self.assertEqual(replay["original_records"][0]["profit"], 90000)
            with self.assertRaises(BetStoreError):
                save_virtual_edit(own, before, self.values())
            with self.assertRaises(BetNotFoundError):
                save_virtual_edit(own, dict(before, id="missing"), self.values())

    def test_manual_value_beats_refetched_value(self):
        record = dict(id="two", date="2026-09-03", team="中日", opponent="広島",
                      handicap=.7, status="final", bet_amount=100000,
                      virtual_edit=self.values(team="中日", opponent="広島", bet_amount=200000, handicap_raw="0"))
        row = replay_records([record], load_verified_scores(), handicaps=load_verified_handicaps())["results"][0]
        self.assertEqual(row["points_delta"], -200000)
        self.assertEqual(row["handicap_source"], "日付別編集で指定")
        self.assertEqual(row["stored_handicap"], .7)

    def test_calendar_has_keyboard_accessible_day_links(self):
        html = calendar_html([], "2026-09")
        self.assertEqual(html.count('target="_self"'), 26)
        self.assertIn('?edit_date=2026-09-03#day-editor', html)
        self.assertIn('aria-label="2026-09-03 の内容を編集"', html)
        self.assertNotIn('edit_date=2026-09-31', html)


if __name__ == "__main__":
    unittest.main()
