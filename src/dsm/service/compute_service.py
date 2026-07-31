import logging
import warnings
from datetime import datetime

import pandas as pd
import pandas_ta_classic as ta
import yfinance as yf

from dsm.model.calc import Calc
from dsm.model.ticker import Ticker

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


def get_zone(cmp, dma50, dma100, dma200):
    """Return the compact zone code for the current price and DMAs."""
    if dma50 is None or dma100 is None or dma200 is None:
        return "U"

    bullish_stack = cmp > dma50 > dma100 > dma200
    bearish_stack = cmp < dma50 < dma100 < dma200

    if bullish_stack and cmp > 1.10 * dma200:
        return "B++"
    if bullish_stack and dma200 < cmp <= 1.10 * dma200:
        return "B+"
    if bearish_stack and cmp < 0.90 * dma200:
        return "B--"
    if bearish_stack and 0.90 * dma200 <= cmp < dma200:
        return "B-"
    return "U"


def _last_indicator(indicator):
    if indicator is not None and pd.notna(indicator.iloc[-1]):
        return float(indicator.iloc[-1])
    return None


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
        calc.dma_50 = _last_indicator(ta.sma(close_prices, length=50)) if len(close_prices) >= 50 else None
        calc.dma_100 = _last_indicator(ta.sma(close_prices, length=100)) if len(close_prices) >= 100 else None
        calc.dma_200 = _last_indicator(ta.sma(close_prices, length=200)) if len(close_prices) >= 200 else None
        calc.shift_pct = ((calc.cmp - calc.dma_200) / calc.dma_200) * 100 if calc.dma_200 else None
        calc.zone = get_zone(calc.cmp, calc.dma_50, calc.dma_100, calc.dma_200)

        car_score = None
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
            car_score = compute_car(close_prices, high_date)
            calc.car = car_score

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
