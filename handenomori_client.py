"""Authenticated, per-fetch Handenomori sessions. Never fall back to guest data."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

LOGIN_URL = "https://handenomori.com/membership-login/"
DEFAULT_CREDENTIALS_FILE = "/run/handenomori/credentials.json"


class HandenomoriError(RuntimeError):
    """Safe public error; never includes credentials or response bodies."""


def load_credentials():
    email = os.environ.get("HANDENOMORI_EMAIL", "")
    password = os.environ.get("HANDENOMORI_PASSWORD", "")
    if not email and not password:
        try:
            payload = json.loads(Path(os.environ.get(
                "HANDENOMORI_CREDENTIALS_FILE", DEFAULT_CREDENTIALS_FILE
            )).read_text(encoding="utf-8"))
            email, password = payload.get("email"), payload.get("password")
        except (OSError, ValueError, AttributeError):
            raise HandenomoriError("ハンデの森の認証情報が未設定です") from None
    if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or not password:
        raise HandenomoriError("ハンデの森の認証情報が未設定です")
    return email.strip(), password


def _trusted(url):
    parts = urlsplit(url)
    return (parts.scheme == "https" and parts.netloc == "handenomori.com"
            and not parts.username and not parts.password)


def _request(session, method, url, timeout, data=None):
    # Check redirects ourselves so a changed login form/redirect can never send
    # credentials or cookies to a different host or to plain HTTP.
    for _ in range(6):
        if not _trusted(url):
            raise HandenomoriError("ハンデの森の転送先を確認できません")
        response = session.request(method, url, data=data, timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        if response.status_code not in (301, 302, 303, 307, 308):
            return response
        target = urljoin(url, response.headers.get("Location", ""))
        if not _trusted(target):
            raise HandenomoriError("ハンデの森の転送先を確認できません")
        if response.status_code in (301, 302, 303):
            method, data = "GET", None
        url = target
    raise HandenomoriError("ハンデの森の転送回数が上限を超えました")


def _authenticated(content):
    soup = BeautifulSoup(content, "html.parser")
    return any(
        _trusted(urljoin(LOGIN_URL, link["href"]))
        and parse_qs(urlsplit(link["href"]).query).get("swpm-logout") == ["true"]
        for link in soup.select("a[href]")
    )


def fetch_member_page(url, timeout=12):
    """Log in anew, verify membership, fetch one page, then discard the session."""
    if not _trusted(url):
        raise HandenomoriError("ハンデの森以外のURLは取得できません")
    email, password = load_credentials()
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": "Mozilla/5.0"})
            login = _request(session, "GET", LOGIN_URL, timeout)
            soup = BeautifulSoup(login.content, "html.parser")
            password_field = soup.select_one('form input[type="password"][name]')
            if password_field is None:
                raise HandenomoriError("ハンデの森のログインフォームを確認できません")
            form = password_field.find_parent("form")
            username_field = form.select_one('input[type="email"][name], input[type="text"][name]')
            action = urljoin(LOGIN_URL, form.get("action") or LOGIN_URL)
            if username_field is None or not _trusted(action):
                raise HandenomoriError("ハンデの森のログインフォームを確認できません")
            fields = {node["name"]: node.get("value", "")
                      for node in form.select('input[type="hidden"][name], input[type="submit"][name]')}
            fields[username_field["name"]] = email
            fields[password_field["name"]] = password
            logged_in = _request(session, "POST", action, timeout, fields)
            if not _authenticated(logged_in.content):
                raise HandenomoriError("ハンデの森へのログインに失敗しました")
            page = _request(session, "GET", url, timeout)
            if not _authenticated(page.content):
                raise HandenomoriError("ハンデの森のログイン状態を確認できません")
            return page.content
    except HandenomoriError:
        raise
    except Exception:
        raise HandenomoriError("ハンデの森の認証付き取得に失敗しました") from None
