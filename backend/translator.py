import functools
import unicodedata
import httpx


def _is_chinese(text: str) -> bool:
    for ch in text:
        if "一" <= ch <= "鿿":
            return True
    return False


@functools.lru_cache(maxsize=512)
def _translate_remote(query: str) -> str:
    """Cached remote translation. Returns the best Chinese translation or the original query."""
    try:
        resp = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": query, "langpair": "en|zh-CN"},
            timeout=3,
        )
        if resp.status_code == 200:
            data = resp.json()
            translated = data.get("responseData", {}).get("translatedText", "")
            if translated and _is_chinese(translated):
                return translated
    except Exception:
        pass

    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="en", target="zh-CN").translate(query)
        if translated and translated != query and _is_chinese(translated):
            return translated
    except Exception:
        pass

    return query


def translate_query(query: str) -> str:
    """Translate English query to Chinese. Keep Chinese text intact."""
    query = query.strip()
    if not query:
        return query
    if _is_chinese(query):
        return query
    return _translate_remote(query)
