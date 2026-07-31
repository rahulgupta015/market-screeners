from .etfs_us_100m_1m_options import ETFS_BY_SYMBOL
from .stocks_us_50b_1m_options import STOCKS_BY_SYMBOL
from .ticker import Ticker


def load_market_universe() -> dict[str, Ticker]:
    """Load stock and ETF metadata into immutable ticker records."""
    universe = {
        symbol: Ticker(symbol=symbol, market_cap_b=entry.get("market_cap_b"), asset_type="stock")
        for symbol, entry in STOCKS_BY_SYMBOL.items()
    }
    universe.update({
        symbol: Ticker(symbol=symbol, market_cap_b=entry.get("market_cap_b"), asset_type="etf")
        for symbol, entry in ETFS_BY_SYMBOL.items()
    })
    return universe
