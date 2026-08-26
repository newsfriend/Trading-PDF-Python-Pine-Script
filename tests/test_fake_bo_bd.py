import unittest
import numpy as np
import pandas as pd
from pathlib import Path

from python.fake_bo_bd import FakeBreakConfig, compute_fake_break_signals


class FakeBreakTests(unittest.TestCase):
    def frame(self):
        close = np.linspace(100, 105, 45)
        frame = pd.DataFrame({
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.full(45, 100.0),
        })
        return frame

    def test_fbd_requires_sweep_then_follow_up(self):
        f = self.frame()
        prior_low = f.loc[10:29, "low"].min()
        f.loc[30, ["open", "high", "low", "close", "volume"]] = [101, 102, prior_low - 2, prior_low + 0.2, 500]
        f.loc[31, ["open", "high", "low", "close", "volume"]] = [prior_low + 0.2, 103, prior_low, 102.5, 200]
        result = compute_fake_break_signals(f, FakeBreakConfig(require_band_touch=False, min_confirmations=0))
        self.assertTrue(result.loc[30, "fbd_sweep"])
        self.assertFalse(result.loc[30, "fbd_buy"])
        self.assertTrue(result.loc[31, "fbd_buy"])
        self.assertAlmostEqual(result.loc[31, "long_stop"], prior_low)

    def test_fbo_requires_sweep_then_follow_up(self):
        f = self.frame()
        prior_high = f.loc[10:29, "high"].max()
        f.loc[30, ["open", "high", "low", "close", "volume"]] = [104, prior_high + 2, 103, prior_high - 0.2, 500]
        f.loc[31, ["open", "high", "low", "close", "volume"]] = [prior_high - 0.2, prior_high, 101, 101.5, 200]
        result = compute_fake_break_signals(f, FakeBreakConfig(require_band_touch=False, min_confirmations=0))
        self.assertTrue(result.loc[30, "fbo_sweep"])
        self.assertTrue(result.loc[31, "fbo_sell"])
        self.assertAlmostEqual(result.loc[31, "short_stop"], prior_high)

    def test_missing_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing OHLCV"):
            compute_fake_break_signals(pd.DataFrame({"close": [1, 2]}))


class FakeBreakPineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("pine/fake_bo_bd.pine").read_text(encoding="utf-8")

    def test_core_manual_contract_is_present(self):
        for token in (
            "fbdSweep = low < previousLow and close > previousLow",
            "fboSweep = high > previousHigh and close < previousHigh",
            "fbdSweep[1] and high > high[1] and close > high[1]",
            "fboSweep[1] and low < low[1] and close < low[1]",
            'alertcondition(fbdBuy, "FBD BUY"',
            'alertcondition(fboSell, "FBO SELL"',
        ):
            self.assertIn(token, self.source)


if __name__ == "__main__":
    unittest.main()
