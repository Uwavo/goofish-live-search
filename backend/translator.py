import unicodedata
import httpx


def _is_chinese(text: str) -> bool:
    for ch in text:
        if "CJK" in unicodedata.name(ch, ""):
            return True
    return False


def translate_query(query: str) -> str:
    """Translate English query to Chinese. Keep Chinese text intact."""
    query = query.strip()
    if not query:
        return query
    if _is_chinese(query):
        return query

    # MyMemory free translation API
    try:
        resp = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": query, "langpair": "en|zh-CN"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            translated = data.get("responseData", {}).get("translatedText", "")
            if translated and _is_chinese(translated):
                return translated
    except Exception:
        pass

    # Google Translate fallback
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="en", target="zh-CN").translate(query)
        if translated and translated != query and _is_chinese(translated):
            return translated
    except Exception:
        pass

    return query
