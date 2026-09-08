import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import auth_session
from auth_session import AuthUser, require_auth0, user_bets_path
from auth_policy import PRODUCTION_ORIGIN


class StopPage(BaseException):
    pass


class Claims(dict):
    is_logged_in = True


def settings():
    return {"auth": {"redirect_uri": PRODUCTION_ORIGIN + "/oauth2callback",
                     "cookie_secret": "test-only-cookie-secret-" * 3,
                     "auth0": {"client_id": "test-id", "client_secret": "test-secret",
                               "server_metadata_url": "https://example.jp.auth0.com/.well-known/openid-configuration",
                               "client_kwargs": {"prompt": "login"}}},
            "security": {"access_mode": "all_verified"}}


class AuthGateTest(unittest.TestCase):
    def setUp(self):
        self.ui = MagicMock()
        self.ui.stop.side_effect = StopPage
        self.ui.button.return_value = False
        self.ui.secrets = settings()
        self.ui.session_state = {}
        self.ui.user = Claims(sub="auth0|one", email="owner@example.com", email_verified=True,
                              iat=1000, exp=40000)
        self.patchers = [patch.object(auth_session, "st", self.ui),
                         patch.object(auth_session, "_session_guard"),
                         patch.object(auth_session, "render_login_screen"),
                         patch.dict(os.environ, {"AI_BASEBALL_AUTH_ENABLED": "1"}),
                         patch("auth_policy.time.time", return_value=2000)]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_missing_configuration_or_disabled_auth_never_returns_legacy_user(self):
        for secrets, enabled in (({}, "1"), (settings(), "0")):
            self.ui.secrets = secrets
            with patch.dict(os.environ, {"AI_BASEBALL_AUTH_ENABLED": enabled}), self.assertRaises(StopPage):
                require_auth0()
        self.ui.login.assert_not_called()

    def test_logged_out_session_stops_before_data_access(self):
        self.ui.user.is_logged_in = False
        with self.assertRaises(StopPage):
            require_auth0()
        auth_session.render_login_screen.assert_called_once_with()

    def test_invalid_identity_and_unverified_email_stop_page(self):
        for changes in ({"sub": ""}, {"email_verified": False}, {"exp": 1}):
            saved = self.ui.user.copy()
            self.ui.user.update(changes)
            with self.subTest(changes=changes), self.assertRaises(StopPage):
                require_auth0()
            self.ui.user = Claims(saved)

    def test_account_switch_clears_previous_users_widget_state(self):
        self.ui.session_state.update({"_auth0_subject": "auth0|previous", "bet_import": "private-record"})
        user = require_auth0()
        self.assertEqual(user.subject, "auth0|one")
        self.assertEqual(self.ui.session_state, {"_auth0_subject": "auth0|one"})

    def test_unauthenticated_paths_rejected_and_user_paths_are_distinct(self):
        with self.assertRaises(PermissionError):
            user_bets_path(Path("data"), AuthUser("legacy-single-user", "", "", False))
        one = user_bets_path(Path("data"), AuthUser("auth0|one", "", "", True))
        two = user_bets_path(Path("data"), AuthUser("../../other", "", "", True))
        self.assertNotEqual(one, two)
        self.assertEqual(two.parent.parent, Path("data/users"))


if __name__ == "__main__":
    unittest.main()
