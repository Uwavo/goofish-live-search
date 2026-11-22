from backend.translator import _is_chinese, translate_query


def test_is_chinese_true():
    assert _is_chinese("手机壳")


def test_is_chinese_false():
    assert not _is_chinese("phone case")


def test_is_chinese_mixed():
    assert _is_chinese("iPhone 手机壳")


def test_translate_chinese_passthrough():
    assert translate_query("手机壳") == "手机壳"


def test_translate_empty():
    assert translate_query("") == ""
    assert translate_query("  ") == ""
