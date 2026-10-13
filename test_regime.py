import unittest

import pandas as pd

from regime import (
    Memory,
    breadth_improving,
    build_snapshot,
    catching_up,
    compute_breadth,
    has_thrust,
    posture_score,
    render_html,
    rolling_ratio,
    transition,
    walk_regime,
)


def day(**overrides) -> dict:
    base = {
        "date": "2026-01-02",
        "t2108": 24.0,
        "t2108_ema10": 22.0,
        "up4": 80,
        "down4": 300,
        "ratio5": 0.56,
        "ratio10": 0.7,
        "bull13": 400,
        "bear13": 800,
        "balance": -400,
        "bull20": 8,
        "bear20": 20,
        "up25m": 10,
        "down25m": 40,
        "up25q": 100,
        "down25q": 200,
        "up50": 12,
        "down50": 8,
        "n": 1000,
        "n_nyse": 400,
        "drawdown": -1.9,
        "spy_above_20": True,
        "health_passes": 18,
        "health_total": 24,
    }
    base.update(overrides)
    return base


class BreadthTests(unittest.TestCase):
    def test_ratio_is_the_sum_of_up_days_over_down_days(self):
        up = pd.Series([2, 2, 2, 2, 2], dtype=float)
        down = pd.Series([4, 4, 4, 4, 4], dtype=float)
        self.assertEqual(float(rolling_ratio(up, down, 5).iloc[-1]), 0.5)

    def test_one_sided_up_window_counts_as_thrust(self):
        up = pd.Series([1, 1, 1, 1, 1], dtype=float)
        down = pd.Series([0, 0, 0, 0, 0], dtype=float)
        self.assertGreaterEqual(float(rolling_ratio(up, down, 5).iloc[-1]), 99)
        self.assertTrue(has_thrust({"ratio5": 99, "up4": 1}))

    def test_t2108_uses_only_nyse_names(self):
        index = pd.bdate_range("2025-01-01", periods=50)
        closes = pd.DataFrame({
            "A": pd.Series(range(50), index=index, dtype=float) + 10,
            "B": pd.Series(range(50, 0, -1), index=index, dtype=float),
            "C": pd.Series(range(50), index=index, dtype=float) + 5,
        })
        out = compute_breadth(closes, pd.Series({"A": True, "B": True, "C": False}))
        self.assertEqual(float(out["t2108"].iloc[-1]), 50.0)
        self.assertEqual(int(out["n_nyse"].iloc[-1]), 2)


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.washout = Memory("Washout", "2026-09-23", 13, 18.0)

    def test_washout_waits_for_the_second_vote(self):
        self.assertEqual(transition("Washout", self.washout, day(t2108=24.0, ratio5=0.56, up4=80)), "Washout")

    def test_washout_bounces_when_the_ratio_confirms(self):
        self.assertEqual(transition("Washout", self.washout, day(t2108=24.0, ratio5=1.6, up4=80)), "Bounce")

    def test_washout_bounces_on_a_500_name_up_day(self):
        self.assertEqual(transition("Washout", self.washout, day(t2108=24.0, ratio5=0.4, up4=520)), "Bounce")

    def test_clearing_25_without_a_thrust_is_weak(self):
        self.assertEqual(transition("Washout", self.washout, day(t2108=26.0, ratio5=0.8, up4=100)), "Weak")

    def test_a_thrust_through_25_is_still_a_bounce(self):
        self.assertEqual(transition("Washout", self.washout, day(t2108=26.0, ratio5=1.6, up4=80)), "Bounce")

    def test_recovery_holds_while_price_stays_above_the_washout_low(self):
        memory = Memory("Recovery", "2026-10-06", 1, 17.1)
        self.assertEqual(transition("Recovery", memory, day(t2108=24.4, ratio5=1.19)), "Recovery")

    def test_recovery_fails_when_the_washout_low_breaks(self):
        memory = Memory("Recovery", "2026-10-06", 2, 17.1)
        self.assertEqual(transition("Recovery", memory, day(t2108=16.0, ratio5=0.4)), "Washout")

    def test_a_low_average_catching_up_is_not_improvement(self):
        stalled = day(t2108=33.5, t2108_ema10=26.9, t2108_delta=2.7, ema_delta=1.5, rise_3=4.8, accel=0.5, ratio5=0.67)
        self.assertTrue(catching_up(stalled))
        self.assertFalse(breadth_improving(stalled))

    def test_breadth_improves_when_the_gap_closes_fast_and_accelerates(self):
        thrust = day(t2108=36.0, t2108_ema10=24.0, t2108_delta=5.0, ema_delta=1.0, rise_3=9.0, accel=2.0, ratio5=1.4)
        self.assertFalse(catching_up(thrust))
        self.assertTrue(breadth_improving(thrust))

    def test_above_a_low_average_does_not_make_a_recovery(self):
        memory = Memory("Bounce", "2026-10-05", 2, 17.1)
        stalled = day(t2108=33.5, ratio5=0.67, catching_up=True, improving=False)
        self.assertEqual(transition("Bounce", memory, stalled), "Weak")

    def test_recovery_ends_when_the_average_is_only_catching_up(self):
        memory = Memory("Recovery", "2026-10-06", 3, 17.1)
        stalled = day(t2108=33.5, ratio5=0.67, catching_up=True, improving=False)
        self.assertEqual(transition("Recovery", memory, stalled), "Weak")

    def test_a_bounce_without_a_low_washes_out_again_under_29(self):
        memory = Memory("Bounce", "2026-08-01", 10, None)
        self.assertEqual(transition("Bounce", memory, day(t2108=24.0, ratio5=0.8)), "Washout")

    def test_extended_rolls_over_under_70(self):
        memory = Memory("Extended", "2026-01-02", 4, None)
        self.assertEqual(transition("Extended", memory, day(t2108=68)), "Rolling over")

    def test_walk_counts_sessions_and_the_votes(self):
        days = [
            day(date="2026-09-23", t2108=18.0, ratio5=0.4, up4=10),
            day(date="2026-09-24", t2108=24.0, ratio5=0.56, up4=80),
        ]
        walked = walk_regime(days)
        self.assertEqual(walked[-1]["stage"], "Washout")
        self.assertEqual(walked[-1]["sessions"], 2)
        self.assertEqual(walked[-1]["since"], "2026-09-23")
        self.assertIn("votes 1 of 2", walked[-1]["progress"])
        self.assertEqual(walked[-1]["posture"], posture_score(24.0, 18, 24))
        self.assertIsInstance(walked[-1]["momentum"], int)


class PageTests(unittest.TestCase):
    def test_page_names_the_stage_and_escapes_rules(self):
        walked = walk_regime([
            day(date="2026-10-10", t2108=22.0),
            day(date="2026-10-12", t2108=24.4, ratio5=0.56, up4=86, down4=367),
        ])
        snapshot = build_snapshot(walked, [], {"price": "15.32", "delta": "—", "band": "normal", "day": "15.13–15.53"}, {"price": "5.24", "delta": "—", "side": "above 5.0"}, [], "12 Oct 2026, close")
        snapshot["rules"] = ["<script>alert(1)</script>"]
        html = render_html(snapshot, [{
            "symbol": "SPY",
            "ema5_above_10": True,
            "ema10_above_20": True,
            "ema10_slope": True,
            "ema20_slope": False,
            "price_above_10": True,
            "price_above_20": False,
            "rsi": "58.4",
            "as_of": "12 Oct",
        }])
        self.assertIn("Regime", html)
        self.assertIn('aria-current="page"', html)
        self.assertIn("Washout", html)
        self.assertIn("Index health", html)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("SPY", html)


if __name__ == "__main__":
    unittest.main()
