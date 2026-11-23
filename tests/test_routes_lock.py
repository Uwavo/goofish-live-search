"""Test that live search is locked behind verified Alipay sign-in."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_live_search_returns_401_when_not_verified():
    with patch("backend.routes.is_verified_connected", return_value=False):
        resp = client.get("/api/search/live", params={"q": "test"})
        assert resp.status_code == 401
        assert "sign in via alipay" in resp.json()["detail"].lower()


def test_live_search_allowed_when_verified():
    with patch("backend.routes.is_verified_connected", return_value=True), \
         patch("backend.routes.search_authenticated", return_value=[]), \
         patch("backend.routes.translate_query", return_value="test"):
        resp = client.get("/api/search/live", params={"q": "test"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
