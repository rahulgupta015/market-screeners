# -------------------------------------------------------------------------
# CAR (Cumulative Average) + 30, 50, 100, 200 DMA Super Breakout Scanner
# Reference: https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html
# -------------------------------------------------------------------------

# Importing required libraries
import yfinance as yf    # Downloads historical stock data from Yahoo Finance
import pandas as pd      # Helps organize data in rows/columns like Excel
import warnings          # Used to hide unnecessary warnings
import logging           # Controls background log messages
from datetime import datetime  # Used to get today's date
from pathlib import Path

# Suppress unnecessary Yahoo Finance warnings
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore')

# -------------------------------------------------------------------------
# Main Scanner Logic
# -------------------------------------------------------------------------

def advanced_stock_scanner(ticker_list):
    """
    Runs the breakout scanner on a list of stock tickers.
    Returns a DataFrame of stocks that meet all breakout conditions.
    """

    results = []  # Stores stocks that pass breakout conditions
    today_date = datetime.now().strftime("%d-%m-%Y")

    print(f"Scanning {len(ticker_list)} stocks... Please wait.\n")

    # Loop through each stock
    for ticker in ticker_list:
        try:
            # 1. Download 2 years of daily data
            # (We need at least 200 days for 200 DMA)
            data = yf.download(ticker, period="2y", interval="1d", progress=False)

            # Skip stocks with insufficient data
            if data.empty or len(data) < 200:
                continue

            close_prices = data['Close'].squeeze()

            # 2. Calculate DMAs
            # Original DMAs preserved
            dma_30 = close_prices.rolling(window=30).mean().iloc[-1]
            dma_50 = close_prices.rolling(window=50).mean().iloc[-1]
            dma_200 = close_prices.rolling(window=200).mean().iloc[-1]

            # NEW: 100 DMA added
            dma_100 = close_prices.rolling(window=100).mean().iloc[-1]

            # Current Market Price
            cmp = close_prices.iloc[-1]

            # 3. Distance from 200 DMA (%)
            dist_200_dma = ((cmp - dma_200) / dma_200) * 100

            # 4. Find 52-week high date (approx 252 trading days)
            last_1y_data = data.tail(252)
            high_series = last_1y_data['High'].squeeze()
            high_date = high_series.idxmax()
            high_date_str = pd.Timestamp(high_date).strftime("%d-%m-%Y")

            # 5. CAR (Cumulative Average)
            car_data = close_prices.loc[high_date:]

            # Need at least 10 days after the high
            if len(car_data) < 10:
                continue

            car_values = car_data.expanding().mean()
            last_10_car = car_values.tail(10)

            # 6. Trend Check — CAR must be rising for last 10 days
            if last_10_car.is_monotonic_increasing:
                car_status = 'Positive'
            else:
                car_status = 'Negative'

            # 7. Breakout Conditions
            # Original conditions preserved, NEW: 100 DMA added
            if (
                    cmp > dma_30 and
                    cmp > dma_50 and
                    cmp > dma_100 and           # NEW condition
                    cmp > dma_200 and
                    dist_200_dma <= 20 and      # CMP within 20% of 200 DMA
                    car_status == 'Positive'
            ):
                action = 'Breakout'
            else:
                action = 'Avoid/Hold'

            # 8. Store only breakout stocks
            if action == 'Breakout':
                results.append({
                    'Date': today_date,
                    'Stock': ticker,
                    'CMP': round(cmp, 2),
                    '30 DMA': round(dma_30, 2),
                    '50 DMA': round(dma_50, 2),
                    '100 DMA': round(dma_100, 2),   # NEW
                    '200 DMA': round(dma_200, 2),
                    'Shift %': round(dist_200_dma, 2),
                    'YHD': high_date_str,
                    'CAR Status': car_status,
                    'Action': action
                })

        except Exception:
            # Skip stock if any error occurs
            pass

    # Convert results to DataFrame
    df_positive = pd.DataFrame(results)

    # Sort by distance from 200 DMA
    if not df_positive.empty:
        df_positive = df_positive.sort_values(by='Shift %', ascending=True)

    return df_positive

# -------------------------------------------------------------------------
# Execution
# -------------------------------------------------------------------------

# Stock universe sourced from Tickers.java (daily-stock-monitor project)
# Organized by market cap category, largest first

SP500_NASDAQ_OVER_200B = [
    "AAPL", "ABBV", "ACN", "ADBE", "AMZN", "AVGO", "BAC", "BLK", "BRK-B", "CAT", "COST",
    "CRM", "CVX", "DIS", "GE", "GOOG", "GOOGL", "HD", "HON", "INTU", "JNJ", "JPM", "KO",
    "LIN", "LLY", "LMT", "MA", "MCD", "META", "MRK", "MSFT", "NFLX", "NKE", "NVDA", "ORCL",
    "PEP", "PFE", "PG", "PM", "QCOM", "SBUX", "TMO", "TSLA", "UNH", "V", "WMT", "XOM",
]

SP500_NASDAQ_BETWEEN_100B_200B = [
    "ADP", "AMGN", "AMD", "ANET", "APD", "AXP", "BA", "BKNG", "BMY", "CB", "CEG", "CHTR",
    "CMCSA", "CME", "COP", "CSCO", "CSX", "CTAS", "DUK", "EL", "FDX", "GILD", "GM", "GS",
    "HUM", "IBM", "ICE", "INTC", "ISRG", "LOW", "LRCX", "MAR", "MDLZ", "MDT", "MS", "MU",
    "NOW", "NXPI", "OXY", "PANW", "PCAR", "PLD", "REGN", "ROST", "SCHW", "SO", "SPG", "TGT",
    "TJX", "TMUS", "TXN", "UNP", "UPS", "USB", "VZ", "WFC", "ZTS",
]

SP500_NASDAQ_BETWEEN_50B_100B = [
    "ADI", "AMAT", "APTV", "BIIB", "BK", "CDNS", "CL", "COF", "CPRT", "CVS", "DHR", "EMR",
    "EXC", "FIS", "FISV", "GIS", "GLW", "HCA", "HLT", "IDXX", "ILMN", "KHC", "KMI", "LULU",
    "MNST", "MRNA", "NOC", "PAYX", "PGR", "PH", "PPG", "PYPL", "SYY", "T", "TRV", "WELL",
    "WM",
]

SP500_NASDAQ_BETWEEN_10B_50B = [
    "AEP", "AFL", "AIG", "ALGN", "ALL", "AMCR", "AON", "APA", "ARE", "ATO", "AVB", "AWK",
    "BALL", "BAX", "BDX", "BEN", "BILL", "BKR", "BXP", "CAG", "CARR", "CBRE", "CDW", "CHD",
    "CINF", "CLX", "CMS", "CNP", "CRL", "CTSH", "D", "DAL", "DD", "DE", "DG", "DHI", "DOV",
    "DRI", "DTE", "EA", "EBAY", "ED", "EFX", "EIX", "ELV", "EOG", "EQIX", "EQR", "ESS", "ETR",
    "EVRG", "FAST", "FE", "FITB", "FOX", "FOXA", "FTNT", "GD", "GPC", "GRMN", "HBAN", "HIG",
    "HPQ", "HSY", "HST", "IEX", "INCY", "IP", "IQV", "IR", "IT", "JBHT", "JKHY", "JCI", "KEY",
    "KEYS", "KIM", "KLAC", "KR", "L", "LDOS", "LEN", "LH", "LKQ", "LNT", "LUV", "LYB", "MCHP",
    "MKC", "MLM", "MO", "MPWR", "MTB", "MTCH", "MTD", "NDAQ", "NEM", "NTRS", "NUE", "NVCR",
    "NVR", "OGN", "OKE", "OMC", "ON", "OTIS", "PENN", "PKG", "PNC", "PNR", "PODD", "POOL",
    "PRU", "PSA", "PTC", "PWR", "QRVO", "RCL", "RJF", "RMD", "RSG", "SBAC", "SEDG", "SHW",
    "SJM", "SLB", "SNA", "SNPS", "STT", "STZ", "SWK", "SWKS", "SYF", "TDG", "TEL", "TFX",
    "TROW", "TSCO", "TT", "TYL", "UAL", "UDR", "UHS", "ULTA", "VICI", "VMC", "VRSK", "VTR",
    "VTRS", "WAB", "WAT", "WBD", "WEC", "WMB", "WY", "YUM",
]

LEVERAGED = [
    "AAPU", "AVL", "GGLL", "LLYX", "METU", "MSFU", "NFXL", "NVDL", "ORCX", "TQQQ", "UPRO",
]

ETF = [
    "GLD", "MAGS", "QQQ", "IBIT", "SCHD", "SLV", "SMH", "SPY", "TOPT", "XLF", "XLK",
]

OTHERS = ["BSX", "BULL", "DJT", "INFY", "SOFI"]

my_stocks = (
    SP500_NASDAQ_OVER_200B
    + SP500_NASDAQ_BETWEEN_100B_200B
    + SP500_NASDAQ_BETWEEN_50B_100B
    + SP500_NASDAQ_BETWEEN_10B_50B
    + LEVERAGED
    + ETF
    + OTHERS
)

# # a small list of stocks for testing purpose
# FOR_TESTING = ["WFC", "AIG", "UPS", "IQV", "WAT"]
#
# # for testing only
# my_stocks = (
#         FOR_TESTING
# )


positive_breakout_data = advanced_stock_scanner(my_stocks)

print("\n--- Final List: POSITIVE BREAKOUT Stocks ---")
if positive_breakout_data.empty:
    print("No stock passed all breakout conditions today.")
else:
    df = positive_breakout_data.copy().astype(str)

    # Compute column widths: max of header and all values
    col_widths = {col: max(len(col), df[col].map(len).max()) for col in df.columns}

    # Build separator and header
    sep = "+-" + "-+-".join("-" * col_widths[col] for col in df.columns) + "-+"
    header = "| " + " | ".join(col.ljust(col_widths[col]) for col in df.columns) + " |"

    print(sep)
    print(header)
    print(sep)
    for _, row in df.iterrows():
        print("| " + " | ".join(str(row[col]).ljust(col_widths[col]) for col in df.columns) + " |")
    print(sep)

    # Excel export: save breakout list to data/out with timestamped filename
    try:
        now_str = datetime.now().strftime("%Y%m%d%H%M")
        output_dir = Path(__file__).resolve().parents[2] / "data" / "out"
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"Breakout_{now_str}.xlsx"
        # Use the original DataFrame (not the string-cast copy) for export
        positive_breakout_data.to_excel(file_path, index=False)
        print(f"\nSaved as '{file_path}'")
    except Exception as e:
        print(f"\nFailed to save Excel file: {e}")


