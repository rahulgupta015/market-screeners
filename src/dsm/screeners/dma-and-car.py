# -------------------------------------------------------------------------
# CAR + DMA + Zone Status Scanner (All Tickers, Console Print, No Filters)
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# Logic reference: README.md (same folder)
# -------------------------------------------------------------------------
# Run command:
# uv run src/dsm/screeners/dma-and-car.py
# uv run src/dsm/screeners/dma-and-car.py --test   (first 10 symbols from MARKET_CAP_BY_SYMBOL)
# uv run src/dsm/screeners/dma-and-car.py --my     (the scanner's MY_TICKERS)

import re
import sys
import time
import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import warnings
import logging
from dataclasses import dataclass
from datetime import datetime

from dsm.screeners.stocks_us_50b_1m_options import STOCKS_BY_SYMBOL
from dsm.screeners.etfs_us_100m_1m_options import ETFS_BY_SYMBOL

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

# Combined lookup so a ticker can be resolved regardless of whether it's a
# stock or an ETF.
MARKET_CAP_BY_SYMBOL = {**STOCKS_BY_SYMBOL, **ETFS_BY_SYMBOL}

# Small fixed sample of symbols the user cares about, for --my runs.
MY_TICKERS = [
    "NFXL", "ORCX", "IBIT", "BULL", "BSX",
]

# ---------------------------------------------------------------------
# ANSI colors used for console output (supported by most modern
# terminals, including Windows Terminal / VS Code integrated terminal).
# ---------------------------------------------------------------------
RESET        = "\033[0m"
RED          = "\033[38;5;196m"  # neon red
GREEN        = "\033[92m"
YELLOW       = "\033[93m"
ORANGE       = "\033[38;5;214m"  # neon/amber orange - kept hue-separated from RED
PURPLE       = "\033[38;5;135m"

GREEN_CHECK = f"{GREEN}\u2714{RESET}"  # ✔ (DMA BO / CAR BO)

ANSI_RE = re.compile(r'\033\[[0-9;]*m')


def visible_len(s):
    """Length of a string ignoring ANSI color escape codes."""
    return len(ANSI_RE.sub('', s))


def vjust(s, width):
    """Left-justify a (possibly ANSI-colored) string to a visible width."""
    pad = width - visible_len(s)
    return s + (" " * pad if pad > 0 else "")


def colorize(value_str, color):
    """Wrap a value string in a color, leaving blanks/dashes uncolored."""
    if not value_str or value_str == "-":
        return value_str
    return f"{color}{value_str}{RESET}"


# ---------------------------------------------------------------------
# Calculation helpers
# ---------------------------------------------------------------------
@dataclass
class Ticker:
    """Raw computed data for one ticker, before display formatting."""

    symbol: str
    market_cap_b: float | None = None
    cmp: float | None = None
    dma_bo: bool = False
    car_bo: bool = False
    ema_8: float | None = None
    rsi: float | None = None
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

    _FIELDS = {
        "Stock": "symbol",
        "Market Cap ($B)": "market_cap_b",
        "CMP": "cmp",
        "DMA BO": "dma_bo",
        "CAR BO": "car_bo",
        "EMA 8": "ema_8",
        "RSI": "rsi",
        "30 DMA": "dma_30",
        "50 DMA": "dma_50",
        "100 DMA": "dma_100",
        "200 DMA": "dma_200",
        "Shift %": "shift_pct",
        "CAR": "car",
        "Zone": "zone",
        "52W High": "high_date",
        "52W Low": "low_date",
        "52W High Price": "high_price",
        "52W Low Price": "low_price",
        "Days Since 52W Low": "days_since_low",
        "Error": "error",
    }

    def __getitem__(self, key):
        return getattr(self, self._FIELDS[key])

    def __setitem__(self, key, value):
        setattr(self, self._FIELDS[key], value)


def compute_car(close_prices, high_date):
    """
    Calculate and return the CAR score.

    Starting from the 52-week-high date, take the expanding mean of the
    closing prices, then find the largest N (10 down to 1) for which the
    last N expanding-mean values are monotonically increasing.
    Returns 0 if it cannot be calculated or none qualify.
    """
    car_data = close_prices.loc[high_date:]
    if len(car_data) < 2:
        return 0
    car_values = car_data.expanding().mean()
    for n in range(10, 0, -1):
        if len(car_values) >= n and car_values.tail(n).is_monotonic_increasing:
            return n
    return 0


def get_zone(cmp, dma50, dma100, dma200):
    """
    Return the Zone label given CMP and the 50/100/200 DMAs.

      B++ : CMP > 50 > 100 > 200 DMA AND CMP > 1.10 * 200 DMA
      B+  : CMP > 50 > 100 > 200 DMA AND 200 DMA < CMP <= 1.10 * 200 DMA
      B-  : CMP < 50 < 100 < 200 DMA AND 0.90 * 200 DMA <= CMP < 200 DMA
      B-- : CMP < 50 < 100 < 200 DMA AND CMP < 0.90 * 200 DMA
      U   : anything else (incl. missing DMAs / not stacked cleanly)
    """
    if dma50 is None or dma100 is None or dma200 is None:
        return "U"

    bullish_stack = cmp > dma50 > dma100 > dma200
    bearish_stack = cmp < dma50 < dma100 < dma200

    if bullish_stack and cmp > 1.10 * dma200:
        return "B++" # Bullish
    if bullish_stack and dma200 < cmp <= 1.10 * dma200:
        return "B+" # Entering Bullish
    if bearish_stack and cmp < 0.90 * dma200:
        return "B--" # Bearish
    if bearish_stack and 0.90 * dma200 <= cmp < dma200:
        return "B-" # Entering Bearish
    return "U" # Unconfirmed


def get_market_cap_billions(ticker):
    """
    Look up market cap (stocks) / AUM (ETFs) in $ Billions from the local
    ticker data files beside this scanner, or None if the ticker isn't in
    either dataset.
    """
    entry = MARKET_CAP_BY_SYMBOL.get(ticker)
    return entry["market_cap_b"] if entry else None


def compute_ticker(ticker):
    """
    Fetch price history for `ticker` and compute every raw indicator
    (CMP, DMAs, Shift %, Zone, CAR score, 52W high/low, breakout flags).

    Pure data step: no ANSI colors, checkmarks, or display formatting.
    Returns a Ticker object; ``error`` is None on success, or
    ("WARN"|"ERROR", msg) if data was unavailable or something raised.
    """
    raw = Ticker(symbol=ticker)

    try:
        data = yf.download(ticker, period="2y", interval="1d", progress=False)

        if data.empty:
            raw["Error"] = ("WARN", "no data returned")
            return raw

        close_prices = data["Close"].squeeze()
        cmp = float(close_prices.iloc[-1])
        raw["CMP"] = cmp

        rsi = ta.rsi(close_prices, length=14)
        if rsi is not None and pd.notna(rsi.iloc[-1]):
            raw["RSI"] = float(rsi.iloc[-1])
        ema_8 = ta.ema(close_prices, length=8)
        if ema_8 is not None and pd.notna(ema_8.iloc[-1]):
            raw["EMA 8"] = float(ema_8.iloc[-1])

        raw["Market Cap ($B)"] = get_market_cap_billions(ticker)

        dma_30  = float(ta.sma(close_prices, length=30).iloc[-1]) if len(close_prices) >= 30 else None
        dma_50  = float(ta.sma(close_prices, length=50).iloc[-1]) if len(close_prices) >= 50 else None
        dma_100 = float(ta.sma(close_prices, length=100).iloc[-1]) if len(close_prices) >= 100 else None
        dma_200 = float(ta.sma(close_prices, length=200).iloc[-1]) if len(close_prices) >= 200 else None
        raw["30 DMA"], raw["50 DMA"], raw["100 DMA"], raw["200 DMA"] = dma_30, dma_50, dma_100, dma_200

        # Shift % from 200 DMA
        shift_pct = ((cmp - dma_200) / dma_200) * 100 if dma_200 else None
        raw["Shift %"] = shift_pct

        # Zone (based on DMA stack + CMP only)
        zone = get_zone(cmp, dma_50, dma_100, dma_200)
        raw["Zone"] = zone

        # DMA Alignment breakout: Zone is B+
        raw["DMA BO"] = (zone == "B+")

        # 52-week high/low, CAR score, days since 52W low
        # (all require a full year of history; left as None otherwise)
        car_score = None
        if len(data) >= 252:
            last_1y = data.tail(252)
            high_series = last_1y["High"].squeeze()
            low_series = last_1y["Low"].squeeze()

            # Use pandas-ta for the 52-week extrema and their positions in
            # the trailing 252-session window.
            high_position = int(ta.maxindex(high_series, length=252).iloc[-1])
            low_position = int(ta.minindex(low_series, length=252).iloc[-1])
            high_date = high_series.index[high_position]
            low_date = low_series.index[low_position]
            raw["52W High Price"] = float(ta.rolling_max(high_series, length=252).iloc[-1])
            raw["52W Low Price"] = float(ta.rolling_min(low_series, length=252).iloc[-1])

            raw["52W High"] = pd.Timestamp(high_date)
            raw["52W Low"] = pd.Timestamp(low_date)

            car_score = compute_car(close_prices, high_date)
            raw["CAR"] = car_score

            # Days since 52W low: positive if the low occurred after the
            # 52W high, negative otherwise.
            days_since_low = (datetime.now().date() - pd.Timestamp(low_date).date()).days
            if pd.Timestamp(low_date) < pd.Timestamp(high_date):
                days_since_low = -days_since_low
            raw["Days Since 52W Low"] = days_since_low

        # CAR breakout: CMP > 50/100/200 DMA, CMP within 0.1%-10% of
        # 200 DMA, and car score >= 7
        if (car_score is not None and dma_50 is not None and dma_100 is not None
                and dma_200 is not None and shift_pct is not None
                and cmp > dma_50 and cmp > dma_100 and cmp > dma_200
                and 0.1 <= shift_pct <= 10 and car_score >= 5):
            raw["CAR BO"] = True

    except Exception as e:
        raw["Error"] = ("ERROR", str(e))

    return raw


# ---------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------
def scan_all(ticker_list):
    """Return raw computed data for every ticker, without display logic."""
    return [compute_ticker(ticker) for ticker in ticker_list]


def display_tickers(tickers):
    """Apply display logic to raw ticker data and print the final tables."""
    print(f"Processing {len(tickers)} symbols...\n")
    for ticker in tickers:
        if ticker["Error"]:
            level, msg = ticker["Error"]
            print(f"  [{level}] {ticker['Stock']}: {msg}")
    print_results(tickers)


# ---------------------------------------------------------------------
# Formatting (kept separate from the calculation above)
# ---------------------------------------------------------------------
ZONE_COLOR = {
    "B++": PURPLE,
    "B+":  GREEN,
    "U":   YELLOW,
    "B-":  ORANGE,
    "B--": RED,
}


def car_color(score):
    if score <= 1:
        return RED
    if score <= 3:
        return ORANGE
    if score <= 5:
        return YELLOW
    if score <= 9:
        return GREEN
    return PURPLE


def shift_color(shift_pct):
    if shift_pct > 10:
        return PURPLE
    if shift_pct >= 0.01:
        return GREEN
    if shift_pct >= -10:
        return ORANGE
    return RED


def format_row(raw):
    """
    Turn one raw ticker record (from compute_ticker) into a
    display-ready row: strings, "-" for missing values, ANSI colors,
    checkmarks, formatted dates. Pure formatting - no calculation
    happens here.
    """
    row = {
        "Stock": raw["Stock"],
        "Market Cap ($B)": "-",
        "CMP": "-",
        "DMA BO": GREEN_CHECK if raw["DMA BO"] else "",
        "CAR BO": GREEN_CHECK if raw["CAR BO"] else "",
        "EMA 8": "-",
        "RSI": "-",
        "30 DMA": "-",
        "50 DMA": "-",
        "100 DMA": "-",
        "200 DMA": "-",
        "Shift %": "-",
        "CAR": "-",
        "Zone": "-",
        "52W High": "-",
        "52W Low": "-",
        "52W High Price": "-",
        "52W Low Price": "-",
        "Days Since 52W Low": "-",
    }

    if raw["Market Cap ($B)"] is not None:
        row["Market Cap ($B)"] = f"{raw['Market Cap ($B)']}"

    cmp = raw["CMP"]
    if cmp is not None:
        row["CMP"] = f"{round(cmp, 2)}"

    if raw["EMA 8"] is not None:
        ema_8_str = f"{raw['EMA 8']:.2f}"
        row["EMA 8"] = colorize(ema_8_str, GREEN) if cmp is not None and cmp > raw["EMA 8"] else ema_8_str

    if raw["RSI"] is not None:
        row["RSI"] = f"{raw['RSI']:.2f}"

    for label in ("30 DMA", "50 DMA", "100 DMA", "200 DMA"):
        dma_val = raw[label]
        if dma_val is not None:
            value_str = f"{round(dma_val, 2)}"
            row[label] = colorize(value_str, GREEN) if cmp is not None and cmp > dma_val else value_str

    shift_pct = raw["Shift %"]
    if shift_pct is not None:
        row["Shift %"] = colorize(f"{shift_pct:+06.2f}", shift_color(shift_pct))

    if raw["Zone"] is not None:
        row["Zone"] = colorize(raw["Zone"], ZONE_COLOR.get(raw["Zone"], ""))

    if raw["CAR"] is not None:
        row["CAR"] = colorize(f"{raw['CAR']}", car_color(raw["CAR"]))

    if raw["52W High"] is not None:
        row["52W High"] = raw["52W High"].strftime("%m-%d-%y")
    if raw["52W Low"] is not None:
        row["52W Low"] = raw["52W Low"].strftime("%m-%d-%y")

    if raw["52W High Price"] is not None:
        row["52W High Price"] = f"{raw['52W High Price']:.2f}"
    if raw["52W Low Price"] is not None:
        row["52W Low Price"] = f"{raw['52W Low Price']:.2f}"

    days_since_low = raw["Days Since 52W Low"]
    if days_since_low is not None:
        dsl_str = f"{days_since_low:+d}"
        row["Days Since 52W Low"] = colorize(dsl_str, GREEN) if days_since_low > 0 else dsl_str

    return row


# ---------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------
def _table_lines(rows, display_cols, col_widths, split_headers):
    """Build the separator/header/data lines for one table section."""
    sep = "+-" + "-+-".join("-" * col_widths[c] for c in display_cols) + "-+"

    header_line1 = "| " + " | ".join(
        split_headers[c][0].ljust(col_widths[c]) if c in split_headers else "".ljust(col_widths[c])
        for c in display_cols
    ) + " |"
    header_line2 = "| " + " | ".join(
        split_headers[c][1].ljust(col_widths[c]) if c in split_headers else c.ljust(col_widths[c])
        for c in display_cols
    ) + " |"

    lines = [sep, header_line1, header_line2, sep]
    for row in rows:
        cells = [vjust(str(row[col]), col_widths[col]) for col in display_cols]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append(sep)
    return lines


def print_results(tickers):
    """Render a list of raw Ticker records as the final status tables."""
    if not tickers:
        print("No results to display.")
        return

    today_str = datetime.now().strftime("%b-%d-%Y")

    display_cols = [
        "Stock", "Market Cap ($B)", "CMP", "DMA BO", "CAR BO",
        "RSI", "EMA 8", "30 DMA", "50 DMA", "100 DMA", "200 DMA", "Shift %", "CAR", "Zone",
        "52W High", "52W Low", "Days Since 52W Low",
        "52W High Price", "52W Low Price",
    ]

    # Headers that are split across two lines so the column doesn't have
    # to be as wide as the full header text.
    split_headers = {
        "Market Cap ($B)": ("Cap", "($B)"),
        "DMA BO": ("DMA", "BO"),
        "CAR BO": ("CAR", "BO"),
        "EMA 8": ("EM8", ""),
        "RSI": ("RSI", ""),
        "30 DMA": ("30", "DMA"),
        "50 DMA": ("50", "DMA"),
        "100 DMA": ("100", "DMA"),
        "200 DMA": ("200", "DMA"),
        "Shift %": ("Shift%", "200 DMA"),
        "52W High": ("52WH", "Date"),
        "52W Low": ("52WL", "Date"),
        "Days Since 52W Low": ("52WL -", "52WH"),
        "52W High Price": ("52WH", "Price"),
        "52W Low Price": ("52WL", "Price"),
    }

    # Part 1: any breakout (DMA BO or CAR BO), sorted by 200 DMA Shift %
    # ascending. Part 2: everything else, sorted by symbol. Sorting is
    # done on the raw values, before any formatting is applied.
    breakout_raw = [r for r in tickers if r["DMA BO"] or r["CAR BO"]]
    other_raw = [r for r in tickers if not (r["DMA BO"] or r["CAR BO"])]

    breakout_raw.sort(key=lambda r: r["Shift %"] if r["Shift %"] is not None else float("inf"))
    other_raw.sort(key=lambda r: r["Stock"])

    breakout_rows = [format_row(r) for r in breakout_raw]
    other_rows = [format_row(r) for r in other_raw]
    all_rows = breakout_rows + other_rows

    # Shared column widths (computed across all results) so both tables
    # line up the same way.
    col_widths = {}
    for col in display_cols:
        value_width = max([visible_len(str(row[col])) for row in all_rows], default=0)
        if col in split_headers:
            header_width = max(len(p) for p in split_headers[col])
        else:
            header_width = len(col)
        col_widths[col] = max(header_width, value_width)

    print(f"Date: {today_str}\n")

    print(f"--- Breakouts (DMA BO / CAR BO) - sorted by 200 DMA Shift % asc ---\n")
    if breakout_rows:
        for line in _table_lines(breakout_rows, display_cols, col_widths, split_headers):
            print(line)
    else:
        print("(none)")

    print(f"\n--- All Other Symbols - sorted by Symbol ---\n")
    for line in _table_lines(other_rows, display_cols, col_widths, split_headers):
        print(line)

    print(f"\nTotal: {len(tickers)} symbols ({len(breakout_rows)} breakouts, {len(other_rows)} others)\n")


if __name__ == "__main__":
    start_time = time.perf_counter()

    use_test = "--test" in sys.argv
    use_my = "--my" in sys.argv

    if use_test:
        tickers = sorted(MARKET_CAP_BY_SYMBOL)[:10]
        print(f"(Running in TEST mode with {len(tickers)} tickers)\n")
    elif use_my:
        tickers = MY_TICKERS
        print(f"(Running in MY mode with {len(tickers)} tickers)\n")
    else:
        tickers = list(MARKET_CAP_BY_SYMBOL)

    results = scan_all(tickers)
    display_tickers(results)

    elapsed = time.perf_counter() - start_time
    print(f"Execution time: {elapsed:.2f}s")


# TODO for me:
# Fix ETFS list - TQQQ, SPY, NFXL, METU, MSFU, MUU, ORCX and any other
