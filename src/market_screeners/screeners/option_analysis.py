"""
option_analysis.py

Quick option-chain "read the mood" scan for a list of US tickers.

WHAT THIS SCRIPT DOES, IN PLAIN ENGLISH
-----------------------------------------
For each ticker, it pulls the current (live) option chain from Yahoo
Finance and works out a handful of numbers that traders use to guess
whether the option market is leaning bullish or bearish for that stock
right now. It doesn't predict anything by itself -- it just measures
lopsidedness between calls and puts in a few different ways, and prints
each measurement in a color (green = bullish lean, red = bearish lean,
yellow = no clear lean) so you can scan the table quickly.

You are meant to run this script twice in a day (e.g. once around
10:15 AM and again around 11:00 AM) and compare the two tables by eye
to see whether the lean is building, fading, or flipping. The script
itself has no memory of past runs -- that comparison is on you.

METRICS COMPUTED (one per column in the printed table):
  - ATM strike        : the strike price closest to the current stock price.
  - Max Call/Put OI    : the strike where the most call/put contracts are
                         open -- often acts like a "wall" price tends to
                         respect during the day.
  - PCR                : Put/Call ratio, using open interest. A rough
                         gauge of whether the crowd is more hedged with
                         puts or more excited with calls.
  - IV SKEW            : compares how expensive out-of-the-money puts are
                         vs out-of-the-money calls, using implied
                         volatility instead of raw price. Strips out the
                         effect of the stock's price level.
  - VOL/OI hotspot     : the near-the-money strike getting unusually high
                         trading volume relative to how many contracts
                         were already open there -- a sign of fresh same-day
                         interest rather than old positions.
  - BMI                : "Balanced Method Indicator" -- an adaptation of
                         the Hindi-language "Taraju Vidhi" (Balance Method)
                         strategy for intraday Nifty/Bank Nifty options,
                         reworked so it works across US stocks at very
                         different price levels. See _compute_bmi() below
                         for the full explanation and source link.
  - MAX PAIN range     : the strike zone where option sellers (option
                         writers) would collectively lose the least money
                         if the stock settled there. Some traders believe
                         price gets pulled toward this zone by expiry.
  - ATR (1Y)           : Average True Range from 1 year of daily bars --
                         a VOLATILITY gauge, not a direction signal. Shows
                         this ticker's typical daily $ move, plus a
                         percentile showing how today's range compares to
                         the past year (e.g. "72%ile" = wider than 72% of
                         the past year's daily ranges). Not colored, since
                         it doesn't lean bullish or bearish either way --
                         it's context for sizing stops and sanity-checking
                         the other columns, not a signal itself.

IMPORTANT CAVEAT ABOUT THE COLOR THRESHOLDS
-----------------------------------------
Every "is this green/red/yellow" cutoff in this file (PCR > 1.2, IV skew
> 1%, BMI > 5%, etc.) is a REASONABLE STARTING GUESS, not a number that
has been statistically tested against real US single-stock data. Some
of them (like the PCR cutoff) are borrowed from conventions used for
INDEX options in other markets, which may not fit individual US stocks
well. Treat the colors as a rough first pass, and adjust the threshold
constants near the top of this file once you've watched the table for a
couple of weeks and have a feel for what "normal" looks like per ticker.
Specific known weak spots are called out as comments at each threshold
below.

Run:
    uv run python -m market_screeners.screeners.option_analysis --my       (personal watch list)
    uv run python -m market_screeners.screeners.option_analysis --test     (first 10 symbols)
    uv run python -m market_screeners.screeners.option_analysis            (full universe)
    uv run python -m market_screeners.screeners.option_analysis --export-html path/to/output.html
"""

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf
import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from market_screeners.model.market_universe import load_market_universe
from market_screeners.model.ticker import Ticker
from market_screeners.service.html_service import capture_output, save_html

# Default tickers for reference (used when running full universe or if not in my/test mode)
DEFAULT_TICKERS = [
    ("TQQQ", 0.5),
    ("QQQ", 1.0),
    ("UPRO", 1.0),
    ("SPY", 1.0),
    ("IBIT", 0.5),
    ("BULL", 0.5),
]

# Data directory for HTML export
DATA_DIR = Path("data")

# Ticker-to-strike-interval mapping for common tickers
STRIKE_INTERVALS = {
    "TQQQ": 0.5,
    "IBIT": 0.5,
    "BULL": 0.5,
}

# Default strike interval for tickers not in the mapping
DEFAULT_STRIKE_INTERVAL = 1.0

# Each entry is (ticker, strike_interval):
#   strike_interval = the real $ gap between consecutive listed strikes
#   for that ticker (e.g. TQQQ lists strikes every $0.50, QQQ/SPY/UPRO
#   every $1.00). You already know these from watching each chain, so
#   supplying them directly is more accurate than the program guessing
#   or approximating a window from % of spot.
#
# This interval is used to build the "near the money" window for IV
# skew and the vol/OI hotspot (see NEAR_MONEY_STRIKE_COUNT below) --
# it converts "N strikes away" into a precise dollar distance using
# each ticker's REAL spacing, instead of assuming every ticker spaces
# strikes the same way.
TICKERS = DEFAULT_TICKERS

# Optional: pin specific tickers to a specific strike instead of
# auto-ATM (closest strike to live spot). Leave empty ({}) to always
# use auto-ATM, which is the accurate, no-guesswork default.
# Example: {"SPY": 560.0} watches the strike nearest $560 for SPY,
# regardless of where spot is when you run the script.
#
# NOTE: pinning a strike does NOT make the reading "more accurate" --
# auto-ATM already finds the true nearest-to-spot strike correctly
# every time. Pinning just changes WHICH strike gets analyzed, in case
# the one you care about isn't the current ATM one.
STRIKE_OVERRIDES: dict[str, float] = {}


# CLI helper functions
def _flag_value(flag: str) -> str | None:
    """Extract the value following a flag in sys.argv."""
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def _load_my_tickers() -> list[str]:
    """Load personal watch list from my_tickers.txt."""
    MY_TICKERS_FILE = Path("my_tickers.txt")
    if not MY_TICKERS_FILE.exists():
        print(
            f"Error: {MY_TICKERS_FILE} not found.\n"
            "Copy my_tickers.example.txt to my_tickers.txt and add your symbols."
        )
        sys.exit(1)
    lines = MY_TICKERS_FILE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _get_strike_interval(ticker: str) -> float:
    """Get the strike interval for a ticker."""
    return STRIKE_INTERVALS.get(ticker, DEFAULT_STRIKE_INTERVAL)


def _auto_html_path(mode: str) -> str:
    """Generate automatic HTML export path with timestamp."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(DATA_DIR / f"option_analysis_{mode}_{ts}.html")

# How many REAL listed strikes above/below the reference strike count
# as "near the money" for IV skew and the vol/OI hotspot. Combined with
# each ticker's strike_interval above, this gives an exact dollar
# window per ticker:
#     window ($) = NEAR_MONEY_STRIKE_COUNT * strike_interval
# Example: TQQQ (interval $0.50) at count 5 -> a $2.50 window each side.
#          SPY  (interval $1.00) at count 5 -> a $5.00 window each side.
# This replaces the earlier percent-of-spot approximation now that we
# have the ticker's actual strike spacing instead of having to guess it.
NEAR_MONEY_STRIKE_COUNT = 5

# BMI (Balanced Method Indicator) -- adapted "Taraju Vidhi".
# Source: Mahesh Chander Kaushik, "Intraday व Option Trading के लिए तराजू विधि"
# https://www.youtube.com/watch?v=KwBs-ASbKSU
#
# Normalized ATM premium skew: (call_mid - put_mid) / (call_mid + put_mid) * 100.
# A reading beyond +/- this threshold (in %) is treated as a directional lean.
#
# CAVEAT: this 5.0% cutoff is an untested starting guess, same as the
# other thresholds in this file -- not fit to historical BMI readings.
BMI_THRESHOLD_PCT = 5.0

# ATR (Average True Range) -- a volatility gauge, not a direction
# signal. It tells you the stock's TYPICAL daily range over the lookback
# period, so you can sanity-check whether today's option-chain reading
# lines up with a normal-sized move or an unusually large one for this
# specific ticker.
#
# We fetch ATR_LOOKBACK_PERIOD of DAILY bars and compute a 14-period
# ATR from them (14 is the standard/default length for ATR). Using a
# full year of daily history doesn't change today's ATR value much by
# itself (ATR(14) only really "looks back" 14 bars), but it DOES let
# us rank today's ATR against the past year and say how typical
# today's range is for this ticker -- that's what the % after the ATR
# value in the table means (e.g. "72%" = today's ATR is higher than
# 72% of daily ATR readings over the past year for this ticker).
ATR_LOOKBACK_PERIOD = "1y"
ATR_LENGTH = 14

# How many months ahead to scan when looking for the single highest-OI
# call strike and highest-OI put strike ACROSS ALL expiries (not just
# the nearest one). This is a separate, heavier pass -- it fetches the
# full chain for every expiry out to this many months, so it's slower
# than the rest of the scan.
MAX_OI_SCAN_MONTHS = 6


# ---------------------------------------------------------------------
# DATA CONTAINER
# ---------------------------------------------------------------------
@dataclass
class OptionSnapshot:
    """
    Plain data holder for everything we compute about one ticker.
    One of these gets created per ticker, filled in by
    OptionChainAnalyzer._analyze_ticker(), and then handed to
    print_table() to render as one row.
    """
    ticker: str
    spot: Optional[float] = None
    atm_strike: Optional[float] = None
    max_call_oi_strike: Optional[float] = None
    max_put_oi_strike: Optional[float] = None
    pcr: Optional[float] = None
    iv_skew_pct: Optional[float] = None      # + means puts richer, - means calls richer
    max_pain_low: Optional[float] = None
    max_pain_high: Optional[float] = None
    hotspot_strike: Optional[float] = None
    hotspot_side: Optional[str] = None       # "C" | "P" | None
    hotspot_ratio: Optional[float] = None    # volume / openInterest at that strike
    bmi_pct: Optional[float] = None          # normalized ATM premium skew, (C-P)/(C+P) * 100
    strike_is_override: bool = False         # True if the strike was pinned by the user, not auto-ATM
    atr: Optional[float] = None              # 14-period ATR ($) from 1 year of daily bars
    atr_percentile: Optional[float] = None   # where today's ATR ranks vs the past year, 0-100
    # Highest-OI call/put strike found by scanning EVERY expiry out to
    # MAX_OI_SCAN_MONTHS (not just the nearest expiry like max_call_oi_strike
    # / max_put_oi_strike above). Each is (strike, open_interest, expiry_date_str).
    max_oi_call_6mo: Optional[tuple[float, int, str]] = None
    max_oi_put_6mo: Optional[tuple[float, int, str]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------
# ANALYZER
# ---------------------------------------------------------------------
class OptionChainAnalyzer:
    """
    Downloads option chain data for a list of tickers and computes the
    metrics described in the module docstring above. Two kinds of
    methods live here:

      - "_compute_*" methods: pure number-crunching. Given the raw
        calls/puts tables from yfinance, they return a metric. No
        printing, no color logic -- just math.

      - "classify_*" methods: turn a computed metric into a color
        ("green" / "red" / "yellow") using a threshold. This is where
        all the "is this bullish or bearish" judgment calls live, kept
        separate from the math so the thresholds are easy to find and
        tune later.
    """

    def __init__(self, tickers: list[tuple[str, float]]):
        self.tickers = tickers
        self.snapshots: list[OptionSnapshot] = []

    def run(self) -> None:
        """Analyze every configured ticker and store the results,
        sorted alphabetically so the printed table is easy to scan.

        Each entry in self.tickers is (ticker, strike_interval) -- see
        the TICKERS comment in CONFIG above. Any strike pin for that
        ticker is looked up separately from STRIKE_OVERRIDES.
        """
        for ticker, strike_interval in self.tickers:
            strike_override = STRIKE_OVERRIDES.get(ticker)
            self.snapshots.append(
                self._analyze_ticker(ticker, strike_interval, strike_override)
            )
        self.snapshots.sort(key=lambda s: s.ticker)

    def _analyze_ticker(
            self, ticker: str, strike_interval: float, strike_override: Optional[float] = None
    ) -> OptionSnapshot:
        """
        Does the actual work for ONE ticker:
          1. Get the current stock price.
          2. Pull the nearest option expiry's full chain (all strikes,
             calls and puts).
          3. Pick the strike to analyze: the true ATM strike (closest
             to spot) by default, or the strike closest to
             strike_override if one was given for this ticker.
          4. Run every metric calculation against that chain, centered
             on the chosen strike, using strike_interval to build an
             exact-dollar "near the money" window (see
             NEAR_MONEY_STRIKE_COUNT in CONFIG).
        If anything goes wrong (bad ticker, no options listed, network
        hiccup, etc.) the error is captured on the snapshot instead of
        crashing the whole scan, so one bad ticker doesn't stop the
        other nine from printing.
        """
        snap = OptionSnapshot(ticker=ticker)
        try:
            tk = yf.Ticker(ticker)

            # Current stock price. fast_info is quick; fall back to the
            # last daily close if fast_info doesn't have it for some reason.
            spot = tk.fast_info.get("lastPrice") or tk.history(period="1d")["Close"].iloc[-1]
            snap.spot = round(float(spot), 2)

            # Use the NEAREST expiration available (front week, or front
            # month if the stock has no weeklies). Nearest expiry is the
            # most sensitive to today's intraday sentiment.
            expirations = tk.options
            if not expirations:
                snap.error = "No option"
                return snap
            expiry = expirations[0]

            chain = tk.option_chain(expiry)
            calls, puts = chain.calls, chain.puts

            # Reference strike for this ticker: normally the ATM strike
            # (closest listed strike to live spot). If strike_override
            # was given, use the strike closest to THAT value instead --
            # e.g. a specific strike you already hold or are watching.
            target_price = strike_override if strike_override is not None else snap.spot
            snap.atm_strike = float(
                calls.iloc[(calls["strike"] - target_price).abs().argsort()[:1]]["strike"].values[0]
            )
            snap.strike_is_override = strike_override is not None

            # Exact-dollar "near the money" window for this specific
            # ticker: N real listed strikes each side, using its actual
            # strike spacing (strike_interval) rather than a guess.
            near_money_window = NEAR_MONEY_STRIKE_COUNT * strike_interval

            # "Walls": the strike with the single largest open interest
            # (number of contracts still open) on each side. Large call
            # OI above spot, or large put OI below spot, can act like
            # resistance/support because option sellers there have an
            # incentive to defend that price into expiry.
            snap.max_call_oi_strike = float(calls.loc[calls["openInterest"].idxmax(), "strike"])
            snap.max_put_oi_strike = float(puts.loc[puts["openInterest"].idxmax(), "strike"])

            # PCR = Put/Call Ratio, using total open interest on each side:
            #   PCR = (sum of all put OI) / (sum of all call OI)
            # PCR > 1 means there are more open put contracts than call
            # contracts -- traditionally read as more hedging/bearish
            # positioning (or, contrarian-style, "too much fear" = bullish).
            # PCR < 1 means more call contracts open, i.e. more upside bets.
            total_call_oi = calls["openInterest"].sum()
            total_put_oi = puts["openInterest"].sum()
            snap.pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else None

            # IV skew: see _compute_iv_skew() below for the full explanation.
            snap.iv_skew_pct = self._compute_iv_skew(calls, puts, snap.spot, near_money_window)

            # Max Pain: see _compute_max_pain() below for the full explanation.
            snap.max_pain_low, snap.max_pain_high = self._compute_max_pain(calls, puts)

            # Vol/OI hotspot: see _compute_hotspot() below for the full explanation.
            snap.hotspot_strike, snap.hotspot_side, snap.hotspot_ratio = self._compute_hotspot(
                calls, puts, snap.atm_strike, near_money_window
            )

            # BMI: see _compute_bmi() below for the full explanation.
            snap.bmi_pct = self._compute_bmi(calls, puts, snap.atm_strike)

            # ATR: see _compute_atr() below for the full explanation.
            # This is a SEPARATE fetch from the option chain above --
            # it pulls 1 year of daily stock price bars (not options
            # data) to measure this ticker's typical daily range.
            daily_bars = tk.history(period=ATR_LOOKBACK_PERIOD, interval="1d")
            snap.atr, snap.atr_percentile = self._compute_atr(daily_bars)

            # Max OI across ALL expiries out to MAX_OI_SCAN_MONTHS: see
            # _scan_max_oi_across_expiries() below. This re-fetches every
            # expiry's chain (separate from the "nearest expiry" chain
            # pulled above), so it's the slowest part of the scan.
            snap.max_oi_call_6mo, snap.max_oi_put_6mo = self._scan_max_oi_across_expiries(
                tk, expirations
            )

        except Exception as e:
            # Anything unexpected (bad ticker symbol, yfinance hiccup,
            # missing data) lands here instead of crashing the whole run.
            snap.error = str(e)

        return snap

    @staticmethod
    def _scan_max_oi_across_expiries(
            tk: "yf.Ticker", expirations: tuple[str, ...]
    ) -> tuple[Optional[tuple[float, int, str]], Optional[tuple[float, int, str]]]:
        """
        Scans EVERY listed expiry out to MAX_OI_SCAN_MONTHS months ahead
        and finds the single highest-OI call strike and highest-OI put
        strike across the whole set -- i.e. "of everything listed over
        the next 6 months, where is the single biggest open-interest
        wall, on each side, and which expiry is it on."

        This is a different question from max_call_oi_strike /
        max_put_oi_strike above, which only look at the NEAREST expiry.
        A strike 3 months out with huge OI (e.g. a LEAPS-style level)
        won't show up in those nearest-expiry fields, but will show up
        here.

        Returns ((call_strike, call_oi, call_expiry), (put_strike, put_oi, put_expiry)),
        with either side (or both) as None if no data was found (e.g.
        ticker has no listed expiries within the window, or a request
        failed for every expiry).

        NOTE: this issues one network request per expiry (via
        tk.option_chain(expiry)), so a ticker with many weekly expiries
        listed 6 months out means many requests -- this is the slowest
        part of the whole scan, and the most likely place to hit
        Yahoo's rate limiting if you run this often.
        """
        cutoff = datetime.today() + timedelta(days=30 * MAX_OI_SCAN_MONTHS)
        expiries_in_range = [
            e for e in expirations
            if datetime.strptime(e, "%Y-%m-%d") <= cutoff
        ]

        best_call: Optional[tuple[float, int, str]] = None  # (strike, OI, expiry)
        best_put: Optional[tuple[float, int, str]] = None

        for expiry in expiries_in_range:
            try:
                chain = tk.option_chain(expiry)
            except Exception:
                # One bad/rate-limited expiry shouldn't kill the whole
                # scan for this ticker -- skip it and keep going.
                continue

            calls, puts = chain.calls, chain.puts

            if not calls.empty and calls["openInterest"].notna().any():
                row = calls.loc[calls["openInterest"].idxmax()]
                oi = int(row["openInterest"])
                if best_call is None or oi > best_call[1]:
                    best_call = (float(row["strike"]), oi, expiry)

            if not puts.empty and puts["openInterest"].notna().any():
                row = puts.loc[puts["openInterest"].idxmax()]
                oi = int(row["openInterest"])
                if best_put is None or oi > best_put[1]:
                    best_put = (float(row["strike"]), oi, expiry)

        return best_call, best_put

    @staticmethod
    def _compute_iv_skew(calls, puts, spot: float, near_money_window: float) -> Optional[float]:
        """
        IV SKEW -- are out-of-the-money puts more "expensive" than
        out-of-the-money calls, after adjusting for the stock's price?

        Raw option prices aren't directly comparable across stocks
        (a $5 option means something different on a $50 stock than a
        $500 stock). Implied Volatility (IV) fixes that -- it's the
        market's estimate of how much the stock will swing, expressed
        as a percentage, so it's already normalized.

        Steps:
          1. Take all out-of-the-money (OTM) calls (strikes ABOVE spot)
             and OTM puts (strikes BELOW spot) that fall within
             near_money_window dollars of spot. near_money_window is
             computed by the caller as NEAR_MONEY_STRIKE_COUNT * this
             ticker's real strike_interval -- e.g. QQQ (interval $1.00,
             count 5) looks $5.00 either side of spot.
          2. Average the IV on each side.
          3. Express the put side relative to the call side:
                 iv_skew_pct = (avg_put_IV - avg_call_IV) / avg_call_IV * 100

        A positive number means puts are pricing in more expected
        movement than calls (puts "richer"). A negative number means
        calls are richer.

        CAVEAT (see classify_iv_skew below): US stocks almost always
        show some natural positive put skew -- it's a structural
        feature of equity options (downside moves are historically
        sharper than upside ones, so puts carry a standing premium),
        not a fresh bullish/bearish signal by itself. A small skew
        reading here is normal background noise, not news.
        """
        otm_calls = calls[(calls["strike"] > spot) & (calls["strike"] <= spot + near_money_window)]
        otm_puts = puts[(puts["strike"] < spot) & (puts["strike"] >= spot - near_money_window)]
        if otm_calls.empty or otm_puts.empty:
            return None
        # .mean() already ignores individual NaN rows by default, which is
        # correct -- but if EVERY row on one side is NaN (no IV data at
        # all in that window), the mean itself comes back NaN. Catch that
        # explicitly so we report "no data" (None) instead of letting a
        # NaN silently pass the "== 0" check below and print as a
        # fake-looking number.
        call_iv = otm_calls["impliedVolatility"].mean()
        put_iv = otm_puts["impliedVolatility"].mean()
        if pd.isna(call_iv) or pd.isna(put_iv) or call_iv == 0:
            return None
        return round((put_iv - call_iv) / call_iv * 100, 1)

    @staticmethod
    def _compute_bmi(calls, puts, atm_strike: float) -> Optional[float]:
        """
        BMI (Balanced Method Indicator) -- adapted Taraju Vidhi ("Balance
        Method") for US single stocks.
        Source: Mahesh Chander Kaushik, "Intraday व Option Trading के लिए तराजू विधि"
        https://www.youtube.com/watch?v=KwBs-ASbKSU

        THE ORIGINAL IDEA (Indian index options, e.g. Nifty):
        Around 30 minutes after the open, compare the ATM call premium
        to the ATM put premium at the SAME strike. If one side is
        pricing noticeably higher than the other (the video used fixed
        point gaps: 25 points for Nifty, 50 for Bank Nifty, 25 for
        FinNifty), the market is expected to drift toward the richer
        side -- e.g. if calls are much pricier than puts, expect upside.

        WHY WE CAN'T COPY THE POINT GAPS DIRECTLY:
        A fixed "25 points" only makes sense because Nifty/Bank Nifty
        always trade around a similar price level and tick size. US
        stocks range from single digits to thousands of dollars, so the
        same 25-point gap would be huge for a cheap stock and
        meaningless for an expensive one. Instead we use a RATIO, which
        automatically scales with the stock's price and typical premium
        size:

            BMI (%) = (call_mid - put_mid) / (call_mid + put_mid) * 100

        call_mid + put_mid is the ATM straddle price -- roughly what
        the market expects the stock could move by. Dividing by that
        turns the raw dollar gap into "what fraction of the expected
        move is skewed toward one side," which IS comparable across
        stocks.

        We use the bid/ask midpoint, (bid + ask) / 2, as "premium"
        rather than the lastPrice column, because lastPrice can be a
        stale trade from minutes/hours ago on a less-active strike,
        while bid/ask reflects where the market is willing to trade
        RIGHT NOW.

        Reading it:
          Positive BMI -> ATM calls richer than puts -> bullish lean.
          Negative BMI -> ATM puts richer than calls -> bearish lean.
        """
        call_row = calls[calls["strike"] == atm_strike]
        put_row = puts[puts["strike"] == atm_strike]
        if call_row.empty or put_row.empty:
            return None

        call_row = call_row.iloc[0]
        put_row = put_row.iloc[0]

        call_mid = (call_row["bid"] + call_row["ask"]) / 2
        put_mid = (put_row["bid"] + put_row["ask"]) / 2

        # Fall back to lastPrice if bid/ask don't give us a usable
        # number -- either genuinely 0 (no quotes posted) OR NaN, which
        # yfinance also returns for illiquid strikes. Checking only
        # "== 0" misses the NaN case (NaN == 0 is False in Python/pandas),
        # which would silently let a NaN premium flow all the way through
        # to a NaN BMI reading -- shown as a real-looking number instead
        # of correctly reporting "no data" for that strike.
        if pd.isna(call_mid) or call_mid == 0:
            call_mid = call_row["lastPrice"]
        if pd.isna(put_mid) or put_mid == 0:
            put_mid = put_row["lastPrice"]

        # If even the lastPrice fallback is missing or zero, we genuinely
        # have no usable premium for this strike -- report "no data"
        # (None) rather than silently computing a meaningless ratio.
        if pd.isna(call_mid) or pd.isna(put_mid):
            return None

        denom = call_mid + put_mid
        if denom == 0:
            return None

        return round((call_mid - put_mid) / denom * 100, 1)

    @staticmethod
    def _compute_atr(daily_bars) -> tuple[Optional[float], Optional[float]]:
        """
        ATR (Average True Range) -- a volatility gauge, NOT a
        directional signal. It answers "how much does this stock
        typically move in a day," in dollars, regardless of which way.

        For each daily bar, "True Range" is the LARGEST of:
          1. today's high - today's low
          2. |today's high - yesterday's close|
          3. |today's low  - yesterday's close|
        Using the largest of the three (not just high-low) matters
        because it also captures overnight gaps -- if the stock gapped
        up or down between yesterday's close and today's open, plain
        high-low would understate how far it actually moved.

        ATR is then a smoothed rolling average of True Range over
        ATR_LENGTH periods (14, the industry-standard default set by
        Welles Wilder, who invented ATR in 1978). We compute it here
        with plain pandas instead of the pandas_ta library -- pandas_ta
        pulls in numba as a dependency, which frequently fails to
        install on Windows / newer Python versions due to numpy version
        conflicts (exactly the error you hit). ATR's formula is simple
        enough that we don't need an extra library for it.

        Specifically we use an exponentially-weighted moving average
        with alpha = 1/ATR_LENGTH, which is mathematically Wilder's
        original smoothing method (the same one pandas_ta uses by
        default internally) -- so this produces the same standard ATR
        values you'd see in any charting platform.

        We also report atr_percentile: where TODAY's ATR ranks against
        every ATR reading in the lookback period, from 0 (lowest range
        in the period) to 100 (highest). This turns a bare dollar
        number ("ATR is $4.20") into context ("today's range is
        typical" vs "today's range is unusually wide for this ticker").

        Returns (atr_dollars, atr_percentile) or (None, None) if there
        wasn't enough history to compute it.
        """
        if daily_bars is None or daily_bars.empty or len(daily_bars) < ATR_LENGTH + 1:
            return None, None

        high = daily_bars["High"]
        low = daily_bars["Low"]
        close = daily_bars["Close"]
        prev_close = close.shift(1)

        true_range = pd.concat(
            [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
            axis=1,
        ).max(axis=1)

        # Wilder's smoothing = an exponentially-weighted moving average
        # with alpha = 1/length. min_periods=ATR_LENGTH means the first
        # ATR_LENGTH-1 bars come back as NaN (not enough data yet to
        # smooth), matching how pandas_ta and every standard charting
        # platform handle the warm-up period.
        atr_series = true_range.ewm(alpha=1 / ATR_LENGTH, adjust=False, min_periods=ATR_LENGTH).mean()

        valid_atr = atr_series.dropna()
        if valid_atr.empty:
            return None, None

        current_atr = atr_series.iloc[-1]
        if pd.isna(current_atr):
            return None, None

        # Percentile rank of today's ATR against the full ATR history
        # we have available (up to ~1 year, minus the first ATR_LENGTH
        # bars needed to warm up the rolling average).
        percentile = (valid_atr < current_atr).mean() * 100

        return round(float(current_atr), 2), round(float(percentile), 0)

    @staticmethod
    def _compute_max_pain(calls, puts):
        """
        MAX PAIN -- the strike price where, if the stock settled there
        at expiry, option WRITERS (the people who sold the options)
        would collectively owe the least money to option buyers.

        Some traders believe price tends to drift toward this zone as
        expiry approaches, on the theory that large option sellers have
        an incentive to nudge things that way. It's a debated idea, not
        a law of markets -- treat it as one more data point, not gospel.

        How it's calculated:
          For every possible strike price S, add up:
            - how much money call buyers WOULD be owed if the stock
              settled at S: max(S - call_strike, 0) * call_open_interest,
              summed across all call strikes
            - how much money put buyers WOULD be owed if the stock
              settled at S: max(put_strike - S, 0) * put_open_interest,
              summed across all put strikes
          Add those two totals together -> that's the "pain" writers
          would feel if the stock settled at S. The strike S with the
          SMALLEST total pain is the max pain point.

        We return a small range (one strike below, one strike above the
        exact max-pain strike) rather than a single number, since the
        exact strike is a bit arbitrary and a small range is easier to
        eyeball against the current spot price.
        """
        strikes = sorted(set(calls["strike"]).union(puts["strike"]))
        pain = {}
        for s in strikes:
            call_loss = ((s - calls["strike"]).clip(lower=0) * calls["openInterest"]).sum()
            put_loss = ((puts["strike"] - s).clip(lower=0) * puts["openInterest"]).sum()
            pain[s] = call_loss + put_loss
        if not pain:
            return None, None
        min_pain_strike = min(pain, key=pain.get)
        # Give a small range around the exact max pain strike for readability.
        idx = strikes.index(min_pain_strike)
        low = strikes[max(idx - 1, 0)]
        high = strikes[min(idx + 1, len(strikes) - 1)]
        return low, high

    @staticmethod
    def _compute_hotspot(calls, puts, atm_strike: float, near_money_window: float):
        """
        VOL/OI HOTSPOT -- which near-the-money strike is getting
        unusually heavy trading TODAY, relative to how many contracts
        were already sitting open there BEFORE today.

        For every strike within near_money_window dollars of the
        reference strike (auto-ATM, or the pinned strike if one was
        set for this ticker), we compute:

            vol_oi_ratio = today's volume / existing open interest

        near_money_window is computed by the caller as
        NEAR_MONEY_STRIKE_COUNT * this ticker's real strike_interval,
        so it's an exact dollar range built from the ticker's actual
        listed strike spacing rather than a guess.

        A ratio above 1.0x means MORE contracts traded today than were
        open at the start of the day at that strike -- a sign of fresh,
        active positioning rather than old, static positions just
        sitting there. We report whichever near-the-money strike (call
        or put side) has the single highest ratio, as long as it clears
        the 1.0x bar; otherwise there's no clear hotspot and we return
        nothing.

        Returns a tuple: (strike, "C" or "P", ratio) or (None, None, None).
        """
        near_calls = calls[(calls["strike"] - atm_strike).abs() <= near_money_window].copy()
        near_puts = puts[(puts["strike"] - atm_strike).abs() <= near_money_window].copy()

        # .replace(0, 1) avoids divide-by-zero for strikes with no prior
        # open interest; if OI is 0 we just use volume/1 as the ratio.
        near_calls["vol_oi"] = near_calls["volume"] / near_calls["openInterest"].replace(0, 1)
        near_puts["vol_oi"] = near_puts["volume"] / near_puts["openInterest"].replace(0, 1)

        best_call = near_calls.loc[near_calls["vol_oi"].idxmax()] if not near_calls.empty else None
        best_put = near_puts.loc[near_puts["vol_oi"].idxmax()] if not near_puts.empty else None

        candidates = []
        if best_call is not None and best_call["vol_oi"] > 1:
            candidates.append((best_call["vol_oi"], best_call["strike"], "C"))
        if best_put is not None and best_put["vol_oi"] > 1:
            candidates.append((best_put["vol_oi"], best_put["strike"], "P"))

        if not candidates:
            return None, None, None
        candidates.sort(reverse=True)
        ratio, strike, side = candidates[0]
        return float(strike), side, float(ratio)

    # -------------------------------------------------------------
    # CLASSIFIERS -- turn a computed number into a green/red/yellow
    # color for the table. This is the ONLY place threshold values
    # live, so tune them here (not in the _compute_* methods above).
    # -------------------------------------------------------------

    @staticmethod
    def classify_pcr(pcr: Optional[float]) -> str:
        """
        green = bullish tilt (relatively more call OI open),
        red   = bearish tilt (relatively more put OI open),
        yellow = neither extreme, treated as neutral.

        CAVEAT: 1.2 / 0.8 is the common cutoff used for INDEX options
        (Nifty-style). It has not been checked against what's "normal"
        PCR for these specific US stocks -- some names naturally run
        put-heavy (institutional hedging) or call-heavy (momentum
        names) even on an ordinary day. Watch this column for a while
        per-ticker before trusting the color.
        """
        if pcr is None:
            return "yellow"
        if pcr > 1.2:
            return "green"
        if pcr < 0.8:
            return "red"
        return "yellow"

    @staticmethod
    def classify_bmi(bmi_pct: Optional[float]) -> str:
        """
        green = ATM calls richer than puts (bullish lean),
        red   = ATM puts richer than calls (bearish lean),
        yellow = within the "no clear lean" band.

        CAVEAT: BMI_THRESHOLD_PCT (5.0%) is an untested starting guess,
        same as the other thresholds in this file.
        """
        if bmi_pct is None:
            return "yellow"
        if bmi_pct > BMI_THRESHOLD_PCT:
            return "green"
        if bmi_pct < -BMI_THRESHOLD_PCT:
            return "red"
        return "yellow"

    @staticmethod
    def classify_iv_skew(iv_skew_pct: Optional[float]) -> str:
        """
        green = puts pricing in more movement than calls (read here as
                a bullish hedging tilt -- heavy put buying for
                protection often means people are also holding/adding
                upside exposure),
        red   = calls pricing in more movement than puts (bearish lean),
        yellow = inside the neutral band.

        CAVEAT: US equity options almost ALWAYS show some natural
        positive put skew -- it's priced in structurally, not a fresh
        signal (see the note in _compute_iv_skew above). A 1% band is
        quite tight given that background skew, so this column may
        read "green" more often than it's telling you anything new.
        Worth watching against a baseline per ticker before trusting it.
        """
        if iv_skew_pct is None:
            return "yellow"
        if iv_skew_pct > 1.0:
            return "green"
        if iv_skew_pct < -1.0:
            return "red"
        return "yellow"

    @staticmethod
    def classify_hotspot(side: Optional[str]) -> str:
        """
        green = today's unusual volume is concentrated on the PUT side
                near the money (read here as a bullish tilt -- often
                protective buying rather than outright bearish betting),
        red   = today's unusual volume is concentrated on the CALL side
                (bearish lean, mirroring the put-side read above),
        yellow = no strike cleared the 1.0x volume/OI bar.
        """
        if side == "P":
            return "green"
        if side == "C":
            return "red"
        return "yellow"

    @staticmethod
    def classify_spot_vs_max_pain(
            spot: Optional[float], low: Optional[float], high: Optional[float]
    ) -> str:
        """
        Colors the SPOT price cell based on where it sits relative to
        the max pain range computed above.

        Idea: price tends to gravitate toward max pain by expiry, so:
          green  = spot is BELOW the max pain range -> theoretically
                   room to drift UP toward it (long-ish bias)
          red    = spot is ABOVE the max pain range -> theoretically
                   room to drift DOWN toward it (short-ish bias)
          yellow = spot is already inside the max pain range (neutral)
        """
        if spot is None or low is None or high is None:
            return "yellow"
        if spot < low:
            return "green"
        if spot > high:
            return "red"
        return "yellow"


# ---------------------------------------------------------------------
# PRINTER
# ---------------------------------------------------------------------
def print_table(snapshots: list[OptionSnapshot]) -> None:
    """
    Renders one row per ticker in a single wide table (back to the
    original layout, per user preference over the stacked-card
    version). To keep the table narrow enough to avoid terminal
    wrapping:
      - Every header is broken across 2 lines (sometimes 3) so each
        column is only as wide as its longest WORD, not its full label.
      - The two 6mo-scan cells are compacted: OI uses "k" notation
        (2,638 -> "2.6k") and the expiry date drops to 2-digit year
        (2026-08-21 -> "21-08-2026"), both via _compact_oi_label().
    Coloring logic is unchanged from before.
    """
    console = Console(force_terminal=True, color_system="standard", width=200)
    table = Table(
        show_header=True,
        header_style="bold",
        show_lines=True,
        box=box.ASCII2,
    )

    table.add_column("TICKER", justify="left")
    table.add_column("SPOT\n($)", justify="left")
    table.add_column("STRIKE\n(ATM)", justify="left")
    table.add_column("MAX C/P\n(near)", justify="left")
    table.add_column("PCR", justify="left")
    table.add_column("IV\nSKEW", justify="left")
    table.add_column("VOL/OI\nHOT", justify="left")
    table.add_column("BMI", justify="left")
    table.add_column("MAX\nPAIN", justify="left")
    table.add_column("ATR\n(1Y)", justify="left")
    table.add_column("CALL MAX\n(6mo)", justify="left")
    table.add_column("PUT MAX\n(6mo)", justify="left")

    color = {"green": "green", "red": "red", "yellow": "yellow"}

    for s in snapshots:
        if s.error:
            table.add_row(f"{s.ticker} !", "-", "-", f"err: {s.error}", "-", "-", "-", "-", "-", "-", "-", "-")
            continue

        # Spot price cell is colored based on where it sits vs the max
        # pain range (see classify_spot_vs_max_pain).
        spot_cell = Text(f"{s.spot:.2f}" if s.spot is not None else "-")
        spot_cell.stylize(
            color[OptionChainAnalyzer.classify_spot_vs_max_pain(s.spot, s.max_pain_low, s.max_pain_high)]
        )

        pcr_cell = Text(f"{s.pcr:.2f}" if s.pcr is not None else "-")
        pcr_cell.stylize(color[OptionChainAnalyzer.classify_pcr(s.pcr)])

        iv_cell = Text(f"{s.iv_skew_pct:+.1f}%" if s.iv_skew_pct is not None else "-")
        iv_cell.stylize(color[OptionChainAnalyzer.classify_iv_skew(s.iv_skew_pct)])

        vol_oi_label = (
            f"${s.hotspot_strike:g} {s.hotspot_side} {s.hotspot_ratio:.1f}x" if s.hotspot_side else "-"
        )
        vol_oi_cell = Text(vol_oi_label)
        vol_oi_cell.stylize(color[OptionChainAnalyzer.classify_hotspot(s.hotspot_side)])

        call_put_wall = f"{s.max_call_oi_strike:g}/{s.max_put_oi_strike:g}"

        bmi_cell = Text(f"{s.bmi_pct:+.1f}%" if s.bmi_pct is not None else "-")
        bmi_cell.stylize(color[OptionChainAnalyzer.classify_bmi(s.bmi_pct)])

        strike_label = f"{s.atm_strike:g}*" if s.strike_is_override else f"{s.atm_strike:g}"

        call_max_6mo_label = _compact_oi_label(s.max_oi_call_6mo)
        put_max_6mo_label = _compact_oi_label(s.max_oi_put_6mo)

        # ATR isn't a bullish/bearish lean like the other columns -- it's
        # a volatility gauge -- so it's shown plain, uncolored, unlike
        # PCR/IV/BMI/hotspot above.
        atr_label = (
            f"${s.atr:.2f}\n({s.atr_percentile:.0f}%ile)"
            if s.atr is not None and s.atr_percentile is not None
            else "-"
        )

        table.add_row(
            s.ticker,
            spot_cell,
            strike_label,
            call_put_wall,
            pcr_cell,
            iv_cell,
            vol_oi_cell,
            bmi_cell,
            f"{s.max_pain_low:g}-\n{s.max_pain_high:g}" if s.max_pain_low is not None else "-",
            atr_label,
            call_max_6mo_label,
            put_max_6mo_label,
        )

    console.print(table)


def _compact_oi_label(entry: Optional[tuple[float, int, str]]) -> str:
    """
    Formats a (strike, OI, expiry) tuple from _scan_max_oi_across_expiries()
    into a narrow 2-line cell: "$STRIKE  OIk" on top, expiry (dd-MM-yyyy)
    below. Compacting OI to "k" notation is what lets these two columns
    fit in a wide table without blowing out its total width -- see
    print_table() docstring.
    """
    if entry is None:
        return "-"
    strike, oi, expiry = entry
    oi_label = f"{oi / 1000:.1f}k" if oi >= 1000 else str(oi)
    # expiry comes in as "YYYY-MM-DD" from yfinance; reformat to dd-MM-yyyy.
    try:
        expiry_label = datetime.strptime(expiry, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        expiry_label = expiry
    return f"${strike:g} {oi_label} OI\n{expiry_label}"


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
def main():
    """Main entry point with CLI argument handling."""
    import time

    # Determine tickers source
    universe = load_market_universe()
    use_test = "--test" in sys.argv
    use_my = "--my" in sys.argv
    html_path = _flag_value("--export-html")

    if use_test:
        # Use first 10 tickers from universe
        symbols = sorted(universe.keys())[:10]
        mode = "test"
        print(f"(Running OPTION ANALYSIS in TEST mode with {len(symbols)} tickers)\n")
    elif use_my:
        # Load from personal watch list
        symbols = _load_my_tickers()
        mode = "my"
        print(f"(Running OPTION ANALYSIS in MY mode with {len(symbols)} tickers)\n")
    else:
        # Use full universe
        symbols = sorted(universe.keys())
        mode = "full"

    # Build ticker list with strike intervals
    tickers = [(symbol, _get_strike_interval(symbol)) for symbol in symbols]

    # Generate HTML path if not specified
    if html_path is None:
        html_path = _auto_html_path(mode)

    print(f"Fetching option chain data for {len(tickers)} tickers...\n")

    # Run the analyzer
    analyzer = OptionChainAnalyzer(tickers)
    analyzer.run()

    # Render table (with capture for HTML export)
    def _render():
        print_table(analyzer.snapshots)

    start_time = time.perf_counter()
    captured = capture_output(_render, echo=True)
    save_html(captured, html_path)

    print(f"\nReport saved -> {html_path}")
    elapsed = time.perf_counter() - start_time
    print(f"Execution time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()