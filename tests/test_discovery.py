from backend.discovery import _extract_ids, extract_item_id_from_url


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
