# -------------------------------------------------------------------------
# CAR + DMA Status Scanner (All Tickers, Console Print, No Filters)
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# -------------------------------------------------------------------------
# Run command:
# uv run src/dsm/screeners/stock-status.py

import yfinance as yf
import pandas as pd
import warnings
import logging
from datetime import datetime

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

TICKERS = [
    "NFXL", "ORCX", "BSX", "IBIT", "BULL", "INFY", "MSFU", "METU",
]

# TICKERS = [
#     "MSFT", "META", "NVDA", "AVGO", "AAPL", "GOOGL", "AMZN",
#     "JPM", "BSX", "INFY", "IBIT", "BULL",
# ]

GREEN = "🟢"
RED  = "🔴"
YELLOW = "🟡"


def safe_dma(close_prices, window):
    """Return the rolling DMA value or None if not enough data."""
    if len(close_prices) >= window:
        return close_prices.rolling(window).mean().iloc[-1]
    return None


def compute_car_score(car_values):
    """
    CAR score: largest N (10 down to 1) for which the last N values
    are monotonically increasing. Returns 0 if none qualify.
    """
    for n in range(10, 0, -1):
        if len(car_values) >= n and car_values.tail(n).is_monotonic_increasing:
            return n
    return 0


def scan_all(ticker_list):
    results = []
    today_date = datetime.now().strftime("%b-%d-%Y")

    print(f"Processing {len(ticker_list)} stocks...\n")

    for ticker in ticker_list:
        try:
            data = yf.download(ticker, period="2y", interval="1d", progress=False)

            if data.empty:
                print(f"  [SKIP] {ticker}: no data returned")
                continue

            # squeeze() collapses MultiIndex columns to a plain Series
            close_prices = data["Close"].squeeze()

            cmp = close_prices.iloc[-1]

            # DMAs
            dma_30  = safe_dma(close_prices, 30)
            dma_50  = safe_dma(close_prices, 50)
            dma_100 = safe_dma(close_prices, 100)
            dma_200 = safe_dma(close_prices, 200)

            # Shift % from 200 DMA
            dist_200_dma = ((cmp - dma_200) / dma_200) * 100 if dma_200 else None

            # 52-week high/low dates
            if len(data) >= 252:
                last_1y = data.tail(252)
                high_series = last_1y["High"].squeeze()
                low_series = last_1y["Low"].squeeze()
                high_date = high_series.idxmax()
                low_date = low_series.idxmin()
                high_date_str = pd.Timestamp(high_date).strftime("%b-%d-%Y")
                low_date_str = pd.Timestamp(low_date).strftime("%b-%d-%Y")
                car_data = close_prices.loc[high_date:]
            else:
                high_date_str = "-"
                low_date_str = "-"
                car_data = pd.Series(dtype=float)

            # CAR score
            if len(car_data) < 2:
                car_score = 0
            else:
                car_values = car_data.expanding().mean()
                car_score = compute_car_score(car_values)

            # Dots: green if CMP > DMA, red otherwise
            dot_30  = GREEN if dma_30  is not None and cmp > dma_30  else RED
            dot_50  = GREEN if dma_50  is not None and cmp > dma_50  else RED
            dot_100 = GREEN if dma_100 is not None and cmp > dma_100 else RED
            dot_200 = GREEN if dma_200 is not None and cmp > dma_200 else RED
            dot_shift = GREEN if dist_200_dma is not None and 0.01 <= dist_200_dma <= 20 else RED
            # CAR dot: yellow if 1-9, green if 10, red otherwise
            if car_score == 10:
                dot_car = GREEN
            elif 1 <= car_score <= 9:
                dot_car = YELLOW
            else:
                dot_car = RED

            # 52W low after high? show green dot if low_date > high_date
            if high_date_str != "-" and low_date_str != "-":
                try:
                    low_after_high = low_date > high_date
                    dot_low_order = GREEN if low_after_high else RED
                except Exception:
                    dot_low_order = ""
            else:
                dot_low_order = ""

            results.append({
                "Date":          today_date,
                "Stock":         ticker,
                "CMP":           f"{round(float(cmp), 2)}",
                "30 DMA":        f"{round(float(dma_30),  2) if dma_30  is not None else '-'}",
                "30 DOT":        dot_30,
                "50 DMA":        f"{round(float(dma_50),  2) if dma_50  is not None else '-'}",
                "50 DOT":        dot_50,
                "100 DMA":       f"{round(float(dma_100), 2) if dma_100 is not None else '-'}",
                "100 DOT":       dot_100,
                "200 DMA":       f"{round(float(dma_200), 2) if dma_200 is not None else '-'}",
                "200 DOT":       dot_200,
                "Shift %":       f"{round(float(dist_200_dma), 2) if dist_200_dma is not None else '-'}",
                "Shift DOT":     dot_shift,
                "CAR Score":     f"{car_score}",
                "CAR DOT":       dot_car,
                "52W High Date": high_date_str,
                "52W Low Date":  low_date_str,
                "52W Low DOT":   dot_low_order,
            })

        except Exception as e:
            print(f"  [ERROR] {ticker}: {e}")
            # Still append a row with blanks so no stock is silently dropped
            results.append({
                "Date":          today_date,
                "Stock":         ticker,
                "CMP":           "-",
                "30 DMA":        "-",
                "30 DOT":        RED,
                "50 DMA":        "-",
                "50 DOT":        RED,
                "100 DMA":       "-",
                "100 DOT":       RED,
                "200 DMA":       "-",
                "200 DOT":       RED,
                "Shift %":       "-",
                "Shift DOT":     RED,
                "CAR Score":     "0",
                "CAR DOT":       RED,
                "52W High Date": "-",
                "52W Low Date":  "-",
                "52W Low DOT":   "",
            })

    return results


def print_results(results):
    if not results:
        print("No results to display.")
        return

    df = pd.DataFrame(results).fillna("").astype(str).sort_values(by='Stock')

    # Define display order and which columns have a trailing dot column
    display_cols = [
        "Date", "Stock", "CMP",
        "30 DMA", "50 DMA", "100 DMA", "200 DMA",
        "Shift %", "CAR Score", "52W High Date", "52W Low Date",
    ]
    dot_cols = {
        "30 DMA": "30 DOT",
        "50 DMA": "50 DOT",
        "100 DMA": "100 DOT",
        "200 DMA": "200 DOT",
        "Shift %": "Shift DOT",
        "CAR Score": "CAR DOT",
        "52W Low Date": "52W Low DOT",
    }

    # Compute column widths: if column has a dot column, leave 2 chars for ' <dot>'
    col_widths = {}
    for col in display_cols:
        base_max = df.get(col, "").map(len).max() if col in df.columns else len(col)
        if col in dot_cols:
            col_widths[col] = max(len(col), base_max + 2)
        else:
            col_widths[col] = max(len(col), base_max)

    # Build separators and header
    sep = "+-" + "-+-".join("-" * col_widths[c] for c in display_cols) + "-+"
    header = "| " + " | ".join(c.ljust(col_widths[c]) for c in display_cols) + " |"

    print(sep)
    print(header)
    print(sep)

    for _, row in df.iterrows():
        cells = []
        for col in display_cols:
            base = row.get(col, "")
            if col in dot_cols:
                dot = row.get(dot_cols[col], "")
                # Place dot right before the pipe (right aligned). Base left-justified.
                cell = base.ljust(col_widths[col] - 2) + (" " + dot)
            else:
                cell = base.ljust(col_widths[col])
            cells.append(cell)
        print("| " + " | ".join(cells) + " |")

    print(sep)
    print(f"\nTotal: {len(results)} stocks\n")


if __name__ == "__main__":
    results = scan_all(TICKERS)
    print()
    print_results(results)
