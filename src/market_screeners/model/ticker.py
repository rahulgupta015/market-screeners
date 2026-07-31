from dataclasses import dataclass


@dataclass(frozen=True)
class Ticker:
    """Immutable ticker metadata loaded from the stock or ETF universe."""

    symbol: str
    market_cap_b: float | None = None
    asset_type: str = "stock"
