# -------------------------------------------------------------------------
# CAR + DMA + Zone Status Scanner (All Tickers, Console Print, No Filters)
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# Logic reference: README.md (same folder)
# -------------------------------------------------------------------------
# Run command:
# uv run src/dsm/screeners/stock-status.py

import re
import yfinance as yf
import pandas as pd
import warnings
import logging
from datetime import datetime

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

TICKERS = [
    "NFXL", "ORCX", "BSX", "IBIT", "BULL", "MSFU",
    "METU", "ADP", "PG", "SOFI", "WMT", "SLV", "GLD",
]

# TICKERS = [
#     "MSFT", "META", "NVDA", "AVGO", "AAPL", "GOOGL", "AMZN",
#     "JPM", "BSX", "INFY", "IBIT", "BULL",
# ]

# ---------------------------------------------------------------------
# ANSI colors used for console output (supported by most modern
# terminals, including Windows Terminal / VS Code integrated terminal).
# ---------------------------------------------------------------------
RESET        = "\033[0m"
RED          = "\033[91m"
GREEN        = "\033[92m"
YELLOW       = "\033[93m"
ORANGE       = "\033[38;5;208m"
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
    if shift_pct >= 0.1:
        return GREEN
    if shift_pct >= -10:
        return YELLOW
    return RED


def get_market_cap_billions(ticker):
    """
    Fetch market cap (stocks) / AUM (ETFs) and return it in $ Billions,
    or None if unavailable.

    yfinance's fast_info exposes fields under different names depending on
    version (e.g. attribute `market_cap` vs dict key `marketCap`), so both
    styles are tried. ETFs frequently don't carry a market cap at all —
    their size is reported as "total assets" (AUM), which lives in the
    slower `.info` dict as `totalAssets`.
    """
    try:
        t = yf.Ticker(ticker)

        try:
            fast = t.fast_info
        except Exception:
            fast = None

        def fast_get(*keys):
            """Try several key names, both dict-style and attribute-style."""
            if fast is None:
                return None
            for k in keys:
                try:
                    v = fast[k]
                    if v is not None:
                        return v
                except Exception:
                    pass
                v = getattr(fast, k, None)
                if v is not None:
                    return v
            return None

        # 1) Direct market cap (works for most regular stocks)
        mcap = fast_get("market_cap", "marketCap")
        if mcap:
            return round(mcap / 1e9, 2)

        # 2) price * shares outstanding (fallback, when available)
        price = fast_get("last_price", "lastPrice")
        shares = fast_get("shares_outstanding", "sharesOutstanding", "shares")
        if price is not None and shares is not None:
            computed = price * shares
            if computed:
                return round(computed / 1e9, 2)

        # 3) Slower .info dict: marketCap for stocks, totalAssets (AUM) for ETFs
        info = t.info
        mcap = info.get("marketCap")
        if mcap:
            return round(mcap / 1e9, 2)

        aum = info.get("totalAssets")
        if aum:
            return round(aum / 1e9, 2)

    except Exception:
        pass
    return None


# ---------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------
def scan_all(ticker_list):
    results = []
    print(f"Processing {len(ticker_list)} stocks...\n")

    for ticker in ticker_list:
        row = {
            "Stock": ticker,
            "Market Cap ($B)": "-",
            "CMP": "-",
            "DMA BO": "",
            "CAR BO": "",
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

        try:
            data = yf.download(ticker, period="2y", interval="1d", progress=False)

            if data.empty:
                print(f"  [WARN] {ticker}: no data returned")
                results.append(row)
                continue

            close_prices = data["Close"].squeeze()
            cmp = float(close_prices.iloc[-1])
            row["CMP"] = f"{round(cmp, 2)}"

            # Market cap (best-effort; leave blank if unavailable)
            mcap_b = get_market_cap_billions(ticker)
            if mcap_b is not None:
                row["Market Cap ($B)"] = f"{mcap_b}"

            # DMAs
            dma_30  = safe_dma(close_prices, 30)
            dma_50  = safe_dma(close_prices, 50)
            dma_100 = safe_dma(close_prices, 100)
            dma_200 = safe_dma(close_prices, 200)

            for label, dma_val in (("30 DMA", dma_30), ("50 DMA", dma_50),
                                    ("100 DMA", dma_100), ("200 DMA", dma_200)):
                if dma_val is not None:
                    value_str = f"{round(dma_val, 2)}"
                    row[label] = colorize(value_str, GREEN) if cmp > dma_val else value_str

            # Shift % from 200 DMA (always show the sign, so + and - line up)
            shift_pct = ((cmp - dma_200) / dma_200) * 100 if dma_200 else None
            if shift_pct is not None:
                row["Shift %"] = colorize(f"{shift_pct:+06.2f}", shift_color(shift_pct))

            # Zone (based on DMA stack + CMP only)
            zone = get_zone(cmp, dma_50, dma_100, dma_200)
            row["Zone"] = colorize(zone, ZONE_COLOR.get(zone, ""))

            # 52-week high/low, CAR score, days since 52W low
            # (all require a full year of history; left blank otherwise)
            car_score = None
            if len(data) >= 252:
                last_1y = data.tail(252)
                high_series = last_1y["High"].squeeze()
                low_series = last_1y["Low"].squeeze()

                high_date = high_series.idxmax()
                low_date = low_series.idxmin()

                row["52W High"] = pd.Timestamp(high_date).strftime("%b-%d-%Y")
                row["52W Low"] = pd.Timestamp(low_date).strftime("%b-%d-%Y")

                car_score = compute_car(close_prices, high_date)
                row["CAR"] = colorize(f"{car_score}", car_color(car_score))

                # Days since 52W low: positive if the low occurred after the
                # 52W high, negative otherwise. Shown in green when positive.
                days_since_low = (datetime.now().date() - pd.Timestamp(low_date).date()).days
                if pd.Timestamp(low_date) < pd.Timestamp(high_date):
                    days_since_low = -days_since_low

                dsl_str = f"{days_since_low:+d}"
                row["Days Since 52W Low"] = colorize(dsl_str, GREEN) if days_since_low > 0 else dsl_str

            # DMA Alignment breakout: ENTERING BULLISH zone AND car score >= 1
            if car_score is not None and zone == "ENTERING BULLISH" and car_score >= 1:
                row["DMA BO"] = GREEN_CHECK

            # CAR breakout: CMP > 50/100/200 DMA, CMP within 0.1%-10% of
            # 200 DMA, and car score >= 7
            if (car_score is not None and dma_50 is not None and dma_100 is not None
                    and dma_200 is not None and shift_pct is not None
                    and cmp > dma_50 and cmp > dma_100 and cmp > dma_200
                    and 0.1 <= shift_pct <= 10 and car_score >= 7):
                row["CAR BO"] = GREEN_CHECK

        except Exception as e:
            print(f"  [ERROR] {ticker}: {e}")

        results.append(row)

    return results


# ---------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------
def print_results(results):
    if not results:
        print("No results to display.")
        return

    today_str = datetime.now().strftime("%b-%d-%Y")

    df = pd.DataFrame(results).fillna("").sort_values(by="Stock")

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

    col_widths = {}
    for col in display_cols:
        value_width = max([visible_len(str(v)) for v in df[col]], default=0)
        if col in split_headers:
            header_width = max(len(p) for p in split_headers[col])
        else:
            header_width = len(col)
        col_widths[col] = max(header_width, value_width)

    sep = "+-" + "-+-".join("-" * col_widths[c] for c in display_cols) + "-+"

    header_line1 = "| " + " | ".join(
        split_headers[c][0].ljust(col_widths[c]) if c in split_headers else "".ljust(col_widths[c])
        for c in display_cols
    ) + " |"
    header_line2 = "| " + " | ".join(
        split_headers[c][1].ljust(col_widths[c]) if c in split_headers else c.ljust(col_widths[c])
        for c in display_cols
    ) + " |"

    print(f"Date: {today_str}\n")
    print(sep)
    print(header_line1)
    print(header_line2)
    print(sep)

    for _, row in df.iterrows():
        cells = [vjust(str(row[col]), col_widths[col]) for col in display_cols]
        print("| " + " | ".join(cells) + " |")

    print(sep)
    print(f"\nTotal: {len(results)} stocks\n")


if __name__ == "__main__":
    results = scan_all(TICKERS)
    print()
    print_results(results)
