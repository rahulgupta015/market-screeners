# Stock Status Scanner — Logic Reference

This document explains the logic implemented in `stock-status.py`.

Every ticker in `TICKERS` is processed — no stock is ever skipped. If a
metric cannot be calculated (not enough historical data), the corresponding
cell is simply left blank rather than guessed at or omitted from the table.

## Output columns

`Stock, Market Cap ($B), CMP, DMA BO, CAR BO, 30 DMA, 50 DMA, 100 DMA, 200 DMA, Shift %, CAR, Zone, 52W High, 52W Low, Days Since 52W Low, EMA 8, RSI, 52W High Price, 52W Low Price`

Rows are sorted by ticker. The current date is printed above the table.
Market cap / AUM is pulled from yfinance and shown in $ Billions.
`get_market_cap_billions()` tries, in order: (1) `fast_info` market cap
(both attribute- and dict-style key names, since yfinance versions
differ), (2) `fast_info` price × shares outstanding, (3) `.info["marketCap"]`,
and (4) `.info["totalAssets"]` — the AUM field Yahoo Finance uses for ETFs.
Left blank if none of these are available.

## Zone

`get_zone(cmp, dma50, dma100, dma200)` returns one of the following, based
purely on CMP and the 50/100/200 DMAs:

| Zone             | Condition                                                              |
|------------------|-------------------------------------------------------------------------|
| BULLISH          | CMP > 50 DMA > 100 DMA > 200 DMA **and** CMP > 1.10 × 200 DMA          |
| ENTERING BULLISH | CMP > 50 DMA > 100 DMA > 200 DMA **and** 200 DMA < CMP ≤ 1.10 × 200 DMA |
| UNCONFIRMED      | DMAs not stacked cleanly (fallback / neutral zone)                      |
| ENTERING BEARISH | CMP < 50 DMA < 100 DMA < 200 DMA **and** 0.90 × 200 DMA ≤ CMP < 200 DMA |
| BEARISH          | CMP < 50 DMA < 100 DMA < 200 DMA **and** CMP < 0.90 × 200 DMA          |

If any DMA is unavailable (insufficient history), the zone defaults to
`UNCONFIRMED`.

**Zone color:**
- BULLISH → purple
- ENTERING BULLISH → green
- UNCONFIRMED → yellow
- ENTERING BEARISH → orange
- BEARISH → red

## CAR (score)

`compute_car(close_prices, high_date)`:

1. Start from the 52-week-high date and take the expanding mean of the
   closing prices from that date forward.
2. Find the largest N (checked from 10 down to 1) for which the **last N**
   expanding-mean values are monotonically increasing.
3. Return that N as the CAR score, or 0 if none qualify.

CAR requires a full year (252 trading days) of history to establish the
52-week high; if unavailable, CAR is left blank.

**CAR color:**
- score ≤ 1 → red
- 2 ≤ score ≤ 4 → orange
- 5 ≤ score ≤ 7 → yellow
- score ≥ 8 → green

## Breakout flags

- **DMA BO** (green check ✔): Zone is `ENTERING BULLISH` **and**
  CAR score ≥ 1. Blank otherwise.
- **CAR BO** (green check ✔): CMP > 50 DMA **and** CMP > 100 DMA
  **and** CMP > 200 DMA, CMP is within 0.1%–10% above the 200 DMA (Shift %
  between 0.1 and 10), **and** CAR score ≥ 7. Blank otherwise.

## DMA columns (30 / 50 / 100 / 200)

Each cell shows the DMA value, colored green when CMP is above that DMA
(plain/uncolored otherwise). No separate marker is used — the color on
the value itself is the signal.

## Shift % From 200 DMA

`shift_pct = (CMP - 200 DMA) / 200 DMA × 100`

**Color:**
- `> 10` → light purple
- `0.1` to `10` → green
- `-10` to `0.1` → yellow
- `< -10` → red

## EMA 8 and RSI

EMA 8 and RSI(14) are calculated with `pandas_ta_classic` and shown at the
end of the table. EMA 8 is colored green when CMP is above it.

## 52W High / 52W Low / Days Since 52W Low

Computed from the trailing 252 trading days (left blank if less than a
year of history is available):

- **52W High / 52W Low**: the date (e.g. `Jul-15-2026`) on which the
  trailing-year high / low occurred.
- **Days Since 52W Low**: number of days since the 52-week-low date.
  - Positive if the low occurred **after** the 52-week high date (i.e. the
    low is more recent than the high — a fresh low).
  - Negative if the low occurred **before** the high date (i.e. the low is
    "stale" relative to a more recent high).
  - Shown in green text when this value is positive.

## Code structure

- `pandas_ta_classic.sma()` — calculates the 30/50/100/200 DMAs.
- `pandas_ta_classic.ema()` / `pandas_ta_classic.rsi()` — calculates EMA 8 and RSI(14).
- `pandas_ta_classic.maxindex()` / `minindex()` — locate 52-week high/low dates.
- `compute_car(close_prices, high_date)` — returns the CAR score.
- `get_zone(cmp, dma50, dma100, dma200)` — returns the Zone label.
- `get_market_cap_billions(ticker)` — fetches market cap / AUM in $B via
  yfinance, trying `fast_info` (both key-casing styles) then falling back
  to `.info["marketCap"]` / `.info["totalAssets"]` (ETF AUM).
- `scan_all(ticker_list)` — loops every ticker, builds one row per stock
  (never skips a stock; blanks whatever can't be calculated).
- `print_results(results)` — renders the final table, date header included.
