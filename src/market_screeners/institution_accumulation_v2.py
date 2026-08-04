# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance",
#     "pandas",
# ]
# ///
"""
Institutional Accumulation Scanner
-----------------------------------
Fetches daily OHLCV (150 days, for rolling-window warm-up) plus weekly OHLCV
for a fixed list of tickers, computes 4 "composite" accumulation criteria
per day, and prints a single table of all days (in the last 60 days) where
at least MIN_SCORE of the 4 criteria fired.

Alongside the score, 3 extra CONTEXT columns are shown (they don't affect
the score, they just help you judge signal quality):
  - VolDryUp    : volume has dried up recently (pre-breakout quiet)
  - Trend(50d)  : price is above its 50-day moving average
  - WeeklyTrend : price is above its 10-week moving average

Run with: uv run src/market_screeners/institution_accumulation_v2.py
"""

import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# CONFIG — tweak these freely
# ---------------------------------------------------------------------------
TICKERS = ["INFY", "HDB", "IBIT", "NFXL", "ORCL", "BULL", "METU", "AAPL", "NVDA", "AVGO", "LOW", "ADP"]

FETCH_DAYS = "150d"          # daily history to download (warm-up for rolling windows)
WEEKLY_FETCH_PERIOD = "1y"   # weekly history for weekly-trend context
ANALYSIS_DAYS = 60           # only show signal days within this recent window
MIN_SCORE = 3                # only print days where >= this many of the 4 criteria fired

DIVERGENCE_WINDOW = 10       # days used to check OBV/AD vs price divergence
ACC_DIST_WINDOW = 25         # rolling window for accumulation-day vs distribution-day count
MOVE_THRESHOLD = 0.002       # 0.2% close move to qualify as an "up day" / "down day"
SUPPORT_WINDOW = 20          # rolling low window used for the VSA "Spring" check
VOL_AVG_WINDOW = 20          # rolling average window for volume & range comparisons
RVOL_THRESHOLD = 2.0         # volume must be > this multiple of its rolling average
STOPPING_VOL_MULT = 1.5      # volume multiple used for the "Stopping Volume" VSA check

VOL_DRYUP_WINDOW = 20        # rolling average window used for the volume dry-up context check
VOL_DRYUP_MULT = 0.5         # volume must be below this multiple of its rolling average
TREND_MA_WINDOW = 50         # daily moving average window for the trend context check
WEEKLY_MA_WINDOW = 10        # weekly moving average window for the weekly-trend context check


# ============================================================
# STRATEGY 1 — OBV / A-D Divergence
# Author: Richard D. Wyckoff
# Style: Wyckoff Composite Operator Accumulation
# Purpose: Detect stealth accumulation when price is flat/down but OBV or A/D rises.
# ============================================================
def compute_obv_ad(df: pd.DataFrame) -> pd.DataFrame:
    """Compute OBV and A/D line as foundations for divergence."""
    # OBV: add volume on up-close, subtract on down-close, 0 on flat
    direction = df["Close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    df["OBV"] = (direction * df["Volume"]).cumsum()

    # A/D Line: CLV weighted by volume
    day_range = (df["High"] - df["Low"]).replace(0, pd.NA)
    clv = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / day_range
    df["AD"] = (clv.fillna(0) * df["Volume"]).cumsum()

    return df


def add_divergence_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Price flat/down over window, OBV or AD rising -> divergence accumulation."""
    price_change = df["Close"] - df["Close"].shift(DIVERGENCE_WINDOW)
    obv_change = df["OBV"] - df["OBV"].shift(DIVERGENCE_WINDOW)
    ad_change = df["AD"] - df["AD"].shift(DIVERGENCE_WINDOW)

    price_flat_or_down = price_change <= 0
    obv_rising = obv_change > 0
    ad_rising = ad_change > 0

    df["div_flag"] = price_flat_or_down & (obv_rising | ad_rising)
    return df


# ============================================================
# STRATEGY 2 — Accumulation vs Distribution (25-day)
# Author: William J. O’Neil
# Style: CANSLIM Institutional Accumulation/Distribution
# Purpose: Count up-volume vs down-volume days to detect net institutional buying.
# ============================================================
def add_acc_dist_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling 25-day accumulation vs distribution day count."""
    pct_change = df["Close"].pct_change()
    vol_up = df["Volume"] > df["Volume"].shift(1)

    is_acc_day = (pct_change >= MOVE_THRESHOLD) & vol_up
    is_dist_day = (pct_change <= -MOVE_THRESHOLD) & vol_up

    df["acc_count"] = is_acc_day.rolling(ACC_DIST_WINDOW).sum()
    df["dist_count"] = is_dist_day.rolling(ACC_DIST_WINDOW).sum()
    df["acc_dist_flag"] = df["acc_count"] > df["dist_count"]
    return df


# ============================================================
# STRATEGY 3 — VSA (Stopping Volume + Spring)
# Author: Richard D. Wyckoff, Tom Williams
# Style: Wyckoff Phase C/D, Volume Spread Analysis
# Purpose: Detect springs, traps, and absorption by large operators.
# ============================================================
def add_vsa_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Detect Stopping Volume and Spring events via VSA logic."""
    day_range = df["High"] - df["Low"]
    avg_range = day_range.rolling(VOL_AVG_WINDOW).mean()
    avg_volume = df["Volume"].rolling(VOL_AVG_WINDOW).mean()

    # Close Location Value: 1 = closed at the high, 0 = closed at the low
    clv = (df["Close"] - df["Low"]) / day_range.replace(0, pd.NA)

    stopping_vol = (
            (df["Volume"] > STOPPING_VOL_MULT * avg_volume)
            & (day_range > avg_range)
            & (clv > 0.5)
            & (df["Close"] < df["Close"].shift(1))
    )

    prior_support = df["Low"].shift(1).rolling(SUPPORT_WINDOW).min()
    spring = (
            (df["Low"] < prior_support)
            & (df["Close"] > prior_support)
            & (df["Close"] > df["Open"])
    )

    df["vsa_event"] = "--"
    df.loc[stopping_vol, "vsa_event"] = "Stopping Vol"
    df.loc[spring, "vsa_event"] = "Spring"  # spring takes priority if both true
    df["vsa_flag"] = df["vsa_event"] != "--"
    return df


# ============================================================
# STRATEGY 4 — RVOL Absorption
# Author: Wyckoff, Linda Raschke
# Style: Wyckoff Absorption, Narrow-Range Patterns
# Purpose: Identify high-volume, tight-range bars showing institutional absorption.
# ============================================================
def add_rvol_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Relative volume spike + narrow range -> absorption by large players."""
    avg_volume = df["Volume"].rolling(VOL_AVG_WINDOW).mean()
    avg_range = (df["High"] - df["Low"]).rolling(VOL_AVG_WINDOW).mean()

    df["rvol"] = df["Volume"] / avg_volume
    narrow_range = (df["High"] - df["Low"]) < avg_range

    df["rvol_flag"] = (df["rvol"] > RVOL_THRESHOLD) & narrow_range
    return df


# ============================================================
# CONTEXT 1 — Volume Dry-Up
# Author: Mark Minervini, William O’Neil
# Style: VCP Stage 2, CANSLIM Quiet Period
# Purpose: Detect float drying up before a breakout.
# ============================================================
def add_vol_dryup_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Volume well below its recent average -> pre-breakout quiet / dry-up."""
    avg_volume = df["Volume"].rolling(VOL_DRYUP_WINDOW).mean()
    df["vol_dryup"] = df["Volume"] < (VOL_DRYUP_MULT * avg_volume)
    return df


# ============================================================
# CONTEXT 2 — Trend(50d)
# Author: Stan Weinstein, William O’Neil
# Style: Stage Analysis, CANSLIM Trend Rules
# Purpose: Confirm intermediate-term uptrend strength.
# ============================================================
def add_trend_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Close above 50-day MA -> healthy intermediate uptrend context."""
    trend_ma = df["Close"].rolling(TREND_MA_WINDOW).mean()
    df["trend_ok"] = df["Close"] > trend_ma
    return df


# ============================================================
# CONTEXT 3 — WeeklyTrend(10-week)
# Author: William O’Neil, Mark Minervini
# Style: 10-week Moving Average Rule, Trend Template
# Purpose: Confirm long-term institutional trend support.
# ============================================================
def add_weekly_trend_flag(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Map weekly 10-week trend flag onto daily rows via as-of merge."""
    weekly = yf.Ticker(symbol).history(period=WEEKLY_FETCH_PERIOD, interval="1wk")

    if weekly.empty:
        df["weekly_trend_ok"] = False
        return df

    weekly_ma = weekly["Close"].rolling(WEEKLY_MA_WINDOW).mean()
    weekly_trend = (weekly["Close"] > weekly_ma).rename("weekly_trend_ok")
    weekly_trend = weekly_trend.reset_index().rename(columns={weekly_trend.index.name or "Date": "Date"})

    daily_dates = df.reset_index().rename(columns={df.index.name or "Date": "Date"})[["Date"]]

    merged = pd.merge_asof(
        daily_dates.sort_values("Date"),
        weekly_trend.sort_values("Date"),
        on="Date",
        direction="backward",
    )

    df["weekly_trend_ok"] = merged["weekly_trend_ok"].fillna(False).values
    return df


# ---------------------------------------------------------------------------
# Per-ticker pipeline
# ---------------------------------------------------------------------------
def analyze_ticker(symbol: str) -> pd.DataFrame:
    df = yf.Ticker(symbol).history(period=FETCH_DAYS, interval="1d")
    if df.empty:
        print(f"  {symbol:<6} ... no data returned, skipping")
        return pd.DataFrame()

    print(f"  {symbol:<6} ... {len(df)} bars loaded")

    # Core volume/price foundations
    df = compute_obv_ad(df)

    # Criteria (score components)
    df = add_divergence_flag(df)
    df = add_acc_dist_flag(df)
    df = add_vsa_flag(df)
    df = add_rvol_flag(df)

    # Context flags (do not affect score)
    df = add_vol_dryup_flag(df)
    df = add_trend_flag(df)
    df = add_weekly_trend_flag(df, symbol)

    # Composite scores
    df["score"] = (
            df["div_flag"].astype(int)
            + df["acc_dist_flag"].astype(int)
            + df["vsa_flag"].astype(int)
            + df["rvol_flag"].astype(int)
    )

    df["context_score"] = (
            df["vol_dryup"].astype(int)
            + df["trend_ok"].astype(int)
            + df["weekly_trend_ok"].astype(int)
    )

    df["symbol"] = symbol
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"Fetching {FETCH_DAYS} daily + {WEEKLY_FETCH_PERIOD} weekly OHLCV for {len(TICKERS)} tickers...")

    all_rows = []
    for symbol in TICKERS:
        df = analyze_ticker(symbol)
        if df.empty:
            continue

        # Only look at the most recent ANALYSIS_DAYS for signals
        recent = df.tail(ANALYSIS_DAYS)
        signals = recent[recent["score"] >= MIN_SCORE]
        all_rows.append(signals)

    if not all_rows:
        print("\nNo signal days found for any ticker.")
        return

    result = pd.concat(all_rows)
    result = result.reset_index()
    # yfinance DatetimeIndex is named "Date"; after reset_index it becomes a column.
    if "Date" not in result.columns:
        result = result.rename(columns={"index": "Date"})

    # Sort by symbol (asc), then date descending within each symbol
    result = result.sort_values(["symbol", "Date"], ascending=[True, False])

    # ---- Print single table ----
    header = (
        f"{'Symbol':<8} {'Date':<12} {'Score':<12} {'Context':<11} {'OBV/AD Div':<12} "
        f"{'AccVsDist(25d)':<16} {'VSA Event':<14} {'RVOL Absorb':<13} "
        f"{'VolDryUp':<10} {'Trend(50d)':<12} {'WeeklyTrend'}"
    )
    sep = "=" * len(header)
    print()
    print(sep)
    print(f"INSTITUTIONAL ACCUMULATION SIGNALS  (min score >= {MIN_SCORE}/4 criteria | context shown separately as x/3)")
    print(sep)
    print(header)
    print("-" * len(header))

    for _, row in result.iterrows():
        date_str = row["Date"].strftime("%Y-%m-%d")
        score_str = f"{int(row['score'])}/4"
        context_str = f"{int(row['context_score'])}/3"
        div_str = "Yes" if row["div_flag"] else "No"
        acc_dist_str = f"{int(row['acc_count'])} vs {int(row['dist_count'])}"
        rvol_str = "Yes" if row["rvol_flag"] else "No"
        dryup_str = "Yes" if row["vol_dryup"] else "No"
        trend_str = "Yes" if row["trend_ok"] else "No"
        weekly_str = "Yes" if row["weekly_trend_ok"] else "No"

        print(
            f"{row['symbol']:<8} {date_str:<12} {score_str:<12} {context_str:<11} {div_str:<12} "
            f"{acc_dist_str:<16} {row['vsa_event']:<14} {rvol_str:<13} "
            f"{dryup_str:<10} {trend_str:<12} {weekly_str}"
        )

    print("-" * len(header))
    print(f"{len(result)} signal day(s) across {result['symbol'].nunique()}/{len(TICKERS)} tickers")


if __name__ == "__main__":
    main()
