import sys
import time
from datetime import datetime
from pathlib import Path

from market_screeners.model.market_universe import load_market_universe
from market_screeners.model.ticker import Ticker
from market_screeners.service.compute_service import scan_all
from market_screeners.service.display_service import display_tickers
from market_screeners.service.html_service import (
    capture_output,
    save_html,
)

DATA_DIR = Path("data")
MY_TICKERS_FILE = Path("my_tickers.txt")


def _flag_value(flag: str) -> str | None:
    """Return the value following `flag` in sys.argv, if present."""
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def _load_my_tickers() -> list[str]:
    """Load personal watch list from my_tickers.txt (gitignored).

    Each non-empty, non-comment line is treated as a ticker symbol.
    Raises SystemExit with a helpful message if the file is missing.
    """
    if not MY_TICKERS_FILE.exists():
        print(
            f"Error: {MY_TICKERS_FILE} not found.\n"
            "Copy my_tickers.example.txt to my_tickers.txt and add your symbols."
        )
        sys.exit(1)
    lines = MY_TICKERS_FILE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _auto_html_path(mode: str) -> str:
    """Build a timestamped HTML path in the data/ folder.

    Example: data/screener_full_20260802_143022.html
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(DATA_DIR / f"screener_{mode}_{ts}.html")


def main() -> None:
    """Parse CLI flags, compute raw data, and render the scanner output."""
    universe = load_market_universe()
    use_test = "--test" in sys.argv
    use_my = "--my" in sys.argv
    html_path = _flag_value("--export-html")

    if use_test:
        tickers = [universe[symbol] for symbol in sorted(universe)[:10]]
        mode = "test"
        print(f"(Running in TEST mode with {len(tickers)} tickers)\n")
    elif use_my:
        symbols = _load_my_tickers()
        tickers = [
            universe.get(symbol, Ticker(symbol=symbol, asset_type="unknown"))
            for symbol in symbols
        ]
        mode = "my"
        print(f"(Running in MY mode with {len(tickers)} tickers)\n")
    else:
        tickers = list(universe.values())
        mode = "full"

    # Always export an HTML to data/ unless the caller already specified a path.
    if html_path is None:
        html_path = _auto_html_path(mode)

    print(f"Processing {len(tickers)} symbols...\n", flush=True)
    start_time = time.perf_counter()
    calculations = scan_all(tickers)

    captured = capture_output(display_tickers, calculations, echo=True)
    save_html(captured, html_path)
    print(f"Report saved -> {html_path}")

    print(f"Execution time: {time.perf_counter() - start_time:.2f}s")
