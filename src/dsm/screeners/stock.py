# -------------------------------------------------------------------------
# CAR (Cumulative Average) + 30, 50, 100, 200 DMA Super Breakout Scanner
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# -------------------------------------------------------------------------

import yfinance as yf
import pandas as pd
import warnings
import logging
from datetime import datetime
from pathlib import Path

# Suppress unnecessary Yahoo Finance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')


def scan_breakouts(ticker_list):
    """
    Runs the breakout scanner on a list of stock tickers.
    Returns a DataFrame of stocks that meet all breakout conditions.
    """
    results = []
    today_date = datetime.now().strftime("%d-%m-%Y")

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
            high_date_str = pd.Timestamp(high_date).strftime("%d-%m-%Y")

            # CAR (Cumulative Average) since high date
            car_data = close_prices.loc[high_date:]

            if len(car_data) < 10:
                continue

            car_values = car_data.expanding().mean()
            last_10_car = car_values.tail(10)

            # Trend Check — CAR must be rising for last 10 days
            if last_10_car.is_monotonic_increasing:
                car_status = 'Positive'
            else:
                car_status = 'Negative'

            # Breakout Conditions
            if (
                    cmp > dma_30 and
                    cmp > dma_50 and
                    cmp > dma_100 and
                    cmp > dma_200 and
                    dist_200_dma <= 20 and
                    car_status == 'Positive'
            ):
                action = 'Breakout'
            else:
                action = 'Avoid/Hold'

            # Store only breakout stocks
            if action == 'Breakout':
                results.append({
                    'Date': today_date,
                    'Stock': ticker,
                    'CMP': round(cmp, 2),
                    '30 DMA': round(dma_30, 2),
                    '50 DMA': round(dma_50, 2),
                    '100 DMA': round(dma_100, 2),
                    '200 DMA': round(dma_200, 2),
                    'Shift %': round(dist_200_dma, 2),
                    'YHD': high_date_str,
                    'CAR Status': car_status,
                    'Action': action
                })

        except Exception:
            pass

    # Convert results to DataFrame
    df_positive = pd.DataFrame(results)

    # Sort by distance from 200 DMA
    if not df_positive.empty:
        df_positive = df_positive.sort_values(by='Shift %', ascending=True)

    return df_positive


def export_to_excel(df, output_dir="data/outputs"):
    """Export results to timestamped Excel file"""
    try:
        now_str = datetime.now().strftime("%Y%m%d%H%M")
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        file_path = out_path / f"Breakout_{now_str}.xlsx"
        df.to_excel(file_path, index=False)
        return file_path
    except Exception as e:
        print(f"Failed to save Excel file: {e}")
        return None


def print_results(df):
    """Print results in formatted table"""
    if df.empty:
        print("No stock passed all breakout conditions today.")
        return

    df_str = df.copy().astype(str)

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
