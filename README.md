# Daily Stock Monitor

A console stock screener for US stocks and ETFs. It downloads two years of
daily Yahoo Finance data, computes technical indicators with
`pandas-ta-classic`, and prints a status table for every requested ticker.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/)

Install/sync the project with:

```bash
uv sync
```

## Run

Run the full stock and ETF universe:

```bash
uv run python -m dsm
```

Run the first 10 symbols from the sorted universe:

```bash
uv run python -m dsm --test
```

Run the small personal watch list:

```bash
uv run python -m dsm --my
```

The scanner can also be run directly:

```bash
uv run src/dsm/screeners/dma-and-car.py --test
```

## Indicators and logic

For each ticker, the compute phase returns a raw `Ticker` record containing:

- Current market price and local market-cap/AUM data
- EMA 8 and RSI(14)
- 30, 50, 100, and 200-day simple moving averages
- Shift from the 200 DMA and compact zone code (`B++`, `B+`, `B-`, `B--`, or `U`)
- 52-week high/low dates and prices
- Days since the 52-week low
- CAR score and DMA/CAR breakout flags

CAR is the custom calculation: it takes the expanding mean of closing prices
from the 52-week-high date and scores the longest increasing tail from 10 down
to 1. The display phase then colors, sorts, and renders the raw records.

## Project layout

```text
src/dsm/
  main.py                    # package entry point
  __main__.py                # python -m dsm support
  screeners/
    dma-and-car.py           # compute and display pipeline
    stocks_us_50b_1m_options.py
    etfs_us_100m_1m_options.py
tests/
  test_dma_and_car.py        # offline unit tests
```

## Test

Run the offline unit tests without downloading market data:

```bash
uv run python -m unittest discover -s tests -v
```
