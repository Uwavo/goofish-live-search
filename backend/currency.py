"""CNY to GBP currency conversion."""
from backend.config import CNY_TO_GBP_RATE


def cny_to_gbp(cny: float | None) -> float | None:
    if cny is None:
        return None
    return round(cny * CNY_TO_GBP_RATE, 2)


def format_cny(price: float | None) -> str:
    if price is None:
        return ""
    return f"¥{price:,.2f}"


def format_gbp(price: float | None) -> str:
    if price is None:
        return ""
    gbp = cny_to_gbp(price)
    return f"£{gbp:,.2f}" if gbp is not None else ""
