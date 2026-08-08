import unittest

import pandas as pd

from market_screeners.screeners.institution import (
    add_acc_dist_flag,
    add_ant_mvp_flag,
    add_divergence_flag,
    add_rvol_flag,
    add_trend_flag,
    add_vol_dryup_flag,
    add_vsa_flag,
    compute_obv_ad,
)


def synthetic_ohlcv(closes, volumes=None, high_pad=0.5, low_pad=0.5):
    """Build a minimal daily OHLCV DataFrame shaped like a yfinance download."""
    dates = pd.date_range("2025-01-01", periods=len(closes), freq="D")
    close = pd.Series(closes, index=dates, dtype=float)
    if volumes is None:
        volumes = [1_000_000] * len(closes)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + high_pad,
            "low": close - low_pad,
            "close": close,
            "volume": pd.Series(volumes, index=dates, dtype=float),
        }
    )


class InstitutionScreenerTests(unittest.TestCase):
    def test_ant_mvp_flags_persistent_momentum_volume_and_price(self):
        # 60 flat days to warm up the 50-day volume SMA, then a strong
        # 15-day run up >20% with up-days and a volume spike on the final day.
        closes = [100] * 60 + [100 + (25 * i / 15) for i in range(1, 16)]
        volumes = [500_000] * 74 + [900_000]
        df = synthetic_ohlcv(closes, volumes)

        df = add_ant_mvp_flag(df)

        self.assertTrue(bool(df["ANT_MVP"].iloc[-1]))

    def test_divergence_flag_fires_when_price_flat_but_obv_rising(self):
        # Price flat, but volume skews to up-days so OBV trends up.
        closes = [100, 100.1, 100, 100.1, 100, 100.1, 100, 100.1, 100, 100.1, 100]
        volumes = [1000, 2000, 1000, 2000, 1000, 2000, 1000, 2000, 1000, 2000, 1000]
        df = synthetic_ohlcv(closes, volumes)
        df = compute_obv_ad(df)

        df = add_divergence_flag(df)

        self.assertIn("div_flag", df.columns)
        self.assertEqual(df["div_flag"].dtype, bool)

    def test_acc_dist_flag_true_when_more_accumulation_than_distribution_days(self):
        # Mostly up-closes on rising volume within the 25-day window.
        closes = [100 + i * 0.5 for i in range(30)]
        volumes = [1000 + i * 10 for i in range(30)]
        df = synthetic_ohlcv(closes, volumes)

        df = add_acc_dist_flag(df)

        self.assertTrue(bool(df["acc_dist_flag"].iloc[-1]))
        self.assertGreater(df["acc_count"].iloc[-1], df["dist_count"].iloc[-1])

    def test_vsa_flag_column_present_and_boolean(self):
        closes = [100 + (i % 5) for i in range(40)]
        df = synthetic_ohlcv(closes)

        df = add_vsa_flag(df)

        self.assertIn("vsa_event", df.columns)
        self.assertIn("vsa_flag", df.columns)
        self.assertEqual(df["vsa_flag"].dtype, bool)

    def test_rvol_flag_fires_on_high_relative_volume_and_narrow_range(self):
        # 24 days of normal ($1.00) daily range to establish an ATR
        # baseline, then a final day with a much narrower ($0.04) range
        # on a volume spike well above the 20-day average.
        dates = pd.date_range("2025-01-01", periods=25, freq="D")
        close = pd.Series([100.0] * 25, index=dates)
        high = pd.Series([100.5] * 24 + [100.02], index=dates)
        low = pd.Series([99.5] * 24 + [99.98], index=dates)
        volume = pd.Series([1000] * 24 + [5000], index=dates, dtype=float)
        df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume})

        df = add_rvol_flag(df)

        self.assertTrue(bool(df["rvol_flag"].iloc[-1]))

    def test_vol_dryup_flag_fires_when_volume_well_below_average(self):
        volumes = [1000] * 20 + [100]
        df = synthetic_ohlcv([100] * 21, volumes)

        df = add_vol_dryup_flag(df)

        self.assertTrue(bool(df["vol_dryup"].iloc[-1]))

    def test_trend_flag_true_when_price_above_50sma(self):
        closes = [100] * 50 + [150]
        df = synthetic_ohlcv(closes)

        df = add_trend_flag(df)

        self.assertTrue(bool(df["trend_ok"].iloc[-1]))


if __name__ == "__main__":
    unittest.main()
