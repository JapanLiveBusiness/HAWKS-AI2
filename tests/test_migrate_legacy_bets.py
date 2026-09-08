import json
from pathlib import Path
import tempfile
import unittest

from scripts.migrate_legacy_bets import migrate_legacy_bets


class LegacyBetMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        (self.data_dir / "bet_records.json").write_text(
            json.dumps([{"id": "legacy-1", "team": "ソフトバンク"}], ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dry_run_does_not_write_target(self):
        target, count = migrate_legacy_bets(self.data_dir, "auth0|owner")
        self.assertEqual(count, 1)
        self.assertFalse(target.exists())
        self.assertNotIn("auth0|owner", str(target))

    def test_apply_preserves_source_and_refuses_unconfirmed_overwrite(self):
        target, count = migrate_legacy_bets(
            self.data_dir,
            "auth0|owner",
            apply=True,
        )
        self.assertEqual(count, 1)
        self.assertTrue(target.exists())
        self.assertTrue((self.data_dir / "bet_records.json").exists())
        with self.assertRaises(FileExistsError):
            migrate_legacy_bets(self.data_dir, "auth0|owner", apply=True)


if __name__ == "__main__":
    unittest.main()
