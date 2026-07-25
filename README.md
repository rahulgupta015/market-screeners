# Daily Stock Monitor (DSM)

## Stock Screener

Advanced stock breakout scanner using technical analysis (DMAs, CAR, 52-week high).

### Prerequisites

- **Python** ≥ 3.12
- **uv** (package manager; [install](https://docs.astral.sh/uv/getting-started/))

### Dependencies

- yfinance ≥ 1.5.2 (Yahoo Finance data)
- pandas ≥ 3.0.5 (data processing)
- openpyxl ≥ 3.1.5 (Excel export)
- numpy ≥ 2.5.1 (numerical operations)
- matplotlib ≥ 3.11.1 (charting)

### Run from Project Root

```bash
uv run python src/dsm/stock-screener.py
```

### Logic

1. Downloads 2 years of daily price data for each stock
2. Calculates 30, 50, 100, and 200-day moving averages (DMA)
3. Finds the 52-week high date and CAR (Cumulative Average Return) since that date
4. Checks if CAR is rising over the last 10 days (Positive trend)
5. Identifies breakouts: CMP > all DMAs, within 20% of 200 DMA, and CAR positive
6. Returns sorted list by distance from 200 DMA
7. Exports results to Excel with timestamp

### Output

- **Console**: Formatted table of breakout stocks
- **Excel**: `data/out/Breakout_YYYYMMDDHHmm.xlsx`
