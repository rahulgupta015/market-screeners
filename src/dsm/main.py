from pathlib import Path
from runpy import run_path

# Small fixed sample of symbols the user cares about, for --my runs.
MY_TICKERS = [
    "NFXL", "ORCX", "IBIT", "BULL", "BSX",
]


def main():
    """Run the stock-status scanner used by every project entry point."""
    scanner = Path(__file__).parent / "screeners" / "stock-status.py"
    run_path(scanner, run_name="__main__")


if __name__ == "__main__":
    main()
