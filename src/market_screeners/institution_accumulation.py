# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance",
#     "pandas",
#     "pandas-ta-classic",
# ]
# ///
"""
Institutional Accumulation Scanner (pandas-ta-classic clean version)
--------------------------------------------------------------------
Uses pandas-ta-classic for all indicator calculations:
  - OBV  (On-Balance Volume)
  - ADL  (Accumulation/Distribution Line)
  - ATR  (Average True Range — used as a dynamic range benchmark)
  - SMA  (Simple Moving Average — 50d daily, 10-week weekly)

Custom logic implements four scored criteria + three context flags:

  SCORE (out of 4) — fires when institutional accumulation is detected:
    1. OBV/AD Divergence     : price flat/down but volume flow rising (Wyckoff)
    2. Acc vs Dist Days      : more up-volume days than down-volume days (O'Neil)
    3. VSA Event             : Stopping Volume or Spring detected (Wyckoff/Williams)
    4. RVOL Absorption       : high volume + tight range = supply absorbed (Raschke)

  CONTEXT (out of 3) — supporting clues, do NOT affect the score:
    1. Volume Dry-Up         : volume drying up before a breakout (Minervini/O'Neil)
    2. Trend(50d)            : price above 50-day MA = uptrend context (Weinstein)
    3. WeeklyTrend(10-week)  : price above 10-week MA = long-term trend support (O'Neil)

Run with: uv run src/market_screeners/institution_accumulation.py
"""

import pandas as pd
import yfinance as yf
import pandas_ta_classic as ta


# ---------------------------------------------------------------------------
# CONFIG — tweak these freely
# ---------------------------------------------------------------------------
TICKERS = ["MSTR", "INFY", "HDB", "IBIT", "NFXL", "ORCL", "BULL", "METU", "AAPL", "NVDA", "AVGO", "LOW", "ADP"]

FETCH_DAYS = "150d"          # daily history (extra bars needed to warm up rolling windows)
WEEKLY_FETCH_PERIOD = "1y"   # weekly history for the weekly-trend context flag
ANALYSIS_DAYS = 60           # only show signal days within this recent window
MIN_SCORE = 3                # only print days where >= this many of the 4 criteria fired

DIVERGENCE_WINDOW = 10       # look-back window (days) for OBV/AD vs price divergence
ACC_DIST_WINDOW = 25         # rolling window for counting acc days vs dist days
MOVE_THRESHOLD = 0.002       # 0.2% minimum close move to count as an acc/dist day
SUPPORT_WINDOW = 20          # rolling low window for the VSA Spring check
VOL_AVG_WINDOW = 20          # rolling window for volume averages and ATR
RVOL_THRESHOLD = 2.0         # volume must exceed this multiple of its rolling average
STOPPING_VOL_MULT = 1.5      # volume multiple for the Stopping Volume VSA check

VOL_DRYUP_WINDOW = 20        # rolling window for volume dry-up context check
VOL_DRYUP_MULT = 0.5         # volume must be below this fraction of its rolling average
TREND_MA_WINDOW = 50         # daily SMA window for the Trend(50d) context flag
WEEKLY_MA_WINDOW = 10        # weekly SMA window for the WeeklyTrend context flag


# ============================================================
# STRATEGY 1 — OBV / A-D Divergence
# Author  : Richard D. Wyckoff
# Style   : Wyckoff Composite Operator Accumulation
# Purpose : Detect stealth accumulation — price is flat or falling, but the
#           volume flow indicators (OBV and A/D Line) are quietly rising.
#           This means buyers are absorbing supply without moving price yet.
# ============================================================
def compute_obv_ad(df):
    """Compute OBV and A/D Line as the foundation for divergence detection."""
    # OBV: running total — adds volume on up-close days, subtracts on down-close days
    df["OBV"] = ta.obv(close=df["close"], volume=df["volume"])
    # A/D Line: CLV (close location within high-low range) weighted by volume, cumulative
    df["AD"]  = ta.ad(high=df["high"], low=df["low"], close=df["close"], volume=df["volume"])
    return df


def add_divergence_flag(df):
    """Flag days where price is flat/down over the window but OBV or AD is rising."""
    price_change = df["close"] - df["close"].shift(DIVERGENCE_WINDOW)
    obv_change   = df["OBV"]   - df["OBV"].shift(DIVERGENCE_WINDOW)
    ad_change    = df["AD"]    - df["AD"].shift(DIVERGENCE_WINDOW)

    # Divergence = price not rising AND at least one volume indicator IS rising
    df["div_flag"] = (price_change <= 0) & ((obv_change > 0) | (ad_change > 0))
    return df


# ============================================================
# STRATEGY 2 — Accumulation vs Distribution Days (25-day rolling)
# Author  : William J. O'Neil
# Style   : CANSLIM Institutional Accumulation/Distribution
# Purpose : Count days where institutions are net buyers (acc days) vs net
#           sellers (dist days) over a rolling 25-day window. More acc days
#           than dist days = institutions building positions.
# ============================================================
def add_acc_dist_flag(df):
    """Rolling 25-day count of accumulation days vs distribution days."""
    pct_change = df["close"].pct_change()
    # Volume must be higher than the prior day to count as an acc or dist day
    vol_up = df["volume"] > df["volume"].shift(1)

    # Acc day: close up >= 0.2% on rising volume
    is_acc_day  = (pct_change >= MOVE_THRESHOLD) & vol_up
    # Dist day: close down >= 0.2% on rising volume
    is_dist_day = (pct_change <= -MOVE_THRESHOLD) & vol_up

    df["acc_count"]     = is_acc_day.rolling(ACC_DIST_WINDOW).sum()
    df["dist_count"]    = is_dist_day.rolling(ACC_DIST_WINDOW).sum()
    # Flag fires when more accumulation days than distribution days in the window
    df["acc_dist_flag"] = df["acc_count"] > df["dist_count"]
    return df


# ============================================================
# STRATEGY 3 — VSA: Stopping Volume + Spring
# Author  : Richard D. Wyckoff, Tom Williams
# Style   : Wyckoff Phase C/D, Volume Spread Analysis
# Purpose : Two classic Wyckoff absorption patterns:
#   Stopping Volume — heavy volume + wide range + strong close on a down day:
#     big money absorbing the selling supply.
#   Spring — price undercuts recent support then snaps back above it with a
#     bullish close: a trap for weak hands, classic Phase C in Wyckoff.
# ============================================================
def add_vsa_flag(df):
    """Detect Stopping Volume and Spring events using VSA rules."""
    # ATR20 used as a dynamic benchmark for "wide range"
    df["atr20"] = ta.atr(high=df["high"], low=df["low"], close=df["close"], length=VOL_AVG_WINDOW)

    day_range  = df["high"] - df["low"]
    avg_volume = df["volume"].rolling(VOL_AVG_WINDOW).mean()

    # CLV (Close Location Value): 1.0 = closed at high, 0.0 = closed at low
    clv = (df["close"] - df["low"]) / day_range.replace(0, pd.NA)

    # Stopping Volume: heavy volume + wide bar + strong close + price still down on the day
    stopping_vol = (
            (df["volume"] > STOPPING_VOL_MULT * avg_volume) &  # volume spike
            (day_range > df["atr20"]) &                         # wide range
            (clv > 0.5) &                                       # closed in upper half
            (df["close"] < df["close"].shift(1))                # still a down close
    )

    # Spring: price dips below recent 20-day support, then closes back above it bullishly
    prior_support = df["low"].shift(1).rolling(SUPPORT_WINDOW).min()
    spring = (
            (df["low"] < prior_support) &       # undercut support (the "spring")
            (df["close"] > prior_support) &     # snapped back above support
            (df["close"] > df["open"])          # bullish close
    )

    df["vsa_event"] = "--"
    df.loc[stopping_vol, "vsa_event"] = "Stopping Vol"
    df.loc[spring, "vsa_event"] = "Spring"  # Spring takes priority if both fire on same day
    df["vsa_flag"] = df["vsa_event"] != "--"
    return df


# ============================================================
# STRATEGY 4 — RVOL Absorption (Narrow Range + Volume Spike)
# Author  : Wyckoff, Linda Bradford Raschke
# Style   : Wyckoff Absorption, Narrow-Range Day Patterns
# Purpose : When volume spikes well above average but the price range stays
#           tight, it means a large operator is absorbing supply or demand
#           without letting price escape. Classic accumulation footprint.
# ============================================================
def add_rvol_flag(df):
    """Relative volume spike + narrow range = institutional absorption."""
    avg_volume = df["volume"].rolling(VOL_AVG_WINDOW).mean()
    # RVOL = today's volume as a multiple of its rolling average
    df["rvol"] = df["volume"] / avg_volume
    # ATR20 as the benchmark for "normal" range — a narrow day is below ATR
    df["atr20"] = ta.atr(high=df["high"], low=df["low"], close=df["close"], length=VOL_AVG_WINDOW)

    narrow_range  = (df["high"] - df["low"]) < df["atr20"]
    # Both conditions must fire: volume spike AND tight range
    df["rvol_flag"] = (df["rvol"] > RVOL_THRESHOLD) & narrow_range
    return df


# ============================================================
# CONTEXT 1 — Volume Dry-Up
# Author  : Mark Minervini, William O'Neil
# Style   : VCP (Volatility Contraction Pattern), CANSLIM Quiet Period
# Purpose : Before a breakout, institutions stop selling and volume dries up.
#           Volume well below its average = the float is being held tight.
#           This is a supporting clue, not a standalone signal.
# ============================================================
def add_vol_dryup_flag(df):
    """Volume significantly below its rolling average = pre-breakout quiet."""
    avg_volume = df["volume"].rolling(VOL_DRYUP_WINDOW).mean()
    # Flag fires when today's volume is less than 50% of its rolling average
    df["vol_dryup"] = df["volume"] < (VOL_DRYUP_MULT * avg_volume)
    return df


# ============================================================
# CONTEXT 2 — Trend(50d)
# Author  : Stan Weinstein, William O'Neil
# Style   : Stage Analysis (Stage 2 uptrend), CANSLIM Trend Rules
# Purpose : Accumulation signals are most meaningful when the stock is in an
#           established uptrend. Price above 50-day MA confirms Stage 2.
# ============================================================
def add_trend_flag(df):
    """Price above 50-day SMA = healthy intermediate-term uptrend context."""
    df["ma50"]     = ta.sma(df["close"], length=TREND_MA_WINDOW)
    df["trend_ok"] = df["close"] > df["ma50"]
    return df


# ============================================================
# CONTEXT 3 — WeeklyTrend (10-week MA)
# Author  : William O'Neil, Mark Minervini
# Style   : 10-week Moving Average Rule, Trend Template
# Purpose : Institutions hold positions that show up clearly on the weekly
#           chart. Price above the 10-week MA = long-term institutional
#           support is intact. Maps weekly result onto each daily row.
# ============================================================
def add_weekly_trend_flag(df, symbol):
    """Map 10-week trend flag onto daily rows via as-of merge."""
    weekly = yf.Ticker(symbol).history(period=WEEKLY_FETCH_PERIOD, interval="1wk")
    if weekly.empty:
        df["weekly_trend_ok"] = False
        return df

    weekly = weekly.rename(columns=str.lower)
    weekly["ma10w"]           = ta.sma(weekly["close"], length=WEEKLY_MA_WINDOW)
    weekly["weekly_trend_ok"] = weekly["close"] > weekly["ma10w"]

    # Reset index so Date becomes a plain column for the merge
    weekly      = weekly.reset_index().rename(columns={"Date": "Date"})
    daily_dates = df.reset_index().rename(columns={"Date": "Date"})[["Date"]]

    # As-of merge: each daily date picks up the most recently completed week's flag
    merged = pd.merge_asof(
        daily_dates.sort_values("Date"),
        weekly[["Date", "weekly_trend_ok"]].sort_values("Date"),
        on="Date",
        direction="backward",
    )

    df["weekly_trend_ok"] = merged["weekly_trend_ok"].fillna(False).values
    return df


# ---------------------------------------------------------------------------
# Per-ticker pipeline — runs all strategies and context flags for one symbol
# ---------------------------------------------------------------------------
def analyze_ticker(symbol):
    df = yf.Ticker(symbol).history(period=FETCH_DAYS, interval="1d")
    if df.empty:
        print(f"  {symbol:<6} ... no data returned, skipping")
        return pd.DataFrame()

    print(f"  {symbol:<6} ... {len(df)} bars loaded")

    # yfinance returns Title-case columns (Close, Volume…) — normalise to lowercase
    df = df.rename(columns=str.lower)

    # Build indicator foundations
    df = compute_obv_ad(df)

    # Score criteria (each contributes 1 point to the score)
    df = add_divergence_flag(df)
    df = add_acc_dist_flag(df)
    df = add_vsa_flag(df)
    df = add_rvol_flag(df)

    # Context flags (informational only — do not affect the score)
    df = add_vol_dryup_flag(df)
    df = add_trend_flag(df)
    df = add_weekly_trend_flag(df, symbol)

    # Composite score: sum of the 4 binary criteria flags
    df["score"] = (
            df["div_flag"].astype(int)
            + df["acc_dist_flag"].astype(int)
            + df["vsa_flag"].astype(int)
            + df["rvol_flag"].astype(int)
    )

    # Context score: sum of the 3 binary context flags (shown separately)
    df["context_score"] = (
            df["vol_dryup"].astype(int)
            + df["trend_ok"].astype(int)
            + df["weekly_trend_ok"].astype(int)
    )

    df["symbol"] = symbol
    return df


# ---------------------------------------------------------------------------
# Main — collect signals across all tickers and print a single sorted table
# ---------------------------------------------------------------------------
def main():
    print(f"Fetching {FETCH_DAYS} daily + {WEEKLY_FETCH_PERIOD} weekly OHLCV for {len(TICKERS)} tickers...")

    all_rows = []
    for symbol in TICKERS:
        df = analyze_ticker(symbol)
        if df.empty:
            continue

        # Trim to recent window — earlier bars were only needed for warm-up
        recent  = df.tail(ANALYSIS_DAYS)
        signals = recent[recent["score"] >= MIN_SCORE]
        all_rows.append(signals)

    if not all_rows:
        print("\nNo signal days found for any ticker.")
        return

    result = pd.concat(all_rows).reset_index()
    # yfinance DatetimeIndex is named "Date" — after reset_index it becomes a column
    if "Date" not in result.columns:
        result = result.rename(columns={"index": "Date"})

    # Sort by symbol A-Z, then most recent date first within each symbol
    result = result.sort_values(["symbol", "Date"], ascending=[True, False])

    header = (
        f"{'Symbol':<8} {'Date':<12} {'Score':<12} {'Context':<11} {'OBV/AD Div':<12} "
        f"{'AccVsDist(25d)':<16} {'VSA Event':<14} {'RVOL Absorb':<13} "
        f"{'VolDryUp':<10} {'Trend(50d)':<12} {'WeeklyTrend'}"
    )
    sep = "=" * len(header)
    print()
    print(sep)
    print(f"INSTITUTIONAL ACCUMULATION SIGNALS  (min score >= {MIN_SCORE}/4 criteria | context shown as x/3)")
    print(sep)
    print(header)
    print("-" * len(header))

    for _, row in result.iterrows():
        acc_dist_str = f"{int(row['acc_count'])} vs {int(row['dist_count'])}"
        print(
            f"{row['symbol']:<8} {row['Date'].strftime('%Y-%m-%d'):<12} "
            f"{str(int(row['score'])) + '/4':<12} "
            f"{str(int(row['context_score'])) + '/3':<11} "
            f"{'Yes' if row['div_flag'] else 'No':<12} "
            f"{acc_dist_str:<16} "
            f"{row['vsa_event']:<14} "
            f"{'Yes' if row['rvol_flag'] else 'No':<13} "
            f"{'Yes' if row['vol_dryup'] else 'No':<10} "
            f"{'Yes' if row['trend_ok'] else 'No':<12} "
            f"{'Yes' if row['weekly_trend_ok'] else 'No'}"
        )

    print("-" * len(header))
    print(f"{len(result)} signal day(s) across {result['symbol'].nunique()}/{len(TICKERS)} tickers")


if __name__ == "__main__":
    main()
