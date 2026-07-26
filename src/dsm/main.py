import sys
from dsm.screeners.stock import scan_breakouts, export_to_excel, print_results
from dsm.config import get_all_tickers, get_test_tickers


def main():
    """Main entry point for stock screener"""
    # Check for --test flag
    use_test = "--test" in sys.argv
    
    print("\n--- Final List: POSITIVE BREAKOUT Stocks ---")
    
    # Get tickers
    all_tickers = get_test_tickers() if use_test else get_all_tickers()
    if use_test:
        print(f"(Running in TEST mode with {len(all_tickers)} stocks)\n")
    
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
