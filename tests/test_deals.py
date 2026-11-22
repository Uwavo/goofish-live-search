import os
import sqlite3
import tempfile

import pytest

from backend.deals import compute_deal_score


def test_deal_score_below_median():
    assert compute_deal_score(50, [100, 100, 100]) == 50


def test_deal_score_at_median():
    assert compute_deal_score(100, [100, 100, 100]) == 0


def test_deal_score_above_median():
    assert compute_deal_score(150, [100, 100, 100]) == 0


def test_deal_score_none_price():
    assert compute_deal_score(None, [100, 200]) is None


def test_deal_score_empty_prices():
    assert compute_deal_score(50, []) is None


def test_deal_score_single_price():
    assert compute_deal_score(50, [100]) is None


def test_deal_score_capped_at_100():
    assert compute_deal_score(0, [1000, 2000, 3000]) == 100


def test_deal_score_zero_median():
    assert compute_deal_score(0, [0, 0, 0]) is None


def test_saved_deals_roundtrip(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("backend.deals.SAVED_DEALS_DB", db_path)

    from backend.deals import get_saved_deals, get_saved_ids, remove_deal, save_deal

    item = {"id": "abc123", "title": "Test", "price": 99.0}
    save_deal(item)
    assert "abc123" in get_saved_ids()
    deals = get_saved_deals()
    assert len(deals) == 1
    assert deals[0]["title"] == "Test"

    remove_deal("abc123")
    assert "abc123" not in get_saved_ids()
    assert len(get_saved_deals()) == 0


def test_save_deal_upsert(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("backend.deals.SAVED_DEALS_DB", db_path)

    from backend.deals import get_saved_deals, save_deal

    save_deal({"id": "x1", "title": "V1", "price": 10})
    save_deal({"id": "x1", "title": "V2", "price": 20})
    deals = get_saved_deals()
    assert len(deals) == 1
    assert deals[0]["title"] == "V2"
