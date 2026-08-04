from dataclasses import dataclass

import pandas as pd

from .ticker import Ticker


@dataclass
class Calc:
    """Raw calculated values for one ticker, before display formatting."""

    ticker: Ticker
    cmp: float | None = None
    rvol: float | None = None
    robv: float | None = None
    obv: float | None = None
    obv_sma_20: float | None = None
    dma_bo: bool = False
    car_bo: bool = False
    mac_bo: bool = False
    ema_8: float | None = None
    rsi: float | None = None
    kst: int | None = None  # +1 bullish, -1 bearish, None unavailable
    dma_30: float | None = None
    dma_50: float | None = None
    dma_100: float | None = None
    dma_200: float | None = None
    shift_pct: float | None = None
    car: int | None = None
    zone: str | None = None
    high_date: pd.Timestamp | None = None
    low_date: pd.Timestamp | None = None
    high_price: float | None = None
    low_price: float | None = None
    days_since_low: int | None = None
    error: tuple[str, str] | None = None
