import json
import os

from backend.browser_engine import (
    AUTH_COOKIE_NAMES,
    GUEST_COOKIE_NAMES,
    PLACEHOLDER_VALUES,
    _has_auth_cookies,
)


# ── Cookie validation ──

def test_guest_cookies_do_not_trigger_auth():
    cookies = [
        {"name": "cna", "value": "abc123"},
        {"name": "_m_h5_tk", "value": "token123"},
        {"name": "_m_h5_tk_enc", "value": "enctoken"},
        {"name": "t", "value": "sometval"},
    ]
    assert not _has_auth_cookies(cookies)


def test_auth_cookies_trigger_connected():
    cookies = [
        {"name": "cookie2", "value": "realauth"},
        {"name": "cna", "value": "abc123"},
    ]
    assert _has_auth_cookies(cookies)


def test_unb_cookie_triggers_connected():
    cookies = [{"name": "unb", "value": "12345"}]
    assert _has_auth_cookies(cookies)


def test_sgcookie_triggers_connected():
    cookies = [{"name": "sgcookie", "value": "sigval"}]
    assert _has_auth_cookies(cookies)


def test_empty_cookies():
    assert not _has_auth_cookies([])


# ── Placeholder / stale value rejection ──

def test_empty_cookie2_rejected():
    assert not _has_auth_cookies([{"name": "cookie2", "value": ""}])


def test_zero_unb_rejected():
    assert not _has_auth_cookies([{"name": "unb", "value": "0"}])


def test_null_string_rejected():
    assert not _has_auth_cookies([{"name": "cookie2", "value": "null"}])


def test_undefined_string_rejected():
    assert not _has_auth_cookies([{"name": "sgcookie", "value": "undefined"}])


def test_deleted_string_rejected():
    assert not _has_auth_cookies([{"name": "cookie2", "value": "deleted"}])


def test_whitespace_only_rejected():
    assert not _has_auth_cookies([{"name": "cookie2", "value": "   "}])


def test_valid_cookie2_with_placeholder_unb():
    cookies = [
        {"name": "cookie2", "value": "realtoken"},
        {"name": "unb", "value": "0"},
    ]
    assert _has_auth_cookies(cookies)


# ── get_session_status (file-based, _verified_connected overrides) ──

def test_session_status_connected_only_when_verified(monkeypatch):
    monkeypatch.setattr("backend.browser_engine._verified_connected", True)
    from backend.browser_engine import get_session_status
    assert get_session_status() == "connected"


def test_session_status_guest_when_not_verified(monkeypatch):
    monkeypatch.setattr("backend.browser_engine._verified_connected", False)
    from backend.browser_engine import get_session_status
    assert get_session_status() == "guest"


def test_session_file_ignored_without_verification(tmp_path, monkeypatch):
    """Even if session_state.json has real auth cookies, status is guest without _verified_connected."""
    state_path = str(tmp_path / "session_state.json")
    state = {
        "cookies": [
            {"name": "cookie2", "value": "authval", "domain": ".goofish.com", "path": "/"},
            {"name": "unb", "value": "999", "domain": ".goofish.com", "path": "/"},
        ]
    }
    with open(state_path, "w") as f:
        json.dump(state, f)
    monkeypatch.setattr("backend.browser_engine.SESSION_STATE_PATH", state_path)
    monkeypatch.setattr("backend.browser_engine._verified_connected", False)
    from backend.browser_engine import get_session_status
    assert get_session_status() == "guest"


def test_session_state_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.browser_engine.SESSION_STATE_PATH", str(tmp_path / "nope.json"))
    monkeypatch.setattr("backend.browser_engine._verified_connected", False)
    from backend.browser_engine import get_session_status
    assert get_session_status() == "guest"


# ── Stale cookie clearing ──

def test_delete_session_file(tmp_path, monkeypatch):
    state_path = str(tmp_path / "session_state.json")
    with open(state_path, "w") as f:
        f.write("{}")
    monkeypatch.setattr("backend.browser_engine.SESSION_STATE_PATH", state_path)
    from backend.browser_engine import _delete_session_file
    _delete_session_file()
    assert not os.path.isfile(state_path)


def test_delete_session_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.browser_engine.SESSION_STATE_PATH", str(tmp_path / "nope.json"))
    from backend.browser_engine import _delete_session_file
    _delete_session_file()  # should not raise


# ── is_verified_connected ──

def test_is_verified_connected_false_by_default(monkeypatch):
    monkeypatch.setattr("backend.browser_engine._verified_connected", False)
    from backend.browser_engine import is_verified_connected
    assert not is_verified_connected()


def test_is_verified_connected_true(monkeypatch):
    monkeypatch.setattr("backend.browser_engine._verified_connected", True)
    from backend.browser_engine import is_verified_connected
    assert is_verified_connected()
