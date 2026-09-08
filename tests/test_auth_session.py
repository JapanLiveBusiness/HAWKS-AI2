import unittest
from pathlib import Path

from auth_session import AuthUser, auth0_enabled, user_bets_path, user_from_claims, user_storage_key


class AuthSessionTest(unittest.TestCase):
    def test_auth_flag_requires_an_explicit_truthy_value(self):
        self.assertTrue(auth0_enabled({"AI_BASEBALL_AUTH_ENABLED": "true"}))
        self.assertFalse(auth0_enabled({}))
        self.assertFalse(auth0_enabled({"AI_BASEBALL_AUTH_ENABLED": "0"}))

    def test_auth0_subject_is_required_and_not_exposed_in_path(self):
        user = user_from_claims(
            {"sub": "auth0|private-user-123", "name": "User", "email": "u@example.com"}
        )
        path = user_bets_path(Path("/data"), user)
        self.assertEqual(path.name, "bet_records.json")
        self.assertEqual(path.parent.parent.name, "users")
        self.assertNotIn("private-user-123", str(path))
        self.assertEqual(len(path.parent.name), 32)

        with self.assertRaises(ValueError):
            user_from_claims({"email": "u@example.com"})

    def test_storage_key_is_stable_and_unauthenticated_access_is_rejected(self):
        self.assertEqual(user_storage_key("auth0|abc"), user_storage_key("auth0|abc"))
        legacy = AuthUser("legacy-single-user", "現行利用者", "", False)
        with self.assertRaises(PermissionError):
            user_bets_path(Path("data"), legacy)


if __name__ == "__main__":
    unittest.main()
