# Market Screeners

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
uv run python -m market_screeners

# First 10 symbols from the sorted universe
uv run python -m market_screeners --test

# Personal watch list
uv run python -m market_screeners --my
```

Direct execution remains available:

```bash
uv run src/market_screeners/screeners/dma-and-car.py --test
```

## Architecture

```text
market universe -> Ticker -> compute service -> Calc -> display service -> Display -> console
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

### Breakouts

DMA BO is independent of Zone and requires `CMP > 50 DMA > 100 DMA > 200 DMA`
with `0% < Shift% < 10%`. DMA breakouts are sorted by Shift% ascending.

CAR BO is also independent of Zone and requires CMP above the 50, 100, and
200 DMAs, `0% < Shift% < 10%`, and `CAR >= 5`. CAR breakouts are sorted by CAR
descending and then Shift% ascending. A ticker can appear in both breakout
tables.

### Zones

Zones are display-only and never affect breakout flags:

- `B++`: bullish ordering with all 50/100/200 DMAs rising
- `B+`: CMP above all three DMAs with the 50 DMA crossing upward over the 100 or 200 DMA
- `B--`: bearish ordering with all 50/100/200 DMAs falling
- `B-`: CMP below all three DMAs with the 50 DMA crossing downward below the 100 or 200 DMA
- `U`: anything else

### Colors

RSI uses purple through 25, green through 40, yellow through 65, and red
above 65. EMA and DMA values are green when CMP is above them. Shift% uses
purple above 10, green from 0.01 to 10, yellow from -10 through 0, and red
below -10. CAR uses red below 2, yellow from 2 through 4, green from 5
through 9, and purple from 10 upward. `52WL - 52WH` is green when positive.

CAR is the custom calculation: it takes the expanding mean of closing prices
from the 52-week-high date and scores the longest increasing tail from 10 down
to 1.

## Test

Tests use synthetic data and mocks, so they do not download market data:

```bash
uv run python -m unittest discover -s tests -v
```
