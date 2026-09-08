"""Exercise actual page entrypoints with missing auth configuration."""

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class ProtectedPagesTest(unittest.TestCase):
    def test_direct_pages_stop_before_showing_private_content(self):
        pages = ["main.py", "pages/AI詳細.py", "pages/BET入力.py", "pages/予想結果.py",
                 "pages/収支マップ.py", "pages/本日のAI予想.py", "pages/球団別詳細.py", "pages/試合.py"]
        with patch.dict(os.environ, {"AI_BASEBALL_AUTH_ENABLED": "0"}):
            for page in pages:
                with self.subTest(page=page):
                    app = AppTest.from_file(str(ROOT / page)).run(timeout=20)
                    self.assertFalse(app.exception, page)
                    self.assertTrue(app.error, page)
                    self.assertIn("ログインの設定", app.error[0].value)
                    self.assertEqual(len(app.metric), 0, page)
                    self.assertEqual(len(app.dataframe), 0, page)
                    self.assertFalse(any("保存" in button.label for button in app.button), page)


if __name__ == "__main__":
    unittest.main()
