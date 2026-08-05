# Institutional accumulation screener moved into package-style module.
# Original logic kept; this module exports main().

import pandas as pd
import yfinance as yf
import pandas_ta_classic as ta

# ---------------------------------------------------------------------------
# CONFIG — tweak these freely
# ---------------------------------------------------------------------------
# No hardcoded ticker list — consume tickers from the shared market_universe,
# the --my watchlist, or the --test subset (first 10 symbols).

# Fetch 210 days of daily history to warm up indicators, but analyze the most recent 120 days.
FETCH_DAYS = "210d"          # daily history (210 days for indicator warm-up)
WEEKLY_FETCH_PERIOD = "1y"   # weekly history for the weekly-trend context flag (unchanged)
ANALYSIS_DAYS = 120           # analyze the last 120 days
MIN_SCORE = 3                 # only print days where >= this many of the 5 criteria fired

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
# STRATEGY 1 — ANT MVP (Momentum–Volume–Price)
# ============================================================
def add_ant_mvp_flag(df):
    """Compute ANT MVP criteria and append result columns."""
    up_days = (df["close"] > df["close"].shift(1)).rolling(15).sum()
    df["ANT_Momentum"] = up_days >= 12

    vol_sma50 = df["volume"].rolling(50).mean()
    df["ANT_Volume"] = df["volume"] > (vol_sma50 * 1.20)

    price_change_15 = (df["close"] - df["close"].shift(15)) / df["close"].shift(15)
    df["ANT_Price"] = price_change_15 > 0.20

    df["ANT_MVP"] = df["ANT_Momentum"] & df["ANT_Volume"] & df["ANT_Price"]
    return df


# ============================================================
# STRATEGY 2 — OBV / A-D Divergence
# ============================================================
def compute_obv_ad(df):
    df["OBV"] = ta.obv(close=df["close"], volume=df["volume"])
    df["AD"]  = ta.ad(high=df["high"], low=df["low"], close=df["close"], volume=df["volume"])
    return df


def add_divergence_flag(df):
    price_change = df["close"] - df["close"].shift(DIVERGENCE_WINDOW)
    obv_change   = df["OBV"]   - df["OBV"].shift(DIVERGENCE_WINDOW)
    ad_change    = df["AD"]    - df["AD"].shift(DIVERGENCE_WINDOW)

    df["div_flag"] = (price_change <= 0) & ((obv_change > 0) | (ad_change > 0))
    return df


# ============================================================
# STRATEGY 3 — Accumulation vs Distribution Days
# ============================================================
def add_acc_dist_flag(df):
    pct_change = df["close"].pct_change()
    vol_up = df["volume"] > df["volume"].shift(1)

    is_acc_day  = (pct_change >= MOVE_THRESHOLD) & vol_up
    is_dist_day = (pct_change <= -MOVE_THRESHOLD) & vol_up

    df["acc_count"]     = is_acc_day.rolling(ACC_DIST_WINDOW).sum()
    df["dist_count"]    = is_dist_day.rolling(ACC_DIST_WINDOW).sum()
    df["acc_dist_flag"] = df["acc_count"] > df["dist_count"]
    return df


# ============================================================
# STRATEGY 4 — VSA: Stopping Volume + Spring
# ============================================================
def add_vsa_flag(df):
    df["atr20"] = ta.atr(high=df["high"], low=df["low"], close=df["close"], length=VOL_AVG_WINDOW)

    day_range  = df["high"] - df["low"]
    avg_volume = df["volume"].rolling(VOL_AVG_WINDOW).mean()

    clv = (df["close"] - df["low"]) / day_range.replace(0, pd.NA)

    stopping_vol = (
            (df["volume"] > STOPPING_VOL_MULT * avg_volume) &
            (day_range > df["atr20"]) &
            (clv > 0.5) &
            (df["close"] < df["close"].shift(1))
    )

    prior_support = df["low"].shift(1).rolling(SUPPORT_WINDOW).min()
    spring = (
            (df["low"] < prior_support) &
            (df["close"] > prior_support) &
            (df["close"] > df["open"])
    )

    df["vsa_event"] = "--"
    df.loc[stopping_vol, "vsa_event"] = "Stopping Vol"
    df.loc[spring, "vsa_event"] = "Spring"
    df["vsa_flag"] = df["vsa_event"] != "--"
    return df


# ============================================================
# STRATEGY 4 — RVOL Absorption
# ============================================================
def add_rvol_flag(df):
    avg_volume = df["volume"].rolling(VOL_AVG_WINDOW).mean()
    df["rvol"] = df["volume"] / avg_volume
    df["atr20"] = ta.atr(high=df["high"], low=df["low"], close=df["close"], length=VOL_AVG_WINDOW)

    narrow_range  = (df["high"] - df["low"]) < df["atr20"]
    df["rvol_flag"] = (df["rvol"] > RVOL_THRESHOLD) & narrow_range
    return df


# ============================================================
# CONTEXT FLAGS
# ============================================================
def add_vol_dryup_flag(df):
    avg_volume = df["volume"].rolling(VOL_DRYUP_WINDOW).mean()
    df["vol_dryup"] = df["volume"] < (VOL_DRYUP_MULT * avg_volume)
    return df


def add_trend_flag(df):
    df["ma50"]     = ta.sma(df["close"], length=TREND_MA_WINDOW)
    df["trend_ok"] = df["close"] > df["ma50"]
    return df


def add_weekly_trend_flag(df, symbol):
    weekly = yf.Ticker(symbol).history(period=WEEKLY_FETCH_PERIOD, interval="1wk")
    if weekly.empty:
        df["weekly_trend_ok"] = False
        return df

    weekly = weekly.rename(columns=str.lower)
    weekly["ma10w"]           = ta.sma(weekly["close"], length=WEEKLY_MA_WINDOW)
    weekly["weekly_trend_ok"] = weekly["close"] > weekly["ma10w"]

    weekly      = weekly.reset_index().rename(columns={"Date": "Date"})
    daily_dates = df.reset_index().rename(columns={"Date": "Date"})[["Date"]]

    merged = pd.merge_asof(
        daily_dates.sort_values("Date"),
        weekly[["Date", "weekly_trend_ok"]].sort_values("Date"),
        on="Date",
        direction="backward",
    )

    df["weekly_trend_ok"] = merged["weekly_trend_ok"].fillna(False).values
    return df


# Per-ticker pipeline
def analyze_ticker(symbol):
    df = yf.Ticker(symbol).history(period=FETCH_DAYS, interval="1d")
    if df.empty:
        return pd.DataFrame()

    df = df.rename(columns=str.lower)

    df = compute_obv_ad(df)

    df = add_ant_mvp_flag(df)
    df = add_divergence_flag(df)
    df = add_acc_dist_flag(df)
    df = add_vsa_flag(df)
    df = add_rvol_flag(df)

    df = add_vol_dryup_flag(df)
    df = add_trend_flag(df)
    df = add_weekly_trend_flag(df, symbol)

    df["score"] = (
            df["ANT_MVP"].astype(int)
            + df["div_flag"].astype(int)
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


# Main runner
import sys
from datetime import datetime
from pathlib import Path
import time

from market_screeners.model.market_universe import load_market_universe
from market_screeners.model.ticker import Ticker
from market_screeners.service.html_service import capture_output, save_html

DATA_DIR = Path("data")


def _flag_value(flag: str) -> str | None:
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def _load_my_tickers() -> list[str]:
    MY_TICKERS_FILE = Path("my_tickers.txt")
    if not MY_TICKERS_FILE.exists():
        print(
            f"Error: {MY_TICKERS_FILE} not found.\n"
            "Copy my_tickers.example.txt to my_tickers.txt and add your symbols."
        )
        sys.exit(1)
    lines = MY_TICKERS_FILE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _auto_html_path(mode: str) -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(DATA_DIR / f"institution_{mode}_{ts}.html")


def main():
    universe = load_market_universe()
    use_test = "--test" in sys.argv
    use_my = "--my" in sys.argv
    html_path = _flag_value("--export-html")

    if use_test:
        tickers = [universe[symbol] for symbol in sorted(universe)[:10]]
        mode = "test"
        print(f"(Running INSTITUTION scanner in TEST mode with {len(tickers)} tickers)\n")
    elif use_my:
        symbols = _load_my_tickers()
        tickers = [
            universe.get(symbol, Ticker(symbol=symbol, asset_type="unknown"))
            for symbol in symbols
        ]
        mode = "my"
        print(f"(Running INSTITUTION scanner in MY mode with {len(tickers)} tickers)\n")
    else:
        tickers = list(universe.values())
        mode = "full"

    # Always export an HTML to data/ unless the caller already specified a path.
    if html_path is None:
        html_path = _auto_html_path(mode)

    print(f"Fetching {FETCH_DAYS} daily + {WEEKLY_FETCH_PERIOD} weekly OHLCV for {len(tickers)} tickers...")

    all_rows = []
    symbol_list = [t.symbol if isinstance(t, Ticker) else str(t) for t in tickers]
    for symbol in symbol_list:
        df = analyze_ticker(symbol)
        if df.empty:
            continue

        # Trim to recent window — earlier bars were only needed for warm-up
        recent = df.tail(ANALYSIS_DAYS)
        signals = recent[recent["score"] >= MIN_SCORE]
        if not signals.empty:
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

    columns = [
        "Symbol", "Date", "Score", "Context", "ANT MVP", "OBV/AD Div",
        "AccVsDist(25d)", "VSA Event", "RVOL Absorb", "VolDryUp", "Trend(50d)", "WeeklyTrend", "Stock"
    ]

    # Build printable rows as lists of strings
    rows = []
    for _, row in result.iterrows():
        acc_dist_str = f"{int(row.get('acc_count',0))} vs {int(row.get('dist_count',0))}"
        date_val = row.get('Date')
        date_str = date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)
        r = [
            str(row.get('symbol','')),
            date_str,
            str(int(row.get('score',0))) + '/5',
            str(int(row.get('context_score',0))) + '/3',
            'Yes' if row.get('ANT_MVP') else 'No',
            'Yes' if row.get('div_flag') else 'No',
            acc_dist_str,
            str(row.get('vsa_event','')),
            'Yes' if row.get('rvol_flag') else 'No',
            'Yes' if row.get('vol_dryup') else 'No',
            'Yes' if row.get('trend_ok') else 'No',
            'Yes' if row.get('weekly_trend_ok') else 'No',
            str(row.get('symbol',''))  # trailing Stock column for easier viewing
        ]
        rows.append(r)

    def _render_table():
        print()
        title = f"INSTITUTIONAL ACCUMULATION SIGNALS  (min score >= {MIN_SCORE}/5 criteria | context shown as x/3)"
        print("=" * len(title))
        print(title)
        print("=" * len(title))

        # compute column widths
        widths = {}
        for i, col in enumerate(columns):
            max_val = max((len(str(r[i])) for r in rows), default=0)
            widths[col] = max(len(col), max_val)

        sep = "+-" + "-+-".join("-" * widths[c] for c in columns) + "-+"
        header = "| " + " | ".join(c.ljust(widths[c]) for c in columns) + " |"

        print(sep)
        print(header)
        print(sep.replace('-', '-'))

        for r in rows:
            line = "| " + " | ".join(str(v).ljust(widths[columns[i]]) for i, v in enumerate(r)) + " |"
            print(line)

        print(sep)
        print(f"{len(rows)} signal day(s) across {result['symbol'].nunique()}/{len(symbol_list)} tickers")

    start_time = time.perf_counter()
    captured = capture_output(_render_table, echo=True)
    save_html(captured, html_path)

    print(f"Report saved -> {html_path}")
    print(f"Execution time: {time.perf_counter() - start_time:.2f}s")


if __name__ == "__main__":
    main()
