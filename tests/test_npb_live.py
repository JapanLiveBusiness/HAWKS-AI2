import unittest
from datetime import date

from game_calendar import merge_game_sources
from npb_live import find_score_url, parse_box_score, parse_play_by_play


class NpbLiveTest(unittest.TestCase):
    def test_find_score_url_uses_matchup_codes(self):
        content = """
        <table><tr><td><a href="/scores/2026/0905/h-l-20/">ソフトバンク戦</a></td></tr></table>
        """
        url = find_score_url(content, date(2026, 9, 5), "ソフトバンク", "西武")
        self.assertEqual(url, "https://npb.jp/scores/2026/0905/h-l-20/box.html")

    def test_parse_box_score_orients_totals_by_team(self):
        content = """
        <p>試合終了</p>
        <table>
          <tr><th>球団</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>6</th><th>7</th><th>8</th><th>9</th><th>計</th></tr>
          <tr><td>西武</td><td>0</td><td>0</td><td>1</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>1</td></tr>
          <tr><td>福岡ソフトバンク</td><td>1</td><td>0</td><td>0</td><td>0</td><td>2</td><td>0</td><td>0</td><td>0</td><td>X</td><td>3</td></tr>
        </table>
        """
        result = parse_box_score(content, "ソフトバンク", "西武")
        self.assertEqual(result["status"], "final")
        self.assertEqual(result["home_score"], 3)
        self.assertEqual(result["away_score"], 1)

    def test_parse_active_plate_appearance(self):
        content = """
        <h3>7回裏（ソフトバンクの攻撃）</h3>
        <table><tr><td>1アウト</td><td>1塁 3塁</td><td>打者A</td><td>2－1</td><td></td></tr></table>
        """
        result = parse_play_by_play(content)
        self.assertEqual(result["inning"], 7)
        self.assertEqual(result["inning_half"], "裏")
        self.assertEqual(result["outs"], 1)
        self.assertEqual(result["bases"], {1: True, 2: False, 3: True})
        self.assertEqual(result["balls"], 2)
        self.assertEqual(result["strikes"], 1)
        self.assertEqual(result["current_batter"], "打者A")

    def test_parse_play_by_play_skips_future_empty_inning_headings(self):
        content = """
        <h3>2回裏（ソフトバンクの攻撃）</h3>
        <table><tr><td>1アウト</td><td>なし</td><td>打者B</td><td>1－1</td><td></td></tr></table>
        <h3>3回表（西武の攻撃）</h3><table><tr><th>試合前</th></tr></table>
        <h3>9回裏（ソフトバンクの攻撃）</h3><table><tr><th>試合前</th></tr></table>
        """

        result = parse_play_by_play(content)

        self.assertEqual(result["inning"], 2)
        self.assertEqual(result["inning_half"], "裏")
        self.assertEqual(result["current_batter"], "打者B")

    def test_live_update_keeps_match_identity_for_merge(self):
        scheduled = {
            "date": "2026-09-05",
            "home": "ソフトバンク",
            "away": "西武",
            "status": "scheduled",
        }
        live = {
            "date": "2026-09-05",
            "home": "ソフトバンク",
            "away": "西武",
            "status": "live",
            "home_score": 2,
            "away_score": 1,
        }
        merged = merge_game_sources([scheduled], [live])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["status"], "live")
        self.assertEqual(merged[0]["home_score"], 2)


if __name__ == "__main__":
    unittest.main()
