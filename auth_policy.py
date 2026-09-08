"""Validate server-side OIDC configuration and access policy (no network calls)."""

from __future__ import annotations

import math
import time
from typing import Any, Mapping
from urllib.parse import urlsplit

PRODUCTION_ORIGIN = "https://ai-baseball.f-polaris.jp"


def validate_auth_config(secrets: Mapping[str, Any]) -> Mapping[str, Any]:
    auth = secrets.get("auth", {})
    provider = auth.get("auth0", {})
    security = secrets.get("security", {})
    if auth.get("redirect_uri") != PRODUCTION_ORIGIN + "/oauth2callback":
        raise ValueError("Auth0 callback must use the canonical production HTTPS URL")
    for value in (auth.get("cookie_secret"), provider.get("client_id"), provider.get("client_secret")):
        if not isinstance(value, str) or not value.strip() or "replace-with" in value:
            raise ValueError("Auth0 configuration is incomplete")
    if len(auth["cookie_secret"]) < 32:
        raise ValueError("Auth0 cookie secret is too short")
    metadata = urlsplit(str(provider.get("server_metadata_url", "")))
    if (metadata.scheme != "https" or not metadata.hostname or metadata.username
            or metadata.password or metadata.port not in (None, 443)
            or metadata.path != "/.well-known/openid-configuration"
            or metadata.query or metadata.fragment or "YOUR_" in metadata.netloc):
        raise ValueError("Invalid HTTPS OIDC metadata URL")
    if auth.get("expose_tokens"):
        raise ValueError("Do not expose OIDC tokens to application code")
    if provider.get("client_kwargs", {}).get("prompt") != "login":
        raise ValueError("Auth0 must request a fresh login")
    mode = security.get("access_mode", "allowlist")
    if mode not in ("allowlist", "all_verified"):
        raise ValueError("Unknown access mode")
    for name in ("allowed_subjects", "allowed_emails"):
        values = security.get(name, [])
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError("Access lists must contain non-empty strings")
    if mode == "allowlist" and not (security.get("allowed_subjects") or security.get("allowed_emails")):
        raise ValueError("At least one authorized user must be configured")
    duration = security.get("session_max_age_seconds", 28800)
    if isinstance(duration, bool) or not isinstance(duration, int) or not 300 <= duration <= 28800:
        raise ValueError("Session duration must be between 5 minutes and 8 hours")
    return security


def authorize_claims(claims: Mapping[str, Any], security: Mapping[str, Any], *, now: float | None = None) -> None:
    """Apply app authorization only to claims already validated by Streamlit OIDC."""
    if not str(claims.get("sub") or "").strip():
        raise PermissionError("ログイン情報を確認できません。再ログインしてください。")
    if claims.get("email_verified") is not True:
        raise PermissionError("メールアドレスの確認を完了してから再ログインしてください。")
    current = time.time() if now is None else now
    try:
        expiry = float(claims["exp"])
        issued = float(claims["auth_time"] if "auth_time" in claims else claims["iat"])
        if not math.isfinite(expiry) or not math.isfinite(issued):
            raise ValueError("Invalid timestamp")
    except (KeyError, TypeError, ValueError, OverflowError):
        raise PermissionError("ログインの有効期限を確認できません。再ログインしてください。") from None
    if current >= expiry or issued > current + 60 or current - issued >= security.get("session_max_age_seconds", 28800):
        raise PermissionError("ログインの有効期限が切れました。再ログインしてください。")
    mode = security.get("access_mode", "allowlist")
    subjects = security.get("allowed_subjects", [])
    emails = {email.strip().casefold() for email in security.get("allowed_emails", [])}
    if mode == "all_verified":
        return
    if mode != "allowlist" or (claims["sub"] not in subjects and str(claims.get("email") or "").strip().casefold() not in emails):
        raise PermissionError("このアプリの利用許可がありません。管理者にお問い合わせください。")
