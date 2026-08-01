import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import pandas as pd

from market_screeners.cli.main import main
from market_screeners.model.ticker import Ticker


def yahoo_response(closes, high_override=None):
    """Build the DataFrame shape returned by yfinance.download."""
    close_series = pd.Series(closes, index=pd.date_range("2025-01-01", periods=len(closes), freq="D"))
    highs = close_series + 0.5
    if high_override is not None:
        highs.iloc[high_override] = close_series.iloc[high_override] + 10
    return pd.DataFrame(
        {
            "Close": close_series,
            "High": highs,
            "Low": close_series - 0.5,
            "Volume": pd.Series([1000] * len(closes), index=close_series.index),
        }
    )


class YahooFinanceIntegrationTests(unittest.TestCase):
    def test_cli_renders_two_tables_from_mocked_yahoo_response(self):
        breakout_closes = [100] * 48 + [100 + (8 * i / 251) for i in range(252)]
        responses = {
            "AAA": yahoo_response(breakout_closes, high_override=48),
            "BBB": yahoo_response([100] * 200 + [100 - (10 * i / 99) for i in range(100)]),
            "CCC": yahoo_response([100] * 299 + [99]),
        }

        def mocked_download(symbol, **kwargs):
            return responses[symbol]

        universe = {symbol: Ticker(symbol) for symbol in responses}
        output = StringIO()
        with (
            patch("market_screeners.cli.main.load_market_universe", return_value=universe),
            patch("market_screeners.service.compute_service.yf.download", side_effect=mocked_download) as download,
            patch.object(sys, "argv", ["market-screeners", "--test"]),
            redirect_stdout(output),
        ):
            main()

        rendered = output.getvalue()
        self.assertEqual(download.call_count, 3)
        self.assertIn("--- Breakouts", rendered)
        self.assertIn("--- Others", rendered)
        self.assertIn("AAA", rendered)
        self.assertIn("BBB", rendered)
        self.assertIn("Total: 3 symbols (2 breakouts, 1 others)", rendered)


if __name__ == "__main__":
    unittest.main()
