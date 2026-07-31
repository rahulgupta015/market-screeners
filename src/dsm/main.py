import sys
from dsm.screeners.stock import scan_breakouts, export_to_excel, print_results
from dsm.stocks_us_50b_1m_options import STOCKS_BY_SYMBOL
from dsm.etfs_us_100m_1m_options import ETFS_BY_SYMBOL

# Combined lookup so a ticker can be resolved regardless of whether it's a
# stock or an ETF.
MARKET_CAP_BY_SYMBOL = {**STOCKS_BY_SYMBOL, **ETFS_BY_SYMBOL}

# Small fixed sample of symbols the user cares about, for --my runs.
MY_TICKERS = [
    "NFXL", "ORCX", "IBIT", "BULL", "BSX",
]


def get_all_tickers():
    """All symbols from the stock + ETF config files."""
    return sorted(MARKET_CAP_BY_SYMBOL)


def get_test_tickers():
    """First 10 symbols from MARKET_CAP_BY_SYMBOL, for --test runs."""
    return sorted(MARKET_CAP_BY_SYMBOL)[:10]


def get_my_tickers():
    """Small fixed sample of symbols, for --my runs."""
    return MY_TICKERS


def main():
    """Main entry point for stock screener"""
    # Check for --test / --my flags
    use_test = "--test" in sys.argv
    use_my = "--my" in sys.argv

    print("\n--- Final List: POSITIVE BREAKOUT Stocks ---")

    # Get tickers
    if use_test:
        all_tickers = get_test_tickers()
        print(f"(Running in TEST mode with {len(all_tickers)} stocks)\n")
    elif use_my:
        all_tickers = get_my_tickers()
        print(f"(Running in MY mode with {len(all_tickers)} stocks)\n")
    else:
        all_tickers = get_all_tickers()

    # Run scanner
    results_df = scan_breakouts(all_tickers)

    # Print results
    print_results(results_df)

    # Export to Excel
    if not results_df.empty:
        file_path = export_to_excel(results_df)
        if file_path:
            print(f"\nSaved as '{file_path}'")


if __name__ == "__main__":
    main()