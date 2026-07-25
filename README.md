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

### Output

- **Console**: Formatted table of breakout stocks
- **Excel**: `data/out/Breakout_YYYYMMDDHHmm.xlsx`
