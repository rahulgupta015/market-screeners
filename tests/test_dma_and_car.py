import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd


MODULE_PATH = Path(__file__).parents[1] / "src" / "dsm" / "screeners" / "dma-and-car.py"
SPEC = importlib.util.spec_from_file_location("dma_and_car", MODULE_PATH)
dma_and_car = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dma_and_car
SPEC.loader.exec_module(dma_and_car)


class DmaAndCarTests(unittest.TestCase):
    def test_zone_codes_preserve_zone_rules(self):
        self.assertEqual(dma_and_car.get_zone(120, 100, 90, 80), "B++")
        self.assertEqual(dma_and_car.get_zone(46, 45, 44, 42), "B+")
        self.assertEqual(dma_and_car.get_zone(92, 95, 98, 100), "B-")
        self.assertEqual(dma_and_car.get_zone(85, 90, 100, 110), "B--")
        self.assertEqual(dma_and_car.get_zone(100, 90, 95, 80), "U")

    def test_compute_car_scores_longest_increasing_tail(self):
        dates = pd.date_range("2026-01-01", periods=5, freq="D")
        prices = pd.Series([10, 9, 8, 9, 10], index=dates)

        self.assertEqual(dma_and_car.compute_car(prices, dates[0]), 3)

    def test_ticker_holds_raw_values_and_supports_display_keys(self):
        ticker = dma_and_car.Ticker(symbol="TEST", cmp=42.5, zone="B+")

        self.assertEqual(ticker["Stock"], "TEST")
        self.assertEqual(ticker["CMP"], 42.5)
        ticker["RSI"] = 55.0
        self.assertEqual(ticker.rsi, 55.0)

    def test_scan_all_returns_raw_ticker_records(self):
        expected = [dma_and_car.Ticker(symbol="AAA"), dma_and_car.Ticker(symbol="BBB")]

        with patch.object(dma_and_car, "compute_ticker", side_effect=expected) as compute:
            actual = dma_and_car.scan_all(["AAA", "BBB"])

        self.assertEqual(actual, expected)
        self.assertEqual(compute.call_count, 2)

    def test_format_row_uses_compact_dates(self):
        ticker = dma_and_car.Ticker(
            symbol="TEST",
            high_date=pd.Timestamp(date(2026, 7, 15)),
            low_date=pd.Timestamp(date(2026, 4, 2)),
        )

        row = dma_and_car.format_row(ticker)

        self.assertEqual(row["52W High"], "07-15-26")
        self.assertEqual(row["52W Low"], "04-02-26")


if __name__ == "__main__":
    unittest.main()
