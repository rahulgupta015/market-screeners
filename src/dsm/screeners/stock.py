# -------------------------------------------------------------------------
# CAR (Cumulative Average) + 30, 50, 100, 200 DMA Super Breakout Scanner
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# -------------------------------------------------------------------------
from operator import truediv

import yfinance as yf
import pandas as pd
import warnings
import logging
from datetime import datetime
from pathlib import Path
from dsm.config import get_ticker_category

# Suppress unnecessary Yahoo Finance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')


def scan_breakouts(ticker_list):
    """
    Runs the breakout scanner on a list of stock tickers.
    Returns a DataFrame of stocks that meet all breakout conditions.
    """
    results = []
    today_date = datetime.now().strftime("%b-%d-%Y")

    print(f"Scanning {len(ticker_list)} stocks... Please wait.\n")

    for ticker in ticker_list:
        try:
            # Download 2 years of daily data (at least 200 days for 200 DMA)
            data = yf.download(ticker, period="2y", interval="1d", progress=False)

            if data.empty or len(data) < 200:
                continue

            close_prices = data['Close'].squeeze()

            # Calculate DMAs
            dma_30 = close_prices.rolling(window=30).mean().iloc[-1]
            dma_50 = close_prices.rolling(window=50).mean().iloc[-1]
            dma_100 = close_prices.rolling(window=100).mean().iloc[-1]
            dma_200 = close_prices.rolling(window=200).mean().iloc[-1]

            # Current Market Price
            cmp = close_prices.iloc[-1]

            # Distance from 200 DMA (%)
            dist_200_dma = ((cmp - dma_200) / dma_200) * 100

            # Find 52-week high date (approx 252 trading days)
            last_1y_data = data.tail(252)
            high_series = last_1y_data['High'].squeeze()
            high_date = high_series.idxmax()
            high_date_str = pd.Timestamp(high_date).strftime("%b-%d-%Y")

            # CAR (Cumulative Average) since high date
            car_data = close_prices.loc[high_date:]

            if len(car_data) < 10:
                continue

            car_values = car_data.expanding().mean()
            last_10_car = car_values.tail(10)
            last_9_car = car_values.tail(9)
            last_8_car = car_values.tail(8)
            last_7_car = car_values.tail(7)

            # CAR Trend Ladder
            if last_10_car.is_monotonic_increasing:
                car_status = 10
            elif last_9_car.is_monotonic_increasing:
                car_status = 9
            elif last_8_car.is_monotonic_increasing:
                car_status = 8
            elif last_7_car.is_monotonic_increasing:
                car_status = 7
            else:
                car_status = 0

            # Display condition
            if (
                    cmp > dma_30 and
                    cmp > dma_50 and
                    cmp > dma_100 and
                    cmp > dma_200 and
                    0.01 <= dist_200_dma <= 20 and
                    car_status >= 7
            ):
                display = 1
            else:
                display = 0

            # Breakout Conditions
            if (
                    display == 1 and
                    car_status == 10
            ):
                action = 'Breakout'
            else:
                action = 'Avoid'

            # Store only candidates with display = 1
            if display == 1:
                category = get_ticker_category(ticker)
                results.append({
                    'Date': today_date,
                    'Stock': ticker,
                    'Category': category,
                    'CMP': round(cmp, 2),
                    'YHD': high_date_str,
                    '30 DMA': round(dma_30, 2),
                    '50 DMA': round(dma_50, 2),
                    '100 DMA': round(dma_100, 2),
                    '200 DMA': round(dma_200, 2),
                    'Action': action,
                    'CAR Score': car_status,
                    'Shift %': round(dist_200_dma, 2),
                })

        except Exception:
            pass

    # Convert results to DataFrame
    df_results = pd.DataFrame(results)

    return df_results


def export_to_excel(df, output_dir="data/outputs"):
    """Export results to timestamped Excel file"""
    try:
        now_str = datetime.now().strftime("%Y-%b-%d_%H-%M")
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        file_path = out_path / f"Breakout_{now_str}.xlsx"
        df.to_excel(file_path, index=False)
        return file_path
    except Exception as e:
        print(f"Failed to save Excel file: {e}")
        return None


def print_results(df):
    """Print results grouped by market cap category, sorted by CAR Score (desc) then Shift % (asc)."""
    if df.empty:
        print("No stock passed candidate conditions today.")
        return

    from dsm.config import CATEGORY_DISPLAY_NAMES

    # Group by category, maintaining the order
    category_order = ["OVER_200B", "BETWEEN_100B_200B", "BETWEEN_50B_100B", "BELOW_50B", "ETF_OVER_1B", "LEVERAGED", "OTHERS"]

    for category in category_order:
        category_df = df[df['Category'] == category].copy()

        if category_df.empty:
            continue

        # Sort by Action desc (Breakout first), CAR Score desc, Shift % asc
        category_df = category_df.sort_values(by=['Action', 'CAR Score', 'Shift %'], ascending=[False, False, True])

        # Print category header
        display_name = CATEGORY_DISPLAY_NAMES.get(category, category)
        print(f"\n{display_name}:")

        # Convert to strings for printing
        df_str = category_df.astype(str)

        # Compute column widths
        col_widths = {col: max(len(col), df_str[col].map(len).max()) for col in df_str.columns}

        # Build separator and header
        sep = "+-" + "-+-".join("-" * col_widths[col] for col in df_str.columns) + "-+"
        header = "| " + " | ".join(col.ljust(col_widths[col]) for col in df_str.columns) + " |"

        print(sep)
        print(header)
        print(sep)
        for _, row in df_str.iterrows():
            print("| " + " | ".join(str(row[col]).ljust(col_widths[col]) for col in df_str.columns) + " |")
        print(sep)
