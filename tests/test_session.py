import json

from backend.browser_engine import AUTH_COOKIE_NAMES, GUEST_COOKIE_NAMES, _has_auth_cookies


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


def test_empty_cookie2_rejected():
    cookies = [{"name": "cookie2", "value": ""}]
    assert not _has_auth_cookies(cookies)


def test_zero_unb_rejected():
    cookies = [{"name": "unb", "value": "0"}]
    assert not _has_auth_cookies(cookies)


def test_null_string_rejected():
    cookies = [{"name": "cookie2", "value": "null"}]
    assert not _has_auth_cookies(cookies)


def test_undefined_string_rejected():
    cookies = [{"name": "sgcookie", "value": "undefined"}]
    assert not _has_auth_cookies(cookies)


def test_deleted_string_rejected():
    cookies = [{"name": "cookie2", "value": "deleted"}]
    assert not _has_auth_cookies(cookies)


def test_whitespace_only_rejected():
    cookies = [{"name": "cookie2", "value": "   "}]
    assert not _has_auth_cookies(cookies)


def test_valid_cookie2_with_placeholder_unb():
    cookies = [
        {"name": "cookie2", "value": "realtoken"},
        {"name": "unb", "value": "0"},
    ]
    assert _has_auth_cookies(cookies)


def test_session_state_reload(tmp_path, monkeypatch):
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
    assert get_session_status() == "connected"


def test_session_state_guest_only(tmp_path, monkeypatch):
    state_path = str(tmp_path / "session_state.json")
    state = {
        "cookies": [
            {"name": "cna", "value": "guestval", "domain": ".goofish.com", "path": "/"},
            {"name": "_m_h5_tk", "value": "guesttoken", "domain": ".goofish.com", "path": "/"},
        ]
    }
    with open(state_path, "w") as f:
        json.dump(state, f)

    monkeypatch.setattr("backend.browser_engine.SESSION_STATE_PATH", state_path)
    monkeypatch.setattr("backend.browser_engine._verified_connected", False)
    from backend.browser_engine import get_session_status
    assert get_session_status() == "guest"


def test_session_state_empty_values_stay_guest(tmp_path, monkeypatch):
    state_path = str(tmp_path / "session_state.json")
    state = {
        "cookies": [
            {"name": "cookie2", "value": "", "domain": ".goofish.com", "path": "/"},
            {"name": "unb", "value": "0", "domain": ".goofish.com", "path": "/"},
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
