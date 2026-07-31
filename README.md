# Daily Stock Monitor (DSM)

## Stock Screener

Advanced stock breakout scanner using technical analysis (DMAs, CAR, 52-week high).

### Prerequisites

- **Python** ≥ 3.12
- **uv** (package manager; [install](https://docs.astral.sh/uv/getting-started/))

### Dependencies

- yfinance ≥ 1.5.2 (Yahoo Finance data)
- pandas ≥ 3.0.5 (data processing)
- pandas-ta-classic == 0.6.52 (technical indicators)

### Run from Project Root

```bash
uv run python -m dsm
```

**Test Mode** (fast testing with 5 stocks):
```bash
uv run python -m dsm --test
```

Or run the scanner script directly:
```bash
uv run python src/dsm/screeners/stock-status.py
```

### Logic

> **Reference**: Stock screener logic adapted from [Mahesh Kaushik's Scanner](https://www.maheshkaushik.com/2026/07/trading-free-google-colab-scanner-code.html)
> 
> Thank you to Mahesh Kaushik for this wonderful stock screener logic!

1. Downloads 2 years of daily price data for each ticker
2. Calculates EMA 8, RSI, and 30/50/100/200-day moving averages (DMA)
3. Finds 52-week high/low prices and dates
4. Calculates the CAR score from the 52-week-high date
5. Identifies DMA and CAR breakout conditions
6. Prints all tickers in a formatted status table

### Testing

Test with a small set of stocks to verify changes quickly:

```bash
uv run python -m dsm --test
```

Test and `--my` ticker selections are defined in `src/dsm/main.py` and
`src/dsm/screeners/stock-status.py`.

### Output

- **Console**: Formatted table containing every ticker and its status indicators

### Project Structure

```
src/dsm/
  ├── main.py              # Entry point
  ├── config.py            # Stock lists & configuration
  ├── screeners/           # Screener modules
  │   └── stock-status.py   # Stock status and breakout screener
  └── utils/               # Utility functions
data/
  ├── inputs/              # Input data files
  └── outputs/             # Generated results
tests/                      # Unit & integration tests
logs/                       # Application logs
scripts/                    # Utility scripts
```
