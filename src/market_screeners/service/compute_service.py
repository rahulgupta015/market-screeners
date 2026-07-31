import logging
import warnings
from datetime import datetime

import pandas as pd
import pandas_ta_classic as ta
import yfinance as yf

from market_screeners.model.calc import Calc
from market_screeners.model.ticker import Ticker

logging.getLogger("yfinance").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore")


def compute_car(close_prices, high_date):
    """Return the CAR score from the high date to the latest close."""
    car_data = close_prices.loc[high_date:]
    if len(car_data) < 2:
        return 0

    car_values = car_data.expanding().mean()
    for length in range(10, 0, -1):
        if len(car_values) >= length and car_values.tail(length).is_monotonic_increasing:
            return length
    return 0


def get_zone(cmp, dma50, dma100, dma200, previous_dmas=None):
    """Return the zone code using DMA ordering, slopes, and crossings."""
    if (
        dma50 is None
        or dma100 is None
        or dma200 is None
        or previous_dmas is None
        or any(previous_dmas.get(length) is None for length in (50, 100, 200))
    ):
        return "U"

    slope_50 = dma50 - previous_dmas[50]
    slope_100 = dma100 - previous_dmas[100]
    slope_200 = dma200 - previous_dmas[200]
    all_rising = slope_50 > 0 and slope_100 > 0 and slope_200 > 0
    all_falling = slope_50 < 0 and slope_100 < 0 and slope_200 < 0

    bullish_stack = cmp > dma50 > dma100 > dma200
    bearish_stack = cmp < dma50 < dma100 < dma200
    bullish_cross = (
        previous_dmas[50] <= previous_dmas[100] and dma50 > dma100
    ) or (
        previous_dmas[50] <= previous_dmas[200] and dma50 > dma200
    )
    bearish_cross = (
        previous_dmas[50] >= previous_dmas[100] and dma50 < dma100
    ) or (
        previous_dmas[50] >= previous_dmas[200] and dma50 < dma200
    )

    if bullish_stack and all_rising:
        return "B++"
    if cmp > dma50 and cmp > dma100 and cmp > dma200 and bullish_cross:
        return "B+"
    if bearish_stack and all_falling:
        return "B--"
    if cmp < dma50 and cmp < dma100 and cmp < dma200 and bearish_cross:
        return "B-"
    return "U"


def _last_indicator(indicator):
    if indicator is not None and pd.notna(indicator.iloc[-1]):
        return float(indicator.iloc[-1])
    return None


def _last_two_indicator(indicator):
    if indicator is None or len(indicator) < 2:
        return None, None
    if pd.isna(indicator.iloc[-1]) or pd.isna(indicator.iloc[-2]):
        return None, None
    return float(indicator.iloc[-1]), float(indicator.iloc[-2])


def is_dma_breakout(calc: Calc) -> bool:
    """Return whether a calculation meets the independent DMA BO rule."""
    return (
        calc.cmp is not None
        and calc.dma_50 is not None
        and calc.dma_100 is not None
        and calc.dma_200 is not None
        and calc.shift_pct is not None
        and calc.cmp > calc.dma_50 > calc.dma_100 > calc.dma_200
        and 0 < calc.shift_pct < 10
    )


def is_car_breakout(calc: Calc) -> bool:
    """Return whether a calculation meets the independent CAR BO rule."""
    return (
        calc.cmp is not None
        and calc.dma_50 is not None
        and calc.dma_100 is not None
        and calc.dma_200 is not None
        and calc.shift_pct is not None
        and calc.car is not None
        and calc.cmp > calc.dma_50
        and calc.cmp > calc.dma_100
        and calc.cmp > calc.dma_200
        and 0 < calc.shift_pct < 10
        and calc.car >= 5
    )


def compute_ticker(ticker: Ticker) -> Calc:
    """Fetch market data and return one raw calculation record."""
    calc = Calc(ticker=ticker)

    try:
        data = yf.download(ticker.symbol, period="2y", interval="1d", progress=False)
        if data.empty:
            calc.error = ("WARN", "no data returned")
            return calc

        close_prices = data["Close"].squeeze()
        calc.cmp = float(close_prices.iloc[-1])
        calc.ema_8 = _last_indicator(ta.ema(close_prices, length=8))
        calc.rsi = _last_indicator(ta.rsi(close_prices, length=14))

        calc.dma_30 = _last_indicator(ta.sma(close_prices, length=30)) if len(close_prices) >= 30 else None
        dma_50, previous_dma_50 = _last_two_indicator(ta.sma(close_prices, length=50)) if len(close_prices) >= 50 else (None, None)
        dma_100, previous_dma_100 = _last_two_indicator(ta.sma(close_prices, length=100)) if len(close_prices) >= 100 else (None, None)
        dma_200, previous_dma_200 = _last_two_indicator(ta.sma(close_prices, length=200)) if len(close_prices) >= 200 else (None, None)
        calc.dma_50 = dma_50
        calc.dma_100 = dma_100
        calc.dma_200 = dma_200
        calc.shift_pct = ((calc.cmp - calc.dma_200) / calc.dma_200) * 100 if calc.dma_200 else None
        calc.zone = get_zone(
            calc.cmp,
            calc.dma_50,
            calc.dma_100,
            calc.dma_200,
            {50: previous_dma_50, 100: previous_dma_100, 200: previous_dma_200},
        )

        if len(data) >= 252:
            last_year = data.tail(252)
            high_series = last_year["High"].squeeze()
            low_series = last_year["Low"].squeeze()

            high_position = int(ta.maxindex(high_series, length=252).iloc[-1])
            low_position = int(ta.minindex(low_series, length=252).iloc[-1])
            high_date = high_series.index[high_position]
            low_date = low_series.index[low_position]

            calc.high_date = pd.Timestamp(high_date)
            calc.low_date = pd.Timestamp(low_date)
            calc.high_price = _last_indicator(ta.rolling_max(high_series, length=252))
            calc.low_price = _last_indicator(ta.rolling_min(low_series, length=252))
            calc.car = compute_car(close_prices, high_date)

            days_since_low = (datetime.now().date() - calc.low_date.date()).days
            if calc.low_date < calc.high_date:
                days_since_low = -days_since_low
            calc.days_since_low = days_since_low

        calc.dma_bo = is_dma_breakout(calc)
        calc.car_bo = is_car_breakout(calc)
    except Exception as exc:
        calc.error = ("ERROR", str(exc))

    return calc


def scan_all(tickers: list[Ticker]) -> list[Calc]:
    """Compute raw records for every ticker without display logic."""
    return [compute_ticker(ticker) for ticker in tickers]
