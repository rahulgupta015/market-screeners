# -------------------------------------------------------------------------
# CAR + DMA + Zone Status Scanner (All Tickers, Console Print, No Filters)
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# Logic reference: README.md (same folder)
# -------------------------------------------------------------------------
# Run command:
# uv run src/dsm/screeners/stock-status.py
# uv run src/dsm/screeners/stock-status.py --test

import re
import sys
import time
import yfinance as yf
import pandas as pd
import warnings
import logging
from datetime import datetime

from dsm.main import TEST_TICKERS
from dsm.stocks_us_50b_1m_options import STOCKS_BY_SYMBOL
from dsm.etfs_us_100m_1m_options import ETFS_BY_SYMBOL

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

# Combined lookup so a ticker can be resolved regardless of whether it's a
# stock or an ETF.
MARKET_CAP_BY_SYMBOL = {**STOCKS_BY_SYMBOL, **ETFS_BY_SYMBOL}

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
def safe_dma(close_prices, window):
    """Return the rolling DMA value or None if not enough data."""
    if len(close_prices) >= window:
        return float(close_prices.rolling(window).mean().iloc[-1])
    return None


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

      BULLISH          : CMP > 50 > 100 > 200 DMA AND CMP > 1.10 * 200 DMA
      ENTERING BULLISH  : CMP > 50 > 100 > 200 DMA AND 200 DMA < CMP <= 1.10 * 200 DMA
      ENTERING BEARISH  : CMP < 50 < 100 < 200 DMA AND 0.90 * 200 DMA <= CMP < 200 DMA
      BEARISH           : CMP < 50 < 100 < 200 DMA AND CMP < 0.90 * 200 DMA
      UNCONFIRMED       : anything else (incl. missing DMAs / not stacked cleanly)
    """
    if dma50 is None or dma100 is None or dma200 is None:
        return "UNCONFIRMED"

    bullish_stack = cmp > dma50 > dma100 > dma200
    bearish_stack = cmp < dma50 < dma100 < dma200

    if bullish_stack and cmp > 1.10 * dma200:
        return "BULLISH"
    if bullish_stack and dma200 < cmp <= 1.10 * dma200:
        return "ENTERING BULLISH"
    if bearish_stack and cmp < 0.90 * dma200:
        return "BEARISH"
    if bearish_stack and 0.90 * dma200 <= cmp < dma200:
        return "ENTERING BEARISH"
    return "UNCONFIRMED"


def get_market_cap_billions(ticker):
    """
    Look up market cap (stocks) / AUM (ETFs) in $ Billions from the local
    config files (src/dsm/stocks_us_50b_1m_options.py and
    etfs_us_100m_1m_options.py), or None if the ticker isn't in either.
    """
    entry = MARKET_CAP_BY_SYMBOL.get(ticker)
    return entry["market_cap_b"] if entry else None


def compute_indicators(ticker):
    """
    Fetch price history for `ticker` and compute every raw indicator
    (CMP, DMAs, Shift %, Zone, CAR score, 52W high/low, breakout flags).

    Pure data step: everything here is a plain number, date, string label,
    or bool - no ANSI colors, checkmarks, or display formatting. See
    format_row() for that.

    Returns a dict; "Error" is None on success, or ("WARN"|"ERROR", msg)
    if data was unavailable or something raised.
    """
    raw = {
        "Stock": ticker,
        "Market Cap ($B)": None,
        "CMP": None,
        "DMA BO": False,
        "CAR BO": False,
        "30 DMA": None,
        "50 DMA": None,
        "100 DMA": None,
        "200 DMA": None,
        "Shift %": None,
        "CAR": None,
        "Zone": None,
        "52W High": None,
        "52W Low": None,
        "Days Since 52W Low": None,
        "Error": None,
    }

    try:
        data = yf.download(ticker, period="2y", interval="1d", progress=False)

        if data.empty:
            raw["Error"] = ("WARN", "no data returned")
            return raw

        close_prices = data["Close"].squeeze()
        cmp = float(close_prices.iloc[-1])
        raw["CMP"] = cmp

        raw["Market Cap ($B)"] = get_market_cap_billions(ticker)

        dma_30  = safe_dma(close_prices, 30)
        dma_50  = safe_dma(close_prices, 50)
        dma_100 = safe_dma(close_prices, 100)
        dma_200 = safe_dma(close_prices, 200)
        raw["30 DMA"], raw["50 DMA"], raw["100 DMA"], raw["200 DMA"] = dma_30, dma_50, dma_100, dma_200

        # Shift % from 200 DMA
        shift_pct = ((cmp - dma_200) / dma_200) * 100 if dma_200 else None
        raw["Shift %"] = shift_pct

        # Zone (based on DMA stack + CMP only)
        zone = get_zone(cmp, dma_50, dma_100, dma_200)
        raw["Zone"] = zone

        # DMA Alignment breakout: Zone is ENTERING BULLISH
        raw["DMA BO"] = (zone == "ENTERING BULLISH")

        # 52-week high/low, CAR score, days since 52W low
        # (all require a full year of history; left as None otherwise)
        car_score = None
        if len(data) >= 252:
            last_1y = data.tail(252)
            high_series = last_1y["High"].squeeze()
            low_series = last_1y["Low"].squeeze()

            high_date = high_series.idxmax()
            low_date = low_series.idxmin()

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
                and 0.1 <= shift_pct <= 10 and car_score >= 7):
            raw["CAR BO"] = True

    except Exception as e:
        raw["Error"] = ("ERROR", str(e))

    return raw


# ---------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------
def scan_all(ticker_list):
    """Compute raw indicators for every ticker. Still just data - no
    formatting or coloring happens here either (see format_row)."""
    results = []
    print(f"Processing {len(ticker_list)} symbols...\n")

    for ticker in ticker_list:
        raw = compute_indicators(ticker)
        if raw["Error"]:
            level, msg = raw["Error"]
            print(f"  [{level}] {ticker}: {msg}")
        results.append(raw)

    return results


# ---------------------------------------------------------------------
# Formatting (kept separate from the calculation above)
# ---------------------------------------------------------------------
ZONE_COLOR = {
    "BULLISH":         PURPLE,
    "ENTERING BULLISH": GREEN,
    "UNCONFIRMED":      YELLOW,
    "ENTERING BEARISH": ORANGE,
    "BEARISH":          RED,
}


def car_color(score):
    if score <= 1:
        return RED
    if score <= 4:
        return ORANGE
    if score <= 7:
        return YELLOW
    return GREEN


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
    Turn one raw indicator row (from compute_indicators) into a
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
        "30 DMA": "-",
        "50 DMA": "-",
        "100 DMA": "-",
        "200 DMA": "-",
        "Shift %": "-",
        "CAR": "-",
        "Zone": "-",
        "52W High": "-",
        "52W Low": "-",
        "Days Since 52W Low": "-",
    }

    if raw["Market Cap ($B)"] is not None:
        row["Market Cap ($B)"] = f"{raw['Market Cap ($B)']}"

    cmp = raw["CMP"]
    if cmp is not None:
        row["CMP"] = f"{round(cmp, 2)}"

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
        row["52W High"] = raw["52W High"].strftime("%b-%d-%Y")
    if raw["52W Low"] is not None:
        row["52W Low"] = raw["52W Low"].strftime("%b-%d-%Y")

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


def print_results(raw_results):
    if not raw_results:
        print("No results to display.")
        return

    today_str = datetime.now().strftime("%b-%d-%Y")

    display_cols = [
        "Stock", "Market Cap ($B)", "CMP", "DMA BO", "CAR BO",
        "30 DMA", "50 DMA", "100 DMA", "200 DMA", "Shift %", "CAR", "Zone",
        "52W High", "52W Low", "Days Since 52W Low",
    ]

    # Headers that are split across two lines so the column doesn't have
    # to be as wide as the full header text.
    split_headers = {
        "Market Cap ($B)": ("Market Cap", "($B)"),
        "Days Since 52W Low": ("Days Since", "52W Low"),
    }

    # Part 1: any breakout (DMA BO or CAR BO), sorted by 200 DMA Shift %
    # ascending. Part 2: everything else, sorted by symbol. Sorting is
    # done on the raw values, before any formatting is applied.
    breakout_raw = [r for r in raw_results if r["DMA BO"] or r["CAR BO"]]
    other_raw = [r for r in raw_results if not (r["DMA BO"] or r["CAR BO"])]

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

    print(f"\nTotal: {len(raw_results)} symbols ({len(breakout_rows)} breakouts, {len(other_rows)} others)\n")


if __name__ == "__main__":
    start_time = time.perf_counter()

    use_test = "--test" in sys.argv
    tickers = TEST_TICKERS if use_test else list(MARKET_CAP_BY_SYMBOL)
    if use_test:
        print(f"(Running in TEST mode with {len(tickers)} tickers)\n")

    results = scan_all(tickers)
    print()
    print_results(results)

    elapsed = time.perf_counter() - start_time
    print(f"Execution time: {elapsed:.2f}s")


# TODO for ai:
# Rename the file stock-status.py appropriately and remove stock.py as thats old now and fix the project accordingly


# TODO for me:
# Fix ETFS list - TQQQ, SPY, NFXL, METU, MSFU, MUU, ORCX and any other