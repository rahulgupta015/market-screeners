import sys
import time

from dsm.model.market_universe import load_market_universe
from dsm.model.ticker import Ticker
from dsm.service.compute_service import scan_all
from dsm.service.display_service import display_tickers

MY_TICKERS = ["NFXL", "ORCX", "IBIT", "BULL", "BSX"]


def main() -> None:
    """Parse CLI flags, compute raw data, and render the scanner output."""
    universe = load_market_universe()
    use_test = "--test" in sys.argv
    use_my = "--my" in sys.argv

    if use_test:
        tickers = [universe[symbol] for symbol in sorted(universe)[:10]]
        print(f"(Running in TEST mode with {len(tickers)} tickers)\n")
    elif use_my:
        tickers = [
            universe.get(symbol, Ticker(symbol=symbol, asset_type="unknown"))
            for symbol in MY_TICKERS
        ]
        print(f"(Running in MY mode with {len(tickers)} tickers)\n")
    else:
        tickers = list(universe.values())

    start_time = time.perf_counter()
    calculations = scan_all(tickers)
    display_tickers(calculations)
    print(f"Execution time: {time.perf_counter() - start_time:.2f}s")
