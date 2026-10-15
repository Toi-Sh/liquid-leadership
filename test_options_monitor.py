import unittest

from options_monitor import atm_iv, bs_gamma, build_book, gamma_flip, parse_occ, render_html, upcoming_expirations


def contract(strike, iv, oi):
    return {"strike": strike, "iv": iv, "oi": oi}


class OptionsMonitorTests(unittest.TestCase):
    def test_occ_symbol_splits_into_expiry_side_and_strike(self):
        expiry, side, strike = parse_occ("SPY261016C00770000", "SPY")
        self.assertEqual(expiry, "2026-10-16")
        self.assertEqual(side, "call")
        self.assertEqual(strike, 770)

    def test_gamma_is_positive_at_the_money(self):
        self.assertGreater(bs_gamma(100, 100, 30 / 365, 0.2), 0)
        self.assertEqual(bs_gamma(100, 100, 0, 0.2), 0)

    def test_atm_iv_uses_the_nearest_strike(self):
        calls = [contract(99, 0.20, 10), contract(110, 0.40, 10)]
        puts = [contract(99, 0.22, 10), contract(110, 0.50, 10)]
        self.assertAlmostEqual(atm_iv(calls, puts, 100), 0.21)

    def test_walls_and_the_flip(self):
        calls = [contract(90, 0.2, 10), contract(100, 0.2, 500), contract(110, 0.2, 10)]
        puts = [contract(90, 0.2, 800), contract(100, 0.2, 10), contract(110, 0.2, 10)]
        book = build_book(calls, puts, 100, "2026-11-20", "2026-10-15")
        self.assertEqual(book["call_wall"], 100)
        self.assertEqual(book["put_wall"], 90)
        self.assertIsNotNone(book["flip"])
        self.assertGreater(gamma_flip(book["strikes"], 100), 90)
        self.assertLess(gamma_flip(book["strikes"], 100), 100)

    def test_expirations_stop_at_the_window(self):
        raw = ["2026-10-14", "2026-10-16", "2026-12-18", "2027-06-18"]
        self.assertEqual(upcoming_expirations(raw, "2026-10-15", limit_days=90, cap=6), ["2026-10-16", "2026-12-18"])

    def test_page_names_the_charts(self):
        html = render_html({
            "as_of": "2026-10-14",
            "names": [],
            "vol": {"vix": [], "vxn": []},
        })
        self.assertIn("Implied volatility", html)
        self.assertIn("Open interest", html)
        self.assertIn("Gamma", html)
        self.assertIn("monitor.html", html)


if __name__ == "__main__":
    unittest.main()
