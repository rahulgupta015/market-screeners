# Daily Stock Monitor

A console stock screener for US stocks and ETFs. It downloads two years of
daily Yahoo Finance data, computes technical indicators with
`pandas-ta-classic`, and prints a status table for every requested ticker.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/)

Install dependencies and the editable project with:

```bash
uv sync
```

## Run

```bash
# Full stock and ETF universe
uv run python -m dsm

# First 10 symbols from the sorted universe
uv run python -m dsm --test

# Personal watch list
uv run python -m dsm --my
```

Direct execution remains available:

```bash
uv run src/dsm/screeners/dma-and-car.py --test
```

## Architecture

```text
market universe → Ticker → compute service → Calc → display service → Display → console
```

- `model/` contains dataclasses and market-universe data.
- `service/compute_service.py` fetches Yahoo Finance data and calculates indicators and CAR.
- `service/display_service.py` formats, colors, sorts, and prints results.
- `cli/main.py` handles command-line flags and orchestrates the services.

`Ticker` is immutable metadata loaded from the stock and ETF universe files.
`Calc` contains raw numeric/date results. `Display` contains final strings,
colors, checkmarks, and compact dates.

## Indicators

The scanner calculates EMA 8, RSI(14), 30/50/100/200 DMAs, 200-DMA shift,
52-week high/low dates and prices, days since the low, compact zone codes, and
DMA/CAR breakout flags.

CAR is the custom calculation: it takes the expanding mean of closing prices
from the 52-week-high date and scores the longest increasing tail from 10 down
to 1.

## Test

Tests use synthetic data and mocks, so they do not download market data:

```bash
uv run python -m unittest discover -s tests -v
```
