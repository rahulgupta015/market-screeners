# -------------------------------------------------------------------------
# CAR + DMA Status Scanner (All Tickers, Console Print, No Filters)
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# -------------------------------------------------------------------------

import yfinance as yf
import pandas as pd
import warnings
import logging
from datetime import datetime

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

TICKERS = [
    "MSFT", "META", "NVDA", "AVGO", "AAPL", "GOOGL", "AMZN",
    "JPM", "BSX", "INFY", "IBIT", "BULL",
]

GREEN = "🟢"
RED  = "🔴"


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

            # 52-week high date
            if len(data) >= 252:
                last_1y = data.tail(252)
                high_series = last_1y["High"].squeeze()
                high_date = high_series.idxmax()          # plain Timestamp after squeeze
                high_date_str = pd.Timestamp(high_date).strftime("%b-%d-%Y")
                car_data = close_prices.loc[high_date:]
            else:
                high_date_str = "-"
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
            dot_car   = GREEN if car_score >= 7 else RED

            results.append({
                "Date":         today_date,
                "Stock":        ticker,
                "CMP":          round(float(cmp), 2),
                "30 DMA":       f"{round(float(dma_30),  2) if dma_30  is not None else '-'} {dot_30}",
                "50 DMA":       f"{round(float(dma_50),  2) if dma_50  is not None else '-'} {dot_50}",
                "100 DMA":      f"{round(float(dma_100), 2) if dma_100 is not None else '-'} {dot_100}",
                "200 DMA":      f"{round(float(dma_200), 2) if dma_200 is not None else '-'} {dot_200}",
                "Shift %":      f"{round(float(dist_200_dma), 2) if dist_200_dma is not None else '-'} {dot_shift}",
                "CAR Score":    f"{car_score} {dot_car}",
                "52W High Date": high_date_str,
            })

        except Exception as e:
            print(f"  [ERROR] {ticker}: {e}")
            # Still append a row with blanks so no stock is silently dropped
            results.append({
                "Date":         today_date,
                "Stock":        ticker,
                "CMP":          "-",
                "30 DMA":       f"- {RED}",
                "50 DMA":       f"- {RED}",
                "100 DMA":      f"- {RED}",
                "200 DMA":      f"- {RED}",
                "Shift %":      f"- {RED}",
                "CAR Score":    f"0 {RED}",
                "52W High Date": "-",
            })

    return results


def print_results(results):
    if not results:
        print("No results to display.")
        return

    df = pd.DataFrame(results)

    # FIX: convert NaN/floats safely to strings
    df_str = df.fillna("").astype(str)

    # Column widths accounting for emoji (they render as 2 chars wide in most terminals)
    col_widths = {}
    for col in df_str.columns:
        max_data = df_str[col].map(len).max()
        col_widths[col] = max(len(col), max_data)

    sep    = "+-" + "-+-".join("-" * col_widths[c] for c in df_str.columns) + "-+"
    header = "| " + " | ".join(c.ljust(col_widths[c]) for c in df_str.columns) + " |"

    print(sep)
    print(header)
    print(sep)
    for _, row in df_str.iterrows():
        print("| " + " | ".join(str(row[c]).ljust(col_widths[c]) for c in df_str.columns) + " |")
    print(sep)
    print(f"\nTotal: {len(results)} stocks\n")


if __name__ == "__main__":
    results = scan_all(TICKERS)
    print()
    print_results(results)
