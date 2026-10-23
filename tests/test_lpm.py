"""
Unit tests for screener/lpm.py with synthetic broker data (FEATURE_LPM.md section 8).

Run from the repo root:  python -m unittest tests.test_lpm
"""
import os
import json
import math
import unittest

from screener.lpm import (
    LPM_PARAMS,
    adaptive_theta,
    build_lpm,
    classify_phase,
    classify_trend,
    compute_daily_metrics,
    compute_intensity,
    compute_lpm,
    compute_vol_rotation,
    detect_divergence,
    divergence_markers,
    dominant_vr_color,
    rolling_slope,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(ROOT, "scratch", "lpm_fixtures")
RETAIL_AVG = 1_000_000


def broker(code, bval=0, bfrq=0, sval=0, sfrq=0):
    return {"broker_code": code, "bval": bval, "bfrq": bfrq, "sval": sval, "sfrq": sfrq, "nval": bval - sval}


def make_day(big=(), retail_n=8, retail_val=100_000_000, scale=1.0, extra=()):
    """
    One synthetic day. big: (code, buy_val, buy_avg, sell_val, sell_avg) per large broker.
    Retail brokers trade at RETAIL_AVG per trade and absorb the large brokers' net,
    so total buy value equals total sell value as in real data.
    """
    rows, big_net = [], 0
    for code, bv, bavg, sv, savg in big:
        rows.append(broker(code, bv, round(bv / bavg) if bv else 0, sv, round(sv / savg) if sv else 0))
        big_net += bv - sv
    per = big_net / retail_n
    for i in range(retail_n):
        bv = retail_val + max(0, -per)
        sv = retail_val + max(0, per)
        rows.append(broker(f"R{i}", bv, round(bv / RETAIL_AVG), sv, round(sv / RETAIL_AVG)))
    rows.extend(extra)
    if scale != 1.0:
        for r in rows:
            r["bval"] *= scale
            r["sval"] *= scale
            r["nval"] *= scale
    return rows


def accumulation_day(i, **kwargs):
    wobble = 1 + 0.2 * math.sin(i)
    return make_day(big=[("BK", 60e6 * wobble, 6e6, 0, 0), ("AK", 50e6 * wobble, 6e6, 0, 0)], **kwargs)


def distribution_day(i):
    wobble = 1 + 0.2 * math.sin(i)
    return make_day(big=[("BK", 0, 0, 60e6 * wobble, 6e6), ("AK", 0, 0, 50e6 * wobble, 6e6)])


def build_days(n, brokers_fn, close_fn):
    return [{"date": f"D{i:03d}", "close": close_fn(i), "brokers": brokers_fn(i)} for i in range(n)]


def flat_close(i):
    return 1000 * (1 + 0.005 * math.sin(i * 1.3))


class TestDailyMetrics(unittest.TestCase):
    def test_neutral_day_has_zero_pressure(self):
        m = compute_daily_metrics(make_day())
        self.assertAlmostEqual(m["pressure"], 0.0, places=12)
        self.assertAlmostEqual(m["avg_trade_value"], RETAIL_AVG)

    def test_large_buyers_get_full_weight(self):
        m = compute_daily_metrics(accumulation_day(0))
        self.assertGreater(m["pressure"], 0.1)
        self.assertEqual(set(m["broker_smart_net"]), {"BK", "AK"})

    def test_price_invariance(self):
        base = [compute_daily_metrics(accumulation_day(i))["pressure"] for i in range(40)]
        scaled = [compute_daily_metrics(accumulation_day(i, scale=100.0))["pressure"] for i in range(40)]
        for a, b in zip(base, scaled):
            self.assertAlmostEqual(a, b, delta=1e-9)

    def test_crowd_invariance_when_large_brokers_are_already_full_weight(self):
        # Holds when the large brokers sit at r >= R1 before and after; with r between
        # R0 and R1, extra small trades lower A_d and can raise their weight instead.
        base = compute_daily_metrics(accumulation_day(3))
        crowded = compute_daily_metrics(accumulation_day(3, extra=[broker("XR", 200e6, 200, 200e6, 200)]))
        self.assertGreater(crowded["pressure"], 0)
        self.assertLess(crowded["pressure"], base["pressure"])

    def test_zero_frequency_side_is_skipped(self):
        day = accumulation_day(0, extra=[
            broker("ZZ", bval=150e6, bfrq=0, sval=0, sfrq=0),
            broker("ZW", bval=0, bfrq=0, sval=150e6, sfrq=0),
            broker("ZY"),
        ])
        for use_conc in (False, True):
            m = compute_daily_metrics(day, dict(LPM_PARAMS, use_conc_weight=use_conc))
            self.assertNotIn("ZZ", m["broker_smart_net"])
            self.assertNotIn("ZW", m["broker_smart_net"])
            self.assertNotIn("ZY", m["broker_smart_net"])

    def test_two_way_broker_never_flips_sign_against_net_flow(self):
        # CC is net seller (nval = -10e6) with block buy (20e6 / 2 = 10e6) and sliced sell (30e6 / 30 = 1e6)
        day = make_day(extra=[
            broker("CC", bval=20e6, bfrq=2, sval=30e6, sfrq=30),
            broker("YP", bval=30e6, bfrq=30, sval=20e6, sfrq=2),
        ])
        m_n1 = compute_daily_metrics(day)
        self.assertNotIn("CC", m_n1["broker_smart_net"])
        self.assertNotIn("YP", m_n1["broker_smart_net"])
        self.assertAlmostEqual(m_n1["pressure"], 0.0, places=12)

        # Under N3 (use_conc_weight=True) with larger net share, sign strictly follows nval
        day_big_net = make_day(extra=[
            broker("CC", bval=20e6, bfrq=2, sval=80e6, sfrq=80),
            broker("YP", bval=80e6, bfrq=80, sval=20e6, sfrq=2),
        ])
        m_n3 = compute_daily_metrics(day_big_net, dict(LPM_PARAMS, use_conc_weight=True))
        self.assertLess(m_n3["broker_smart_net"]["CC"], 0.0)
        self.assertGreater(m_n3["broker_smart_net"]["YP"], 0.0)
        self.assertLessEqual(abs(m_n3["broker_smart_net"]["CC"]), 60e6)
        self.assertLessEqual(abs(m_n3["broker_smart_net"]["YP"]), 60e6)

    def test_balanced_broker_with_zero_nval_is_excluded(self):
        day = make_day(extra=[broker("MM", bval=50e6, bfrq=5, sval=50e6, sfrq=50)])
        for use_conc in (False, True):
            m = compute_daily_metrics(day, dict(LPM_PARAMS, use_conc_weight=use_conc))
            self.assertNotIn("MM", m["broker_smart_net"])
            self.assertAlmostEqual(m["pressure"], 0.0, places=12)

    def test_n3_concentration_weight_captures_sliced_institutional_order(self):
        # Broker IN sells 100e6 in 100 trades (avg 1e6 == RETAIL_AVG, so w_size == 0)
        # Retail absorbs 100e6 across 10 brokers (10e6 each, < 2% of turnover)
        day = [broker("IN", bval=0, bfrq=0, sval=100e6, sfrq=100)] + [
            broker(f"R{i}", bval=90e6, bfrq=90, sval=80e6, sfrq=80) for i in range(10)
        ]
        m_n1 = compute_daily_metrics(day)
        self.assertEqual(m_n1["broker_smart_net"], {})
        self.assertAlmostEqual(m_n1["pressure"], 0.0, places=12)

        m_n3 = compute_daily_metrics(day, dict(LPM_PARAMS, use_conc_weight=True))
        self.assertAlmostEqual(m_n3["broker_smart_net"]["IN"], -100e6)
        self.assertAlmostEqual(m_n3["pressure"], -100e6 / 900e6)

    def test_day_without_trades_returns_none(self):
        self.assertIsNone(compute_daily_metrics([]))
        self.assertIsNone(compute_daily_metrics(None))
        self.assertIsNone(compute_daily_metrics([broker("XX")]))

    def test_low_liquidity_scales_pressure(self):
        day = [broker("BK", 30e6, 3, 0, 0), broker("R0", 0, 0, 30e6, 30), broker("R1", 5e6, 5, 5e6, 5)]
        m = compute_daily_metrics(day)
        unscaled = compute_daily_metrics(day, dict(LPM_PARAMS, low_liquidity_frq=0))
        self.assertTrue(m["low_liquidity"])
        self.assertFalse(unscaled["low_liquidity"])
        self.assertAlmostEqual(m["pressure"], unscaled["pressure"] * m["frequency"] / 50)

    def test_vr_efficiency_and_top5_share(self):
        day = [broker("A", 100, 10, 0, 0), broker("B", 0, 0, 100, 10), broker("C", 50, 5, 50, 5)]
        m = compute_daily_metrics(day)
        self.assertAlmostEqual(m["vr_efficiency"], 200 / (2 * 150))
        self.assertAlmostEqual(m["top5_share"], 1.0)


class TestLineAndTrend(unittest.TestCase):
    def test_line_starts_from_virtual_zero_and_gap_stays_flat(self):
        self.assertEqual(compute_lpm([0.1, None, -0.05]), [10.0, 10.0, 5.0])

    def test_slope_needs_full_window_and_skips_gaps(self):
        p = [0.1] * 4 + [None] + [0.1] * 5
        s5 = rolling_slope(p, 5)
        self.assertIsNone(s5[3])
        self.assertAlmostEqual(s5[4], 10.0)
        self.assertAlmostEqual(s5[9], 10.0)

    def test_slope_none_when_window_mostly_missing(self):
        self.assertIsNone(rolling_slope([0.1, None, None, None, 0.1], 5)[4])

    def test_adaptive_theta(self):
        self.assertEqual(adaptive_theta([0.1] * 30, 5)[-1], LPM_PARAMS["theta_floor"])
        noisy = [0.1 if i % 2 else -0.1 for i in range(30)]
        self.assertAlmostEqual(adaptive_theta(noisy, 5)[-1], 10.0 / math.sqrt(5))

    def test_trend_table(self):
        self.assertEqual(classify_trend(2.0, 1.0, 1.0), "RISING")
        self.assertEqual(classify_trend(2.0, -1.0, 1.0), "TURNING_UP")
        self.assertEqual(classify_trend(-2.0, -1.0, 1.0), "FALLING")
        self.assertEqual(classify_trend(-2.0, 1.0, 1.0), "TURNING_DOWN")
        self.assertEqual(classify_trend(0.5, 5.0, 1.0), "FLAT")
        self.assertEqual(classify_trend(None, None, 1.0), "DATA_KURANG")


class TestDivergence(unittest.TestCase):
    def test_recent_high_counts_after_the_record_day(self):
        closes = [1000.0] * 21
        closes[18] = 1030.0
        closes[19] = closes[20] = 1020.0
        status, chg, new_high = detect_divergence(closes, 20, slope_slow=-5.0, theta_slow=0.5)
        self.assertTrue(new_high)
        self.assertAlmostEqual(chg, 2.0)
        self.assertEqual(status, "NEGATIVE")

    def test_not_enough_history(self):
        self.assertEqual(detect_divergence([1000.0] * 10, 9, 5.0, 0.5), (None, None, None))

    def test_markers_are_debounced(self):
        statuses = ["NONE", "POSITIVE", "NONE", "POSITIVE", "POSITIVE", "NONE", "NONE", "NONE", "POSITIVE", "NEGATIVE"]
        dates = [f"D{i}" for i in range(len(statuses))]
        self.assertEqual(divergence_markers(statuses, dates), [
            {"date": "D1", "type": "POSITIVE"},
            {"date": "D8", "type": "POSITIVE"},
            {"date": "D9", "type": "NEGATIVE"},
        ])


class TestLenses(unittest.TestCase):
    def test_spike_on_day_30(self):
        shares = [0.20 + 0.01 * ((i % 3) - 1) for i in range(29)] + [0.60]
        z, levels = compute_intensity(shares)
        self.assertIsNone(levels[5])
        self.assertTrue(all(lvl == "NORMAL" for lvl in levels[10:29]))
        self.assertEqual(levels[29], "SPIKE_EKSTREM")

    def test_spike_reachable_with_high_baseline_concentration(self):
        # Old ratio rule: 0.95 / 0.45 = 2.1, so SPIKE_EKSTREM (>= 2.5) could never fire here
        shares = [0.45 + 0.02 * ((i % 3) - 1) for i in range(25)] + [0.95]
        _, levels = compute_intensity(shares)
        self.assertEqual(levels[-1], "SPIKE_EKSTREM")

    def test_vol_rotation_colors(self):
        rising = [0.10 + 0.01 * i for i in range(15)]
        falling = list(reversed(rising))
        self.assertEqual(compute_vol_rotation(rising)[1][-1], "HIJAU")
        self.assertEqual(compute_vol_rotation(falling)[1][-1], "MERAH")
        self.assertIsNone(compute_vol_rotation(rising)[1][5])

    def test_dominant_color_tie_goes_to_more_severe(self):
        self.assertEqual(dominant_vr_color(["HIJAU", "HIJAU", "KUNING", "KUNING", "MERAH"]), "KUNING")
        self.assertEqual(dominant_vr_color([None, None]), None)


class TestPhase(unittest.TestCase):
    def test_persiapan(self):
        self.assertEqual(classify_phase("RISING", "NONE", 3.0, 2, "HIJAU", "NORMAL")["id"], "PERSIAPAN")

    def test_persiapan_blocked_after_big_rally(self):
        self.assertEqual(classify_phase("RISING", "NONE", 12.0, 2, "HIJAU", "NORMAL")["id"], "MARKUP")

    def test_turning_down_after_rally_is_panas_not_distribusi(self):
        self.assertEqual(classify_phase("TURNING_DOWN", "NONE", 8.0, 0, "HIJAU", "NORMAL")["id"], "PANAS")

    def test_falling_with_falling_price_is_markdown(self):
        self.assertEqual(classify_phase("FALLING", "NONE", -6.0, 0, "MERAH", "NORMAL")["id"], "MARKDOWN")

    def test_falling_after_rally_is_distribusi(self):
        self.assertEqual(classify_phase("FALLING", "NONE", 7.0, 0, "HIJAU", "NORMAL")["id"], "DISTRIBUSI")

    def test_positive_divergence_with_spikes_stays_senyap(self):
        self.assertEqual(classify_phase("TURNING_UP", "POSITIVE", -1.0, 3, "KUNING", "NORMAL")["id"], "SENYAP")

    def test_data_kurang(self):
        self.assertEqual(classify_phase("DATA_KURANG", None, None, 0, None, None)["id"], "DATA_KURANG")

    def test_secondary_notes(self):
        self.assertIn("Pelepasan Bertahap", classify_phase("FALLING", "NONE", -3.0, 1, None, "SPIKE")["secondary"])
        self.assertIn("Belum Bermakna", classify_phase("FLAT", "NONE", 0.0, 1, None, "SPIKE_EKSTREM")["secondary"])
        self.assertIsNone(classify_phase("RISING", "NONE", 3.0, 0, None, "NORMAL")["secondary"])


class TestScenarios(unittest.TestCase):
    def test_neutral(self):
        out = build_lpm(build_days(40, lambda i: make_day(), flat_close))
        self.assertEqual(out["trend"]["status"], "FLAT")
        self.assertTrue(all(abs(s["pressure"]) < 1e-9 for s in out["series"]))
        self.assertEqual(out["phase"]["id"], "NETRAL")

    def test_silent_accumulation(self):
        out = build_lpm(build_days(40, accumulation_day, flat_close))
        self.assertEqual(out["trend"]["status"], "RISING")
        self.assertEqual(out["divergence"]["status"], "POSITIVE")
        self.assertEqual(out["phase"]["id"], "SENYAP")
        self.assertEqual({b["broker_code"] for b in out["top_smart_brokers"]}, {"BK", "AK"})
        self.assertTrue(all(b["net_smart_value"] > 0 for b in out["top_smart_brokers"]))

    def test_hidden_distribution(self):
        out = build_lpm(build_days(40, distribution_day, lambda i: 1000 * 1.004 ** i))
        self.assertGreaterEqual(out["divergence"]["price_chg_20"], 8.0)
        self.assertEqual(out["trend"]["status"], "FALLING")
        self.assertEqual(out["divergence"]["status"], "NEGATIVE")
        self.assertEqual(out["phase"]["id"], "DISTRIBUSI")
        self.assertEqual(out["divergence"]["markers"][0]["type"], "NEGATIVE")

    def test_gap_day(self):
        days = build_days(40, accumulation_day, flat_close)
        days[14]["brokers"] = None
        out = build_lpm(days)
        self.assertTrue(out["series"][14]["gap"])
        self.assertIsNone(out["series"][14]["pressure"])
        self.assertEqual(out["series"][14]["lpm"], out["series"][13]["lpm"])
        self.assertEqual(out["coverage"], {"available_days": 39, "gap_days": 1})

    def test_short_history_is_data_kurang_but_still_drawn(self):
        out = build_lpm(build_days(15, accumulation_day, flat_close))
        self.assertEqual(out["trend"]["status"], "DATA_KURANG")
        self.assertEqual(out["phase"]["id"], "DATA_KURANG")
        self.assertEqual(len(out["series"]), 15)
        self.assertGreater(out["series"][-1]["lpm"], 0)

    def test_few_stored_days_inside_long_calendar_is_data_kurang(self):
        # Found in the real BBCA smoke test: 10 stored days out of 80 passed the half-window rule
        days = build_days(80, accumulation_day, flat_close)
        for d in days[:70]:
            d["brokers"] = None
        out = build_lpm(days)
        self.assertEqual(out["trend"]["status"], "DATA_KURANG")
        self.assertIsNone(out["divergence"]["status"])
        self.assertEqual(out["divergence"]["markers"], [])
        self.assertEqual(out["phase"]["id"], "DATA_KURANG")

    def test_twenty_days_is_enough_for_trend(self):
        out = build_lpm(build_days(20, accumulation_day, flat_close))
        self.assertNotEqual(out["trend"]["status"], "DATA_KURANG")

    def test_empty_input(self):
        self.assertIsNone(build_lpm([]))


@unittest.skipUnless(os.path.isdir(FIXTURE_DIR), "fixture Langkah 0 tidak ada (scratch/ di-gitignore)")
class TestRealFixtures(unittest.TestCase):
    def load(self, name):
        with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as f:
            return json.load(f)["response"]["brokers"]

    def test_bbca_single_day(self):
        brokers = self.load("R1_BBCA_2026-10-20_2026-10-20.json")
        m = compute_daily_metrics(brokers)
        self.assertAlmostEqual(m["turnover"], sum(b["bval"] for b in brokers))
        self.assertAlmostEqual(m["pressure"], 0.0060, places=3)
        self.assertFalse(m["low_liquidity"])
        m_n3 = compute_daily_metrics(brokers, dict(LPM_PARAMS, use_conc_weight=True))
        self.assertAlmostEqual(m_n3["pressure"], -0.0262, places=3)

    def test_illiquid_day(self):
        m = compute_daily_metrics(self.load("R5_ASRM_2026-10-20_2026-10-20.json"))
        self.assertEqual(m["frequency"], 70)
        self.assertFalse(m["low_liquidity"])
        self.assertTrue(-1.0 <= m["pressure"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
