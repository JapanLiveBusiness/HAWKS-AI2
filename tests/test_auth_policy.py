import copy
import unittest

from auth_policy import PRODUCTION_ORIGIN, authorize_claims, validate_auth_config


def configuration():
    return {
        "auth": {
            "redirect_uri": PRODUCTION_ORIGIN + "/oauth2callback",
            "cookie_secret": "test-only-not-a-real-secret-" * 3,
            "auth0": {
                "client_id": "test-client",
                "client_secret": "test-secret",
                "server_metadata_url": "https://example.jp.auth0.com/.well-known/openid-configuration",
                "client_kwargs": {"prompt": "login"},
            },
        },
        "security": {"access_mode": "all_verified", "session_max_age_seconds": 28800},
    }


def identity(**changes):
    return {"sub": "auth0|one", "email": "owner@example.com", "email_verified": True,
            "iat": 1000, "exp": 40000, **changes}


class AuthPolicyTest(unittest.TestCase):
    def test_verified_registration_allowed_and_unverified_rejected(self):
        policy = validate_auth_config(configuration())
        authorize_claims(identity(), policy, now=2000)
        for value in (False, "true", 1, None):
            with self.subTest(value=value), self.assertRaises(PermissionError):
                authorize_claims(identity(email_verified=value), policy, now=2000)

    def test_allowlist_denies_other_users_and_checks_exact_verified_email(self):
        policy = {"access_mode": "allowlist", "allowed_emails": ["OWNER@example.com"]}
        authorize_claims(identity(), policy, now=2000)
        for email in ("other@example.com", "owner@example.com.attacker.test", ""):
            with self.subTest(email=email), self.assertRaises(PermissionError):
                authorize_claims(identity(email=email), policy, now=2000)
        with self.assertRaises(PermissionError):
            authorize_claims(identity(email_verified=False), policy, now=2000)
        authorize_claims(identity(), {"allowed_subjects": ["auth0|one"]}, now=2000)
        with self.assertRaises(PermissionError):
            authorize_claims(identity(sub="auth0|two"), {"allowed_subjects": ["auth0|one"]}, now=2000)

    def test_expired_and_malformed_claims_denied(self):
        for changes in ({"exp": 2000}, {"iat": 999999}, {"iat": None}, {"exp": None},
                        {"exp": "nan"}, {"iat": "inf"}, {"sub": ""}):
            with self.subTest(changes=changes), self.assertRaises(PermissionError):
                authorize_claims(identity(**changes), {"access_mode": "all_verified"}, now=2000)

    def test_absolute_session_lifetime_cannot_be_extended_by_new_page(self):
        with self.assertRaises(PermissionError):
            authorize_claims(identity(), {"access_mode": "all_verified"}, now=29800)
        with self.assertRaises(PermissionError):
            authorize_claims(identity(auth_time=100, iat=2000), {"access_mode": "all_verified", "session_max_age_seconds": 1000}, now=2500)

    def test_incomplete_configuration_fails_closed(self):
        for key in ("cookie_secret", "redirect_uri", "auth0"):
            config = configuration()
            del config["auth"][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_auth_config(config)
        config = configuration()
        config["security"] = {}
        with self.assertRaises(ValueError):
            validate_auth_config(config)

    def test_https_exact_callback_and_token_protection(self):
        for callback in ("http://ai-baseball.f-polaris.jp/oauth2callback", "https://evil.test/oauth2callback",
                         PRODUCTION_ORIGIN + "/oauth2callback?next=https://evil.test"):
            config = configuration()
            config["auth"]["redirect_uri"] = callback
            with self.subTest(callback=callback), self.assertRaises(ValueError):
                validate_auth_config(config)
        for metadata in ("http://example.jp.auth0.com/.well-known/openid-configuration",
                         "https://user:pass@example.com/.well-known/openid-configuration"):
            config = configuration()
            config["auth"]["auth0"]["server_metadata_url"] = metadata
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                validate_auth_config(config)
        config = configuration()
        config["auth"]["expose_tokens"] = ["access"]
        with self.assertRaises(ValueError):
            validate_auth_config(config)

    def test_unknown_policy_or_unbounded_lifetime_rejected(self):
        for policy in ({"access_mode": "anything"}, {"session_max_age_seconds": 999999},
                       {"session_max_age_seconds": True}, {"allowed_emails": "owner@example.com"}):
            config = copy.deepcopy(configuration())
            config["security"].update(policy)
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                validate_auth_config(config)


if __name__ == "__main__":
    unittest.main()
