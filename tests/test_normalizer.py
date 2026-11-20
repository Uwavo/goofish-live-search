from backend.normalizer import (
    detect_status,
    filter_by_price,
    normalize_image_url,
    normalize_listing,
    parse_price,
)


def test_normalize_image_url_strips_size():
    assert normalize_image_url("https://img.goofish.com/abc_200x200.jpg") == "https://img.goofish.com/abc.jpg"
    assert normalize_image_url("https://img.goofish.com/abc_100x100q90.jpg") == "https://img.goofish.com/abc.jpg"


def test_normalize_image_url_adds_https():
    assert normalize_image_url("//img.goofish.com/abc.jpg") == "https://img.goofish.com/abc.jpg"


def test_normalize_image_url_no_change():
    assert normalize_image_url("https://img.goofish.com/abc.jpg") == "https://img.goofish.com/abc.jpg"


def test_normalize_image_url_empty():
    assert normalize_image_url("") == ""


def test_parse_price_float():
    assert parse_price(99.5) == 99.5


def test_parse_price_string():
    assert parse_price("¥1,234.56") == 1234.56


def test_parse_price_none():
    assert parse_price(None) is None


def test_parse_price_invalid():
    assert parse_price("free") is None


def test_detect_status_sold():
    assert detect_status("sold") == "sold"
    assert detect_status("已卖出") == "sold"
    assert detect_status("下架") == "sold"


def test_detect_status_on_sale():
    assert detect_status("on_sale") == "on_sale"
    assert detect_status("active") == "on_sale"


def test_detect_status_none():
    assert detect_status(None) == "unknown"


def test_normalize_listing():
    raw = {
        "itemId": "123",
        "title": "Test Item",
        "price": 50.0,
        "images": [{"url": "//img.goofish.com/a_200x200.jpg"}],
        "sellerNick": "seller1",
        "area": "Beijing",
        "status": "on_sale",
        "desc": "A test item",
    }
    result = normalize_listing(raw)
    assert result["id"] == "123"
    assert result["title"] == "Test Item"
    assert result["price"] == 50.0
    assert result["images"] == ["https://img.goofish.com/a.jpg"]
    assert result["seller"] == "seller1"
    assert result["url"] == "https://www.goofish.com/item/123"


def test_filter_by_price():
    items = [
        {"price": 10.0}, {"price": 50.0}, {"price": 100.0}, {"price": None}
    ]
    assert len(filter_by_price(items, 20, 80)) == 1
    assert filter_by_price(items, 20, 80)[0]["price"] == 50.0
    assert len(filter_by_price(items, None, None)) == 3
