from datetime import date
import json
from unittest.mock import Mock

import pytest

import handenomori_client as client

FORM = b'''<form method="post"><input type="text" name="swpm_user_name">
<input type="password" name="swpm_password"><input type="hidden" name="nonce" value="test-nonce">
<input type="submit" name="swpm-login" value="Log In"></form>'''
MEMBER = b'<a href="/membership-login/?swpm-logout=true">Logout</a>'
PAGE = "https://handenomori.com/jpb/20260906/"


def response(content, status=200, location=None):
    return Mock(content=content, status_code=status, headers={"Location": location} if location else {})


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("HANDENOMORI_EMAIL", "test@example.invalid")
    monkeypatch.setenv("HANDENOMORI_PASSWORD", "test-only-password")
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=session)
    monkeypatch.setattr(client.requests, "Session", factory)
    return session, factory


def test_each_fetch_logs_in_and_preserves_nonce(setup):
    session, factory = setup
    session.request.side_effect = [response(FORM), response(b"", 302, "/"), response(MEMBER), response(MEMBER)] * 2
    assert client.fetch_member_page(PAGE) == MEMBER
    assert client.fetch_member_page(PAGE) == MEMBER
    assert factory.call_count == 2
    assert session.__exit__.call_count == 2
    calls = session.request.call_args_list
    assert [c.args[0] for c in calls] == ["GET", "POST", "GET", "GET"] * 2
    assert calls[1].kwargs["data"] == {"swpm_user_name": "test@example.invalid", "swpm_password": "test-only-password", "nonce": "test-nonce", "swpm-login": "Log In"}
    assert all(c.kwargs["allow_redirects"] is False for c in calls)


@pytest.mark.parametrize("stage", ["login", "data"])
def test_guest_page_is_never_accepted(setup, stage):
    session, _ = setup
    session.request.side_effect = [response(FORM), response(FORM)] if stage == "login" else [response(FORM), response(MEMBER), response(FORM)]
    with pytest.raises(client.HandenomoriError):
        client.fetch_member_page(PAGE)
    assert session.request.call_count == (2 if stage == "login" else 3)


@pytest.mark.parametrize("target", ["https://evil.invalid/", "http://handenomori.com/", "https://handenomori.com.evil.invalid/"])
def test_redirect_never_leaks_credentials(setup, target):
    session, _ = setup
    session.request.side_effect = [response(FORM), response(b"", 307, target)]
    with pytest.raises(client.HandenomoriError):
        client.fetch_member_page(PAGE)
    assert session.request.call_count == 2


def test_untrusted_form_action_not_submitted(setup):
    session, _ = setup
    session.request.return_value = response(FORM.replace(b'<form ', b'<form action="https://evil.invalid/" '))
    with pytest.raises(client.HandenomoriError):
        client.fetch_member_page(PAGE)
    assert session.request.call_count == 1


def test_transport_errors_are_sanitized(setup):
    session, _ = setup
    session.request.side_effect = RuntimeError("secret-response-body test-only-password")
    with pytest.raises(client.HandenomoriError) as error:
        client.fetch_member_page(PAGE)
    assert "test-only-password" not in str(error.value)
    assert "secret-response" not in str(error.value)


def test_credentials_file_and_missing_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv("HANDENOMORI_EMAIL", raising=False)
    monkeypatch.delenv("HANDENOMORI_PASSWORD", raising=False)
    path = tmp_path / "credentials.json"
    monkeypatch.setenv("HANDENOMORI_CREDENTIALS_FILE", str(path))
    with pytest.raises(client.HandenomoriError):
        client.load_credentials()
    path.write_text(json.dumps({"email": "test@example.invalid", "password": "test-only"}))
    assert client.load_credentials() == ("test@example.invalid", "test-only")
    monkeypatch.setenv("HANDENOMORI_EMAIL", "partial@example.invalid")
    with pytest.raises(client.HandenomoriError):
        client.load_credentials()


def test_daily_fetch_and_hawks_column_mapping(monkeypatch):
    import game_calendar
    import handicap_source
    markup = '''<div class="game-detail2"><span class="detail-card-team">ソフトバンク</span>
    <span class="detail-card-team">西武</span><table><tr>
    <td class="single-handi-handi">0.7</td><td class="single-handi-handi"></td></tr></table></div>'''
    fetch = Mock(return_value=markup)
    monkeypatch.setattr(game_calendar, "fetch_member_page", fetch)
    monkeypatch.setattr(handicap_source, "fetch_member_page", fetch)
    assert game_calendar.fetch_daily_handicaps(date(2026, 9, 6))[0]["home_handicap"] == "0.7"
    result = handicap_source.fetch_hawks_handicap(date(2026, 9, 6))
    assert (result["favored_team"], result["handicap_score"]) == ("ソフトバンク", -0.7)
    fetch.side_effect = client.HandenomoriError("failed")
    assert game_calendar.fetch_daily_handicaps(date(2026, 9, 6)) == []
    with pytest.raises(client.HandenomoriError):
        game_calendar.fetch_daily_handicaps(date(2026, 9, 6), strict=True)
