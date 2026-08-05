"""
option_analysis.py

Quick 11 AM option-chain scan for a list of US tickers.
Computes: ATM strike, Call/Put OI walls, PCR, IV skew,
Max Pain range, and a Vol/OI hotspot ratio -- then prints a
color-coded table using `rich`.

Run:
    uv run python src/market_screeners/option_analysis.py
"""

from dataclasses import dataclass
from typing import Optional

import yfinance as yf
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
TICKERS = ["AAPL", "META", "NVDA", "MSFT", "IBIT", "NFLX", "ORCL", "BULL"]

# How many strikes above/below spot to consider "near the money"
# when computing IV skew and the vol/OI hotspot.
NEAR_STRIKE_WINDOW = 5


# ---------------------------------------------------------------------
# DATA CONTAINER
# ---------------------------------------------------------------------
@dataclass
class OptionSnapshot:
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
    signal: str = "yellow"                   # "green" | "red" | "yellow"
    error: Optional[str] = None


# ---------------------------------------------------------------------
# ANALYZER
# ---------------------------------------------------------------------
class OptionChainAnalyzer:
    def __init__(self, tickers: list[str]):
        self.tickers = tickers
        self.snapshots: list[OptionSnapshot] = []

    def run(self) -> None:
        for tk in self.tickers:
            self.snapshots.append(self._analyze_ticker(tk))

    def _analyze_ticker(self, ticker: str) -> OptionSnapshot:
        snap = OptionSnapshot(ticker=ticker)
        try:
            tk = yf.Ticker(ticker)

            # Spot price
            spot = tk.fast_info.get("lastPrice") or tk.history(period="1d")["Close"].iloc[-1]
            snap.spot = round(float(spot), 2)

            # Nearest expiration (front week/month)
            expirations = tk.options
            if not expirations:
                snap.error = "No option expirations found"
                return snap
            expiry = expirations[0]

            chain = tk.option_chain(expiry)
            calls, puts = chain.calls, chain.puts

            # ATM strike = strike closest to spot
            snap.atm_strike = float(
                calls.iloc[(calls["strike"] - snap.spot).abs().argsort()[:1]]["strike"].values[0]
            )

            # Max OI strikes
            snap.max_call_oi_strike = float(calls.loc[calls["openInterest"].idxmax(), "strike"])
            snap.max_put_oi_strike = float(puts.loc[puts["openInterest"].idxmax(), "strike"])

            # PCR (OI based)
            total_call_oi = calls["openInterest"].sum()
            total_put_oi = puts["openInterest"].sum()
            snap.pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi else None

            # IV skew: compare avg IV of near-money OTM puts vs OTM calls
            snap.iv_skew_pct = self._compute_iv_skew(calls, puts, snap.spot)

            # Max Pain (simplified): strike range with lowest total option "loss" to writers
            snap.max_pain_low, snap.max_pain_high = self._compute_max_pain(calls, puts)

            # Vol/OI hotspot: near-money strike with highest volume-to-OI ratio
            snap.hotspot_strike, snap.hotspot_side, snap.hotspot_ratio = self._compute_hotspot(
                calls, puts, snap.atm_strike
            )

            # Composite signal (PCR + IV skew must agree)
            snap.signal = self._compute_signal(snap)

        except Exception as e:
            snap.error = str(e)

        return snap

    @staticmethod
    def _compute_iv_skew(calls, puts, spot: float) -> Optional[float]:
        otm_calls = calls[calls["strike"] > spot].nsmallest(NEAR_STRIKE_WINDOW, "strike")
        otm_puts = puts[puts["strike"] < spot].nlargest(NEAR_STRIKE_WINDOW, "strike")
        if otm_calls.empty or otm_puts.empty:
            return None
        call_iv = otm_calls["impliedVolatility"].mean()
        put_iv = otm_puts["impliedVolatility"].mean()
        if call_iv == 0:
            return None
        return round((put_iv - call_iv) / call_iv * 100, 1)

    @staticmethod
    def _compute_max_pain(calls, puts):
        strikes = sorted(set(calls["strike"]).union(puts["strike"]))
        pain = {}
        for s in strikes:
            call_loss = ((s - calls["strike"]).clip(lower=0) * calls["openInterest"]).sum()
            put_loss = ((puts["strike"] - s).clip(lower=0) * puts["openInterest"]).sum()
            pain[s] = call_loss + put_loss
        if not pain:
            return None, None
        min_pain_strike = min(pain, key=pain.get)
        # give a small range around the exact max pain strike for readability
        idx = strikes.index(min_pain_strike)
        low = strikes[max(idx - 1, 0)]
        high = strikes[min(idx + 1, len(strikes) - 1)]
        return low, high

    @staticmethod
    def _compute_hotspot(calls, puts, atm_strike: float):
        """Returns (strike, side, ratio) for the near-money strike with the
        highest volume/openInterest ratio, or (None, None, None) if nothing
        clears the > 1 threshold."""
        near_calls = calls[(calls["strike"] - atm_strike).abs() <= NEAR_STRIKE_WINDOW].copy()
        near_puts = puts[(puts["strike"] - atm_strike).abs() <= NEAR_STRIKE_WINDOW].copy()

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

    @staticmethod
    def classify_pcr(pcr: Optional[float]) -> str:
        """green = bullish tilt, red = bearish tilt, yellow = neutral."""
        if pcr is None:
            return "yellow"
        if pcr > 1.2:
            return "green"
        if pcr < 0.8:
            return "red"
        return "yellow"

    @staticmethod
    def classify_iv_skew(iv_skew_pct: Optional[float]) -> str:
        """green = puts richer (bullish hedging tilt), red = calls richer (bearish)."""
        if iv_skew_pct is None:
            return "yellow"
        if iv_skew_pct > 1.0:
            return "green"
        if iv_skew_pct < -1.0:
            return "red"
        return "yellow"

    @staticmethod
    def classify_hotspot(side: Optional[str]) -> str:
        """green = put-side hotspot (bullish tilt), red = call-side (bearish)."""
        if side == "P":
            return "green"
        if side == "C":
            return "red"
        return "yellow"

    @classmethod
    def _compute_signal(cls, snap: OptionSnapshot) -> str:
        """
        Overall ticker signal is decided ONLY by PCR + IV skew agreeing.
        VOL/OI hotspot is informational only and does not vote here.
        """
        pcr_class = cls.classify_pcr(snap.pcr)
        iv_class = cls.classify_iv_skew(snap.iv_skew_pct)

        if pcr_class == "green" and iv_class == "green":
            return "green"
        if pcr_class == "red" and iv_class == "red":
            return "red"
        return "yellow"


# ---------------------------------------------------------------------
# PRINTER
# ---------------------------------------------------------------------
def print_table(snapshots: list[OptionSnapshot]) -> None:
    console = Console()
    table = Table(
        show_header=True,
        header_style="bold",
        show_lines=True,
        box=box.ASCII2,
    )

    table.add_column("TICKER", justify="left")
    table.add_column("SPOT ($)", justify="left")
    table.add_column("STRIKE ($)\n(ATM)", justify="left")
    table.add_column("CALL WALL ($)\n(Strike)", justify="left")
    table.add_column("PUT WALL ($)\n(Strike)", justify="left")
    table.add_column("PCR", justify="left")
    table.add_column("IV\nSKEW", justify="left")
    table.add_column("MAX PAIN ($)\nRANGE", justify="left")
    table.add_column("VOL/OI", justify="left")

    circle = {"green": "green", "red": "red", "yellow": "yellow"}

    for s in snapshots:
        if s.error:
            table.add_row(f"{s.ticker} !", "-", "-", "-", "-", "-", "-", "-", f"error: {s.error}")
            continue

        ticker_cell = Text(f"{s.ticker} ")
        ticker_cell.append("\u25CF", style=circle[s.signal])  # colored dot, single-width

        pcr_text = Text(f"{s.pcr:.2f}" if s.pcr is not None else "-")
        pcr_text.stylize(circle[OptionChainAnalyzer.classify_pcr(s.pcr)])

        iv_text = Text(f"{s.iv_skew_pct:+.1f}%" if s.iv_skew_pct is not None else "-")
        iv_text.stylize(circle[OptionChainAnalyzer.classify_iv_skew(s.iv_skew_pct)])

        if s.hotspot_side:
            vol_oi_label = f"${s.hotspot_strike:g} {s.hotspot_side} {s.hotspot_ratio:.1f}x"
        else:
            vol_oi_label = "-"
        vol_oi_text = Text(vol_oi_label)
        vol_oi_text.stylize(circle[OptionChainAnalyzer.classify_hotspot(s.hotspot_side)])

        table.add_row(
            ticker_cell,
            f"{s.spot:.2f}",
            f"{s.atm_strike:g}",
            f"{s.max_call_oi_strike:g}",
            f"{s.max_put_oi_strike:g}",
            pcr_text,
            iv_text,
            f"{s.max_pain_low:g}-{s.max_pain_high:g}" if s.max_pain_low is not None else "-",
            vol_oi_text,
        )

    console.print(table)


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
if __name__ == "__main__":
    analyzer = OptionChainAnalyzer(TICKERS)
    analyzer.run()
    print_table(analyzer.snapshots)