"""Auth0 login helpers and per-user storage routing."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from auth_policy import authorize_claims, validate_auth_config
from auth_login_ui import render_login_screen


AUTH_PROVIDER = "auth0"
AUTH_ENABLED_ENV = "AI_BASEBALL_AUTH_ENABLED"


@dataclass(frozen=True)
class AuthUser:
    subject: str
    name: str
    email: str
    authenticated: bool

    @property
    def display_name(self) -> str:
        return self.name or self.email or "ログインユーザー"


def auth0_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the deployment has mounted its Auth0 configuration."""
    values = os.environ if environ is None else environ
    return str(values.get(AUTH_ENABLED_ENV, "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _claim(user: Any, key: str) -> str:
    try:
        value = user.get(key, "")
    except (AttributeError, TypeError):
        try:
            value = user[key]
        except (KeyError, TypeError):
            value = ""
    return str(value or "").strip()


def user_from_claims(claims: Mapping[str, Any]) -> AuthUser:
    """Build the application identity from validated OIDC identity claims."""
    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise ValueError("Auth0のユーザー識別子を確認できません。")
    return AuthUser(
        subject=subject,
        name=str(claims.get("name") or "").strip(),
        email=str(claims.get("email") or "").strip(),
        authenticated=True,
    )


def _validated_identity() -> AuthUser:
    security = validate_auth_config(st.secrets)
    claims = {key: st.user.get(key) for key in ("sub", "name", "email", "email_verified", "exp", "iat", "auth_time")}
    if claims["auth_time"] is None:
        del claims["auth_time"]
    authorize_claims(claims, security)
    return user_from_claims(claims)


@st.fragment(run_every="60s")
def _session_guard() -> None:
    """Recheck open sessions so expiry/revocation does not require navigation."""
    try:
        if not auth0_enabled() or not st.user.is_logged_in:
            raise PermissionError("Authentication required")
        _validated_identity()
    except Exception:
        st.session_state.clear()
        st.logout()
        st.stop()


def require_auth0() -> AuthUser:
    """Stop before reading application data unless login and authorization pass."""
    try:
        if not auth0_enabled():
            raise ValueError("Auth0 is not enabled")
        validate_auth_config(st.secrets)
    except Exception:
        st.title("AI BASEBALL STUDIO")
        st.error("ログインの設定を確認中です。管理者にお問い合わせください。")
        st.stop()

    if not bool(getattr(st.user, "is_logged_in", False)):
        render_login_screen()
        st.stop()

    try:
        user = _validated_identity()
    except PermissionError as exc:
        st.error(str(exc))
        if st.button("ログアウトして再試行"):
            st.session_state.clear()
            st.logout()
        st.stop()
    except Exception:
        st.error("ログイン情報を確認できません。再ログインしてください。")
        if st.button("ログアウトして再試行"):
            st.session_state.clear()
            st.logout()
        st.stop()

    if st.session_state.get("_auth0_subject") != user.subject:
        st.session_state.clear()
        st.session_state["_auth0_subject"] = user.subject
    _session_guard()
    return user


def user_storage_key(subject: str) -> str:
    """Create a filesystem-safe opaque key without exposing the Auth0 subject."""
    normalized = str(subject or "").strip()
    if not normalized:
        raise ValueError("ユーザー識別子が空です。")
    return sha256(f"auth0:{normalized}".encode("utf-8")).hexdigest()[:32]


def user_bets_path(data_dir: Path, user: AuthUser) -> Path:
    """Route authenticated users to isolated files; never fall back to shared data."""
    base = Path(data_dir)
    if not user.authenticated:
        raise PermissionError("ログインが必要です。")
    return base / "users" / user_storage_key(user.subject) / "bet_records.json"


def render_account_controls(user: AuthUser) -> None:
    """Show the active Auth0 identity and an application-session logout control."""
    if not user.authenticated:
        return
    account = st.container(horizontal=True, horizontal_alignment="right")
    identity = user.email or user.display_name
    account.caption(f":material/account_circle: {identity}")
    if account.button("ログアウト", key="auth0_logout", icon=":material/logout:"):
        st.session_state.clear()
        st.logout()
