from backend.currency import cny_to_gbp, format_cny, format_gbp


def test_cny_to_gbp():
    assert cny_to_gbp(100) == 11.0


def test_cny_to_gbp_none():
    assert cny_to_gbp(None) is None


def test_cny_to_gbp_zero():
    assert cny_to_gbp(0) == 0.0


def test_format_cny():
    assert format_cny(1234.5) == "¥1,234.50"
    assert format_cny(None) == ""


def test_format_gbp():
    assert format_gbp(100) == "£11.00"
    assert format_gbp(None) == ""
