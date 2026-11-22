from backend.discovery import _extract_ids, _extract_price, extract_item_id_from_url


def test_extract_ids_from_html():
    html = '''
    <a href="https://www.goofish.com/item/1234567890123">Item</a>
    <a href="https://goofish.com/item/9876543210987">Item2</a>
    <a href="https://example.com/other">Not goofish</a>
    '''
    ids = _extract_ids(html)
    assert "1234567890123" in ids
    assert "9876543210987" in ids
    assert len(ids) == 2


def test_extract_ids_query_param():
    html = '<a href="https://goofish.com/item?id=1234567890123&categoryId=0">Item</a>'
    ids = _extract_ids(html)
    assert "1234567890123" in ids


def test_extract_ids_dedupes():
    html = '''
    <a href="https://goofish.com/item/1234567890123">A</a>
    <a href="https://goofish.com/item?id=1234567890123">B</a>
    '''
    ids = _extract_ids(html)
    assert len(ids) == 1


def test_extract_item_id_from_url():
    assert extract_item_id_from_url("https://www.goofish.com/item/1234567890123") == "1234567890123"
    assert extract_item_id_from_url("https://www.goofish.com/item?id=810502212426&categoryId=0") == "810502212426"
    assert extract_item_id_from_url("https://example.com") is None


def test_extract_ids_no_match():
    assert _extract_ids("<html><body>no items</body></html>") == []


# Price extraction tests

def test_price_yen_symbol():
    assert _extract_price("¥1200") == 1200.0
    assert _extract_price("￥1,200.00") == 1200.0
    assert _extract_price("价格 ¥ 999") == 999.0


def test_price_yuan_suffix():
    assert _extract_price("售价1200元") == 1200.0
    assert _extract_price("只要888元包邮") == 888.0


def test_price_chinese_prefix():
    assert _extract_price("售价1200") == 1200.0
    assert _extract_price("出1200") == 1200.0
    assert _extract_price("标价7200") == 7200.0
    assert _extract_price("到手价3300") == 3300.0


def test_price_with_commas():
    assert _extract_price("¥12,500") == 12500.0
    assert _extract_price("售价1,200.50") == 1200.5


def test_price_no_match():
    assert _extract_price("no price here") is None
    assert _extract_price("") is None
