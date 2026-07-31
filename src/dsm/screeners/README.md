# DMA and CAR screener

`dma-and-car.py` has two phases:

1. `scan_all()` fetches data and returns `list[Ticker]` raw records.
2. `display_tickers()` applies errors, colors, formatting, sorting, and table output.

## Raw `Ticker` data

Each record contains the ticker symbol, market cap/AUM, CMP, EMA 8, RSI(14),
30/50/100/200 DMAs, 200-DMA shift, zone, 52-week dates and prices, days since
the low, CAR, breakout flags, and any error.

Missing values remain `None` in the compute phase and display as `-`.

## Indicators

`pandas_ta_classic` supplies SMA, EMA, RSI, and rolling high/low calculations.
The 52-week window uses 252 trading sessions. The high/low positions are
located with `maxindex()` and `minindex()` so their dates remain aligned with
the prices.

## CAR

`compute_car(close_prices, high_date)` starts at the 52-week-high date, takes
the expanding mean of closing prices, and returns the largest `N` from 10 down
to 1 for which the final `N` values are monotonically increasing. It returns
zero when no qualifying tail exists.

## Zone codes

- `B++`: bullish stack and CMP above 110% of the 200 DMA
- `B+`: bullish stack and CMP between the 200 DMA and 110% of it
- `B-`: bearish stack and CMP between 90% of the 200 DMA and the 200 DMA
- `B--`: bearish stack and CMP below 90% of the 200 DMA
- `U`: unconfirmed or missing DMAs

## Commands

```bash
uv run src/dsm/screeners/dma-and-car.py
uv run src/dsm/screeners/dma-and-car.py --test
uv run src/dsm/screeners/dma-and-car.py --my
```
