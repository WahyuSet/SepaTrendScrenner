"""
Quality Setup Screener Engine (screener/quality_screener.py)
------------------------------------------------------------
Implements 100-Point Composite Momentum & Quality Scoring,
Trade Setup Generation (Pullback & Breakout scenarios),
Fibonacci Retracement / Extension levels, and Supertrend
for all 941 listed IDX companies.
"""
from __future__ import annotations

import os
import json
import math
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd
import numpy as np

from screener.indicators_calc import (
    calc_ema, calc_sma, calc_rsi, calc_bollinger,
    calc_macd, calc_atr, calc_supertrend, calc_donchian, calc_adx
)

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join("data", "cache", "quality_setup_result.json")
MASTER_TICKERS_FILE = os.path.join("data", "idx_master_tickers.json")
FETCH_PERIOD = "2y"   # Consistent with main scan pipeline; ensures 200+ bars for EMA200

# In-memory scan status tracking
_scan_state = {
    "is_scanning": False,
    "progress": 0,
    "total": 0,
    "current_ticker": "",
    "started_at": None,
    "completed_at": None,
    "error": None
}


def _safe_round(value, decimals: int = 2):
    """Safely round numbers."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


# =========================================================================
# 1. 100-POINT COMPOSITE STOCK QUALITY SCORING (IDR ADAPTED)
# =========================================================================

def compute_stock_score(indicators: Dict, change_pct_rank: Optional[float] = None) -> Optional[Dict]:
    """
    Compute 100-point composite stock score adapted for IDX market (IDR Rupiah).
    Returns dict with score, grade, breakdown, signals, penalties, liquidity.
    """
    close = indicators.get("close")
    open_price = indicators.get("open")
    if not close or not open_price or close <= 0:
        return None

    breakdown = {}
    signals = []
    penalties = []
    total = 0

    # ── A. Trend & Momentum — 50 pts ──────────────────────────────────────
    ema20 = indicators.get("EMA20")
    ema50 = indicators.get("EMA50")
    ema200 = indicators.get("EMA200")

    # A1. EMA Trend Structure (15 pts)
    ema_pts = 0
    if ema20 and ema50 and ema200:
        if close > ema20 > ema50 > ema200:
            ema_pts = 15
            signals.append("Perfect EMA alignment (Price > 20 > 50 > 200)")
        elif close > ema20 > ema50:
            ema_pts = 10
            signals.append("EMA bullish (Price > 20 > 50)")
        elif close > ema20:
            ema_pts = 5
            signals.append("Price above EMA20")
    elif ema20 and close > ema20:
        ema_pts = 5
    breakdown["ema_trend"] = ema_pts
    total += ema_pts

    # A2. RSI Strength Zone (10 pts)
    rsi = indicators.get("RSI")
    rsi_pts = 0
    if rsi is not None:
        if 55 <= rsi <= 70:
            rsi_pts = 10
            signals.append(f"RSI {rsi:.0f} in optimal momentum zone (55–70)")
        elif 50 <= rsi < 55:
            rsi_pts = 7
        elif 70 < rsi <= 75:
            rsi_pts = 5
            signals.append(f"RSI {rsi:.0f} slightly elevated")
        elif 75 < rsi <= 78:
            rsi_pts = 2
            penalties.append(f"RSI {rsi:.0f} approaching overbought zone (-gap penalty)")
        elif 45 <= rsi < 50:
            rsi_pts = 3
    breakdown["rsi"] = rsi_pts
    total += rsi_pts

    # A3. MACD Confirmation (10 pts)
    macd_line = indicators.get("MACD.macd")
    macd_signal = indicators.get("MACD.signal")
    macd_pts = 0
    if macd_line is not None and macd_signal is not None:
        histogram = macd_line - macd_signal
        if macd_line > macd_signal and histogram > 0:
            macd_pts = 10
            signals.append("MACD bullish + histogram rising")
        elif macd_line > macd_signal:
            macd_pts = 7
            signals.append("MACD bullish crossover")
        elif histogram > 0:
            macd_pts = 4
    breakdown["macd"] = macd_pts
    total += macd_pts

    # A4. Relative Performance Rank (15 pts)
    perf_pts = 0
    if change_pct_rank is not None:
        if change_pct_rank >= 0.90:
            perf_pts = 15
            signals.append("Top 10% price performer vs universe")
        elif change_pct_rank >= 0.75:
            perf_pts = 12
            signals.append("Top 25% price performer")
        elif change_pct_rank >= 0.60:
            perf_pts = 8
        elif change_pct_rank >= 0.40:
            perf_pts = 4
    else:
        perf_pts = 8
    breakdown["relative_performance"] = perf_pts
    total += perf_pts

    # ── B. Confirmation — 20 pts ──────────────────────────────────────────
    # B5. Volume Confirmation (10 pts)
    volume = indicators.get("volume")
    vol_sma20 = indicators.get("volume.SMA20")
    vol_pts = 0
    vol_ratio = None
    if volume and vol_sma20 and vol_sma20 > 0:
        vol_ratio = volume / vol_sma20
        if vol_ratio >= 1.5:
            vol_pts = 10
            signals.append(f"Volume {vol_ratio:.1f}x above 20-day average")
        elif vol_ratio >= 1.2:
            vol_pts = 7
        elif vol_ratio >= 1.0:
            vol_pts = 4
    breakdown["volume_confirmation"] = vol_pts
    total += vol_pts

    # B6. ADX / Trend Strength (10 pts)
    adx = indicators.get("ADX")
    adx_pts = 0
    if adx is not None:
        if adx >= 30:
            adx_pts = 10
            signals.append(f"Strong trend momentum (ADX {adx:.0f})")
        elif 25 <= adx < 30:
            adx_pts = 8
        elif 20 <= adx < 25:
            adx_pts = 5
    else:
        adx_pts = 5
    breakdown["adx"] = adx_pts
    total += adx_pts

    # ── C. Risk-Adjusted Quality — 15 pts ─────────────────────────────────
    # C7. ATR% Volatility Control (10 pts)
    atr_val = indicators.get("ATR")
    atr_pct = (atr_val / close) * 100 if atr_val and close > 0 else None
    vol_ctrl_pts = 0
    if atr_pct is not None:
        if 1.0 <= atr_pct <= 3.5:
            vol_ctrl_pts = 10
            signals.append(f"ATR% {atr_pct:.1f}% (ideal swing volatility)")
        elif 3.5 < atr_pct <= 5.0:
            vol_ctrl_pts = 7
        elif 5.0 < atr_pct <= 7.0:
            vol_ctrl_pts = 4
        else:
            if atr_pct > 7.0:
                penalties.append(f"ATR% {atr_pct:.1f}% (high volatility)")
    breakdown["volatility_control"] = vol_ctrl_pts
    total += vol_ctrl_pts

    # C8. Distance & Stability (5 pts)
    stab_pts = 0
    sma200 = indicators.get("SMA200")
    if sma200 and close and sma200 > 0:
        dist_200 = ((close - sma200) / sma200) * 100
        if 0 < dist_200 <= 25:
            stab_pts += 3
        elif dist_200 > 40:
            stab_pts += 1
    bb_upper = indicators.get("BB.upper")
    bb_lower = indicators.get("BB.lower")
    bb_middle = indicators.get("BB.middle")
    if bb_upper and bb_lower and bb_middle and bb_middle > 0:
        bbw = (bb_upper - bb_lower) / bb_middle
        if bbw < 0.12:
            stab_pts += 2
        elif bbw < 0.20:
            stab_pts += 1
    stab_pts = min(5, stab_pts)
    breakdown["drawdown_stability"] = stab_pts
    total += stab_pts

    # ── D. Overlay & Supertrend — 15 pts ──────────────────────────────────
    supertrend = indicators.get("supertrend")
    super_pts = 0
    if supertrend and supertrend.get("direction") == 1:
        super_pts += 10
        signals.append("Supertrend Bullish confirm")
    elif close and ema50 and close > ema50:
        super_pts += 5

    sma50 = indicators.get("SMA50")
    if sma50 and sma200 and sma50 > sma200:
        super_pts += 5
        signals.append("Golden Cross (SMA50 > SMA200)")

    super_pts = min(15, super_pts)
    breakdown["supertrend_overlay"] = super_pts
    total += super_pts

    # ── Bonuses / Penalties ───────────────────────────────────────────────
    bonus = 0
    change_pct = ((close - open_price) / open_price) * 100 if open_price else 0.0

    if vol_ratio and vol_ratio >= 1.5 and change_pct > 2.0:
        bonus += 3
        signals.append("Volume surge with price expansion")

    # Donchian Breakout confirmation (+3 bonus)
    donchian_data = indicators.get("donchian", {})
    don_upper = donchian_data.get("upper") if donchian_data else None
    if don_upper and close >= don_upper:
        bonus += 3
        signals.append(f"Donchian 20 Breakout (close >= {_safe_round(don_upper, 0)})")

    if ema200 and close < ema200:
        bonus -= 10
        penalties.append("Price below EMA200 (-10)")

    if rsi is not None and rsi > 78:
        bonus -= 5
        penalties.append(f"RSI {rsi:.0f} extreme overbought (-5)")

    if vol_ratio is not None and vol_ratio < 0.4:
        bonus -= 8
        penalties.append("Dry trading volume (-8)")

    # ── Liquidity Assessment (IDR Rupiah Standard) ────────────────────────
    avg_vol = vol_sma20 if vol_sma20 and vol_sma20 > 0 else (volume if volume else 0)
    avg_turnover_idr = avg_vol * close
    liquidity_ok = True
    liquidity_cap = None
    liquidity_warnings = []

    # Hard filters for IDX:
    # 1. Turnover < Rp 200 Juta = dead illiquid
    if avg_turnover_idr < 200_000_000:
        bonus -= 20
        penalties.append(f"Low turnover Rp {avg_turnover_idr/1e6:.0f} Jt/day (-20)")
        liquidity_ok = False
        liquidity_cap = "Avoid"
        liquidity_warnings.append("Turnover < Rp 200 Jt")
    elif avg_turnover_idr < 500_000_000:
        bonus -= 10
        penalties.append(f"Moderate turnover Rp {avg_turnover_idr/1e6:.0f} Jt/day (-10)")
        liquidity_ok = False
        liquidity_cap = "Watchlist"
        liquidity_warnings.append("Turnover < Rp 500 Jt")
    elif avg_turnover_idr < 1_000_000_000:
        bonus -= 4

    # 2. Volume in lot (< 5.000 lot/day is thin)
    avg_lot = avg_vol / 100.0
    if avg_lot < 5000:
        bonus -= 10
        penalties.append(f"Thin volume {avg_lot:,.0f} lot/day (-10)")
        liquidity_ok = False
        if liquidity_cap is None:
            liquidity_cap = "Watchlist"
        liquidity_warnings.append("Volume < 5.000 lot")

    # 3. Current volume == 0
    if volume is not None and volume == 0:
        bonus -= 15
        penalties.append("Zero trading activity today (-15)")
        liquidity_ok = False
        liquidity_cap = "Avoid"
        liquidity_warnings.append("Zero volume today")

    final_score = max(0, min(100, total + bonus))

    # Grade determination
    grade_order = ["Avoid", "Watchlist", "Strong", "Elite"]
    if final_score >= 85:
        grade = "Elite"
    elif final_score >= 70:
        grade = "Strong"
    elif final_score >= 55:
        grade = "Watchlist"
    else:
        grade = "Avoid"

    if liquidity_cap and grade_order.index(grade) > grade_order.index(liquidity_cap):
        orig_grade = grade
        grade = liquidity_cap
        penalties.append(f"Grade capped {orig_grade} -> {grade} (liquidity constraint)")

    return {
        "score": int(final_score),
        "grade": grade,
        "change_pct": _safe_round(change_pct, 2),
        "breakdown": breakdown,
        "signals": signals,
        "penalties": penalties,
        "liquidity": {
            "avg_turnover_idr": _safe_round(avg_turnover_idr, 0),
            "avg_volume_lot": _safe_round(avg_lot, 0),
            "current_volume_lot": _safe_round(volume / 100.0 if volume else 0, 0),
            "liquidity_ok": liquidity_ok,
            "warnings": liquidity_warnings
        }
    }


# =========================================================================
# 2. TRADE SETUP & SCENARIOS (PULLBACK vs BREAKOUT)
# =========================================================================

def compute_trade_setup(indicators: Dict, recent_highs: List[float], recent_lows: List[float], fib_levels: Optional[Dict] = None) -> Optional[Dict]:
    """
    Generate actionable trade setups (Pullback vs Breakout),
    anchoring Entry, Adaptive Stop Loss (1.5x - 2.0x ATR, min -3% floor),
    Resistance-driven Target 1/2, and dynamic Risk/Reward ratio.
    """
    close = indicators.get("close")
    atr = indicators.get("ATR")
    ema20 = indicators.get("EMA20")
    ema50 = indicators.get("EMA50")
    bb_upper = indicators.get("BB.upper")
    bb_lower = indicators.get("BB.lower")

    if not close or not atr or atr <= 0:
        return None

    # Identify dynamic supports & resistances
    support_candidates = []
    resistance_candidates = []

    # Recent swing points
    if recent_lows:
        swing_low = min(recent_lows[-30:]) if len(recent_lows) >= 30 else min(recent_lows)
        if swing_low < close:
            support_candidates.append(swing_low)
    if recent_highs:
        swing_high = max(recent_highs[-30:]) if len(recent_highs) >= 30 else max(recent_highs)
        if swing_high > close:
            resistance_candidates.append(swing_high)

    # EMAs
    for em in [ema20, ema50]:
        if em and em < close:
            support_candidates.append(em)
        elif em and em > close:
            resistance_candidates.append(em)

    # Bollinger Bands
    if bb_lower and bb_lower < close:
        support_candidates.append(bb_lower)
    if bb_upper and bb_upper > close:
        resistance_candidates.append(bb_upper)

    # Donchian Channels (Upper Resistance, Lower Support)
    donchian = indicators.get("donchian") or {}
    donchian_upper = donchian.get("upper")
    donchian_lower = donchian.get("lower")
    if donchian_upper and donchian_upper > close:
        resistance_candidates.append(donchian_upper)
    if donchian_lower and donchian_lower < close:
        support_candidates.append(donchian_lower)

    # Fibonacci Extension (Resistance) & Retracement (Support)
    if fib_levels:
        for ext_key in ["ext_1272", "ext_1618"]:
            ext_val = fib_levels.get(ext_key)
            if ext_val and ext_val > close:
                resistance_candidates.append(ext_val)
        gp = fib_levels.get("golden_pocket")
        if gp and gp < close:
            support_candidates.append(gp)
        f500 = fib_levels.get("fib_500")
        if f500 and f500 < close:
            support_candidates.append(f500)

    all_supports = sorted(list(set(_safe_round(s, 0) for s in support_candidates if s and s < close)), reverse=True)
    all_resistances = sorted(list(set(_safe_round(r, 0) for r in resistance_candidates if r and r > close)))

    supports = all_supports[:5]
    resistances = all_resistances[:5]

    # Breakout Entry: Nearest resistance
    if resistances:
        breakout_entry = resistances[0]
        breakout_entry_source = "Nearest Resistance"
    else:
        breakout_entry = _safe_round(close * 1.02, 0)
        breakout_entry_source = "Fallback +2%"

    # Pullback Entry priority: EMA20 > Golden Pocket 61.8% > Fib 50% > Nearest Support
    pullback_candidates = []
    if ema20 and ema20 < close:
        pullback_candidates.append(("EMA20", _safe_round(ema20, 0)))
    if fib_levels and fib_levels.get("golden_pocket") and fib_levels["golden_pocket"] < close:
        pullback_candidates.append(("Golden Pocket 61.8%", _safe_round(fib_levels["golden_pocket"], 0)))
    if fib_levels and fib_levels.get("fib_500") and fib_levels["fib_500"] < close:
        pullback_candidates.append(("Fib 50%", _safe_round(fib_levels["fib_500"], 0)))
    if supports:
        pullback_candidates.append(("Dynamic Support", supports[0]))

    if pullback_candidates:
        pullback_entry_source = pullback_candidates[0][0]
        pullback_entry = pullback_candidates[0][1]
    else:
        pullback_entry_source = "Fallback -3%"
        pullback_entry = _safe_round(close * 0.97, 0)

    scenarios = {}

    def _build_scenario(entry_price: float, mode: str, entry_src: str):
        if not entry_price or entry_price <= 0:
            return None

        # Adaptive Stop Loss based on volatility
        atr_pct = (atr / entry_price) * 100.0 if entry_price > 0 else 0
        atr_mult = 1.5 if atr_pct <= 3.5 else 2.0

        sl_cand = [entry_price - atr_mult * atr]
        sups_under = [s for s in all_supports if s < entry_price]
        if sups_under:
            sl_cand.append(sups_under[0] - 0.5 * atr)
        stop = max(sl_cand)

        # Floor: SL minimum -3% di bawah entry (tidak boleh lebih dangkal dari -3%)
        sl_floor = entry_price * 0.97
        if stop > sl_floor:
            stop = sl_floor

        if stop >= entry_price or (entry_price - stop) <= 0:
            stop = entry_price - atr_mult * atr
        if stop >= entry_price:
            stop = entry_price * 0.95

        risk = entry_price - stop
        risk_pct = (risk / entry_price) * 100.0

        # Targets based on real resistance (with minimum R:R >= 1.0)
        res_above = [r for r in all_resistances if r > entry_price]
        valid_targets = [r for r in res_above if (r - entry_price) >= 1.0 * risk]

        if len(valid_targets) >= 2:
            t1 = valid_targets[0]
            t2 = valid_targets[1]
        elif len(valid_targets) == 1:
            t1 = valid_targets[0]
            t2 = max(entry_price + 2.5 * risk, t1 + 1.0 * risk)
        else:
            t1 = entry_price + 1.5 * risk
            t2 = entry_price + 2.5 * risk

        # Ensure t2 > t1
        if t2 <= t1:
            t2 = t1 + 1.0 * risk

        rr_1 = (t1 - entry_price) / risk if risk > 0 else 1.0
        rr_2 = (t2 - entry_price) / risk if risk > 0 else 2.0

        return {
            "mode": mode,
            "entry": _safe_round(entry_price, 0),
            "entry_source": entry_src,
            "stop_loss": _safe_round(stop, 0),
            "stop_loss_pct": _safe_round(risk_pct, 1),
            "target_1": _safe_round(t1, 0),
            "target_2": _safe_round(t2, 0),
            "rr_target_1": _safe_round(rr_1, 1),
            "rr_target_2": _safe_round(rr_2, 1)
        }

    sc_breakout = _build_scenario(breakout_entry, "Breakout", breakout_entry_source)
    sc_pullback = _build_scenario(pullback_entry, "Pullback", pullback_entry_source)

    dist_res_pct = ((breakout_entry - close) / close) * 100 if breakout_entry else 99
    dist_ema_pct = abs((close - pullback_entry) / close) * 100 if pullback_entry else 99

    if sc_breakout:
        sc_breakout["distance_pct"] = _safe_round(dist_res_pct, 1)
        scenarios["breakout"] = sc_breakout
    if sc_pullback:
        sc_pullback["distance_pct"] = _safe_round(dist_ema_pct, 1)
        scenarios["pullback"] = sc_pullback

    # Determine primary setup based on proximity
    dist_pct = 0.0
    if dist_res_pct <= 3.0:
        primary_name = "breakout"
        setup_type = "Breakout Ready"
        dist_pct = dist_res_pct
    elif dist_ema_pct <= 2.5:
        primary_name = "pullback"
        setup_type = "Pullback Swing"
        dist_pct = dist_ema_pct
    else:
        if dist_res_pct < dist_ema_pct:
            primary_name = "breakout"
            dist_pct = dist_res_pct
            setup_type = "Breakout Jauh" if dist_res_pct > 8.0 else "Breakout Setup"
        else:
            primary_name = "pullback"
            dist_pct = dist_ema_pct
            setup_type = "Pullback Setup"

    if primary_name == "breakout" and dist_res_pct > 8.0:
        setup_type = "Breakout Jauh"

    primary = scenarios.get(primary_name) or scenarios.get("breakout") or scenarios.get("pullback")

    return {
        "setup_type": setup_type,
        "primary_scenario": primary_name,
        "entry": primary["entry"] if primary else _safe_round(close, 0),
        "entry_source": primary.get("entry_source", "") if primary else "",
        "distance_pct": _safe_round(dist_pct, 1),
        "stop_loss": primary["stop_loss"] if primary else _safe_round(close * 0.95, 0),
        "stop_loss_pct": primary["stop_loss_pct"] if primary else 5.0,
        "target_1": primary["target_1"] if primary else _safe_round(close * 1.05, 0),
        "target_2": primary["target_2"] if primary else _safe_round(close * 1.10, 0),
        "risk_reward": primary["rr_target_2"] if primary else 2.0,
        "scenarios": scenarios,
        "supports": supports,
        "resistances": resistances
    }


# =========================================================================
# 3. FIBONACCI RETRACEMENT & EXTENSION LEVELS
# =========================================================================

def compute_fibonacci_levels(swing_high: float, swing_low: float, trend: str = "uptrend") -> Dict:
    """Calculate Fibonacci retracement and extension levels."""
    diff = swing_high - swing_low
    if diff <= 0:
        return {}

    levels = {}
    # Retracements: 0.236, 0.382, 0.5, 0.618 (Golden Pocket), 0.786
    ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
    for r in ratios:
        if trend == "uptrend":
            # Retracement falls from high
            val = swing_high - (diff * r)
        else:
            # Retracement bounces from low
            val = swing_low + (diff * r)
        levels[f"fib_{int(r*1000)}"] = _safe_round(val, 0)

    # Extensions: 1.272, 1.618, 2.618
    ext_ratios = [1.272, 1.618, 2.618]
    for er in ext_ratios:
        if trend == "uptrend":
            val = swing_high + (diff * (er - 1.0))
        else:
            val = swing_low - (diff * (er - 1.0))
        levels[f"ext_{int(er*1000)}"] = _safe_round(val, 0)

    levels["golden_pocket"] = levels.get("fib_618")
    levels["swing_high"] = _safe_round(swing_high, 0)
    levels["swing_low"] = _safe_round(swing_low, 0)
    levels["trend"] = trend

    return levels


# =========================================================================
# 4. CANDLE & MARKET STRUCTURE
# =========================================================================

def _detect_market_structure(open_p: float, high: float, low: float, close: float) -> Dict:
    """Analyze candle body strength and wick proportions."""
    if high <= low:
        return {"type": "Flat", "strength": "Weak", "body_pct": 0}
    total_range = high - low
    body = abs(close - open_p)
    body_pct = (body / total_range) * 100.0 if total_range > 0 else 0

    candle_type = "Bullish" if close > open_p else ("Bearish" if close < open_p else "Doji")
    strength = "Strong" if body_pct >= 65 else ("Moderate" if body_pct >= 40 else "Weak")

    upper_wick = (high - max(open_p, close)) / total_range * 100.0 if total_range > 0 else 0
    lower_wick = (min(open_p, close) - low) / total_range * 100.0 if total_range > 0 else 0

    return {
        "candle_type": candle_type,
        "strength": strength,
        "body_pct": _safe_round(body_pct, 1),
        "upper_wick_pct": _safe_round(upper_wick, 1),
        "lower_wick_pct": _safe_round(lower_wick, 1)
    }


# =========================================================================
# 5. WORKER EVALUATOR PER TICKER
# =========================================================================

def evaluate_ticker_quality(
    ticker: str,
    meta: Dict,
    df: pd.DataFrame,
    change_pct_rank: Optional[float] = None
) -> Optional[Dict]:
    """Calculate all technical indicators and run quality scoring on a ticker dataframe."""
    try:
        if df is None or len(df) < 50:
            return None

        # Clean series
        closes = df["Close"].astype(float).tolist()
        highs = df["High"].astype(float).tolist()
        lows = df["Low"].astype(float).tolist()
        opens = df["Open"].astype(float).tolist()
        volumes = df["Volume"].astype(float).tolist()

        n = len(closes)
        if n < 50:
            return None

        # 1. Indicator arrays
        ema20_arr = calc_ema(closes, 20)
        ema50_arr = calc_ema(closes, 50)
        ema200_arr = calc_ema(closes, 200)
        # Guard: Mark EMA200 unreliable if fewer than 220 bars available
        _ema200_valid = n >= 220
        if not _ema200_valid:
            logger.debug(f"[{ticker}] Only {n} bars — EMA200 may be unreliable")

        sma20_arr = calc_sma(closes, 20)
        sma50_arr = calc_sma(closes, 50)
        sma200_arr = calc_sma(closes, 200)
        rsi_arr = calc_rsi(closes, 14)
        bb = calc_bollinger(closes, 20, 2.0)
        macd = calc_macd(closes, 12, 26, 9)
        atr_arr = calc_atr(highs, lows, closes, 14)
        supertrend = calc_supertrend(highs, lows, closes, 10, 3.0)
        donchian = calc_donchian(highs, lows, 20)
        vol_sma20_arr = calc_sma(volumes, 20)

        # ADX via proper Wilder's smoothing
        adx_arr = calc_adx(highs, lows, closes, 14)
        adx_val = next((v for v in reversed(adx_arr) if v is not None), 25.0)

        # Build indicators dict for current bar
        curr_ind = {
            "close": closes[-1],
            "open": opens[-1],
            "high": highs[-1],
            "low": lows[-1],
            "volume": volumes[-1],
            "volume.SMA20": vol_sma20_arr[-1] if vol_sma20_arr else None,
            "EMA20": ema20_arr[-1] if ema20_arr else None,
            "EMA50": ema50_arr[-1] if ema50_arr else None,
            "EMA200": ema200_arr[-1] if ema200_arr else None,
            "SMA20": sma20_arr[-1] if sma20_arr else None,
            "SMA50": sma50_arr[-1] if sma50_arr else None,
            "SMA200": sma200_arr[-1] if sma200_arr else None,
            "RSI": rsi_arr[-1] if rsi_arr else None,
            "BB.upper": bb["upper"][-1] if bb["upper"] else None,
            "BB.middle": bb["middle"][-1] if bb["middle"] else None,
            "BB.lower": bb["lower"][-1] if bb["lower"] else None,
            "MACD.macd": macd["macd"][-1] if macd["macd"] else None,
            "MACD.signal": macd["signal"][-1] if macd["signal"] else None,
            "ATR": atr_arr[-1] if atr_arr else None,
            "ADX": adx_val,
            "supertrend": {
                "direction": supertrend["direction"][-1] if supertrend["direction"] else None,
                "upper": supertrend["upper"][-1] if supertrend["upper"] else None,
                "lower": supertrend["lower"][-1] if supertrend["lower"] else None
            },
            "donchian": {
                "upper": donchian["upper"][-1] if donchian["upper"] else None,
                "lower": donchian["lower"][-1] if donchian["lower"] else None,
                "middle": donchian.get("middle", [None])[-1] if donchian.get("middle") else None
            }
        }

        # 2. Score
        score_res = compute_stock_score(curr_ind, change_pct_rank=change_pct_rank)
        if not score_res:
            return None

        # Filter: Only keep Elite (>=85) and Strong (>=70)
        if score_res["score"] < 70:
            return None

        # 3. Fibonacci Levels (over last 60 bars)
        lookback_fib = min(n, 60)
        f_high = max(highs[-lookback_fib:])
        f_low = min(lows[-lookback_fib:])
        trend_dir = "uptrend" if closes[-1] >= ((f_high + f_low) / 2.0) else "downtrend"
        fib_levels = compute_fibonacci_levels(f_high, f_low, trend_dir)

        # 4. Trade Setup (with Fib levels integrated)
        trade_setup = compute_trade_setup(curr_ind, highs, lows, fib_levels=fib_levels)

        # 5. Structure & Candle
        structure = _detect_market_structure(opens[-1], highs[-1], lows[-1], closes[-1])

        # Supertrend text
        st_dir = curr_ind["supertrend"]["direction"]
        st_label = "BULLISH" if st_dir == 1 else ("BEARISH" if st_dir == -1 else "NEUTRAL")

        # Compile response
        return {
            "ticker": ticker,
            "name": meta.get("name", ticker),
            "sector": meta.get("sector", "General"),
            "price": _safe_round(closes[-1], 0),
            "change_pct": score_res["change_pct"],
            "score": score_res["score"],
            "grade": score_res["grade"],
            "setup_type": trade_setup["setup_type"] if trade_setup else "Swing Setup",
            "primary_scenario": trade_setup["primary_scenario"] if trade_setup else "breakout",
            "entry_source": trade_setup["entry_source"] if trade_setup else "",
            "distance_pct": trade_setup["distance_pct"] if trade_setup else 0.0,
            "supertrend": st_label,
            "entry": trade_setup["entry"] if trade_setup else closes[-1],
            "stop_loss": trade_setup["stop_loss"] if trade_setup else _safe_round(closes[-1] * 0.95, 0),
            "stop_loss_pct": trade_setup["stop_loss_pct"] if trade_setup else 5.0,
            "target_1": trade_setup["target_1"] if trade_setup else _safe_round(closes[-1] * 1.05, 0),
            "target_2": trade_setup["target_2"] if trade_setup else _safe_round(closes[-1] * 1.10, 0),
            "risk_reward": trade_setup["risk_reward"] if trade_setup else 2.0,
            "rsi": _safe_round(curr_ind["RSI"], 1),
            "atr_pct": _safe_round((curr_ind["ATR"] / closes[-1]) * 100 if curr_ind["ATR"] else 0, 1),
            "volume_ratio": _safe_round((curr_ind["volume"] / curr_ind["volume.SMA20"]) if curr_ind.get("volume.SMA20") else 1.0, 1),
            "turnover_idr": score_res["liquidity"]["avg_turnover_idr"],
            "score_breakdown": score_res["breakdown"],
            "signals": score_res["signals"],
            "penalties": score_res["penalties"],
            "fibonacci": fib_levels,
            "structure": structure,
            "supports": trade_setup["supports"] if trade_setup else [],
            "resistances": trade_setup["resistances"] if trade_setup else [],
            "scenarios": trade_setup["scenarios"] if trade_setup else {}
        }
    except Exception as e:
        logger.debug(f"Error evaluating {ticker}: {e}")
        return None


# =========================================================================
# 6. SCAN RUNNER (941 TICKERS PARALLEL BATCH)
# =========================================================================

def load_master_universe() -> Dict[str, Dict]:
    """Load the full 941 IDX stock list."""
    universe = {}
    if os.path.exists(MASTER_TICKERS_FILE):
        try:
            with open(MASTER_TICKERS_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
                for it in items:
                    t = it.get("ticker", "").strip().upper()
                    if t:
                        universe[t] = {
                            "name": it.get("name", t),
                            "sector": it.get("sector", "General")
                        }
        except Exception as e:
            logger.error(f"Failed to load master tickers JSON: {e}")

    # Fallback to 205 tickers CSV if json fails
    if not universe and os.path.exists("data/idx_tickers.csv"):
        try:
            df = pd.read_csv("data/idx_tickers.csv")
            for _, r in df.iterrows():
                t = str(r["ticker"]).strip().upper()
                universe[t] = {
                    "name": str(r.get("name", t)),
                    "sector": str(r.get("sector", "General"))
                }
        except Exception as e:
            logger.error(f"Fallback CSV failed: {e}")

    return universe


def _compute_30d_return(df: pd.DataFrame) -> Optional[float]:
    """Compute 30-day (approx 20-30 trading days) price return for cross-universe ranking."""
    try:
        closes = df["Close"].dropna().astype(float)
        if len(closes) < 20:
            return None
        lookback = min(30, len(closes) - 1)
        c_end = float(closes.iloc[-1])
        c_start = float(closes.iloc[-1 - lookback])
        if c_start <= 0:
            return None
        return float((c_end - c_start) / c_start * 100.0)
    except Exception:
        return None


def run_quality_scan(max_workers: int = 16, preloaded_data: Optional[Dict[str, pd.DataFrame]] = None) -> Dict:
    """
    Run the full quality setup scan over the 941 IDX universe.
    Returns summary results and saves to cache JSON.
    """
    global _scan_state
    _scan_state["is_scanning"] = True
    _scan_state["started_at"] = datetime.now().isoformat()
    _scan_state["progress"] = 0
    _scan_state["error"] = None

    universe = load_master_universe()
    tickers = list(preloaded_data.keys()) if preloaded_data is not None else list(universe.keys())
    total = len(tickers)
    _scan_state["total"] = total

    logger.info(f"🚀 Starting Quality Setup Scan for {total} IDX tickers with {max_workers} threads...")

    # Data dictionary: either preloaded or fetched
    data_map: Dict[str, pd.DataFrame] = {}
    if preloaded_data is not None:
        data_map = dict(preloaded_data)
    else:
        # Standalone mode: fetch data first across threads
        def _fetch_one(t: str):
            try:
                symbol = f"{t}.JK"
                stock = yf.Ticker(symbol)
                df = stock.history(period=FETCH_PERIOD, auto_adjust=False)
                if df is not None and not df.empty and len(df) >= 50:
                    df = df.dropna(subset=["Close"])
                    return t, df
            except Exception:
                pass
            return t, None

        logger.info(f"Fetching {total} tickers with period={FETCH_PERIOD}...")
        fetch_done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(_fetch_one, t): t for t in tickers}
            for future in as_completed(future_map):
                fetch_done += 1
                _scan_state["progress"] = int((fetch_done / max(total, 1)) * 50)
                t, df = future.result()
                if df is not None:
                    data_map[t] = df

    # ── PRE-PASS: Compute 30d returns for universe ranking ─────────────
    logger.info("Computing 30d return ranks across universe...")
    returns_map: Dict[str, float] = {}
    for t, df in data_map.items():
        ret = _compute_30d_return(df)
        if ret is not None:
            returns_map[t] = ret

    # Build percentile rank map (0.0 – 1.0)
    rank_map: Dict[str, float] = {}
    if returns_map:
        sorted_tickers = sorted(returns_map, key=lambda x: returns_map[x])
        n_ranked = len(sorted_tickers)
        for i, t in enumerate(sorted_tickers):
            rank_map[t] = i / (n_ranked - 1) if n_ranked > 1 else 0.5
    logger.info(f"Ranked {len(rank_map)} tickers by 30d return.")

    # ── EVALUATION PASS: Evaluate with rank ─────────────────────────────
    passed_results = []
    eval_done = 0
    total_to_eval = len(data_map)

    def _eval_one(t: str):
        meta = universe.get(t, {"name": t, "sector": "General"})
        df = data_map.get(t)
        if df is None:
            return None
        rank = rank_map.get(t)
        return evaluate_ticker_quality(t, meta, df, change_pct_rank=rank)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_eval_one, t): t for t in data_map.keys()}
        for future in as_completed(future_map):
            eval_done += 1
            if preloaded_data is not None:
                _scan_state["progress"] = int((eval_done / max(total, 1)) * 100)
            else:
                _scan_state["progress"] = 50 + int((eval_done / max(total_to_eval, 1)) * 50)
            res = future.result()
            if res:
                passed_results.append(res)

    # Sort results by score descending, then risk_reward descending
    passed_results.sort(key=lambda x: (x["score"], x.get("risk_reward", 0)), reverse=True)

    # Statistics
    elite_count = sum(1 for x in passed_results if x["grade"] == "Elite")
    strong_count = sum(1 for x in passed_results if x["grade"] == "Strong")
    breakout_count = sum(1 for x in passed_results if "Breakout" in x.get("setup_type", ""))
    pullback_count = sum(1 for x in passed_results if "Pullback" in x.get("setup_type", ""))
    avg_rr = _safe_round(sum(x.get("risk_reward", 0) for x in passed_results) / len(passed_results), 1) if passed_results else 0.0

    now_dt = datetime.now()
    output = {
        "status": "success",
        "scan_time": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_time_iso": now_dt.isoformat(),
        "expires_at_iso": (now_dt + timedelta(hours=24)).isoformat(),
        "fetch_period": FETCH_PERIOD,
        "scan_mode": "preloaded" if preloaded_data is not None else "standalone",
        "total_scanned": total,
        "passed_count": len(passed_results),
        "elite_count": elite_count,
        "strong_count": strong_count,
        "breakout_count": breakout_count,
        "pullback_count": pullback_count,
        "avg_rr": avg_rr,
        "data": passed_results
    }

    # Save to cache
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        logger.info(f"✅ Quality Setup scan finished: {len(passed_results)}/{total} passed. Saved to {CACHE_FILE}")
    except Exception as e:
        logger.error(f"Failed to save quality setup cache: {e}")

    _scan_state["is_scanning"] = False
    _scan_state["progress"] = total
    _scan_state["completed_at"] = now_dt.isoformat()
    return output


def get_cached_quality_results() -> Optional[Dict]:
    """Retrieve the cached scan results from disk."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {CACHE_FILE}: {e}")
    return None


def get_quality_scan_status() -> Dict:
    """Return the current scanning progress status."""
    return _scan_state


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Quality Screener evaluation on sample tickers...")
    u = load_master_universe()
    sample_tickers = ["RAJA", "BBCA", "MEDC", "BRPT", "ASII"]
    for sym in sample_tickers:
        meta = u.get(sym, {"name": sym, "sector": "Energy"})
        t = yf.Ticker(f"{sym}.JK")
        hist = t.history(period=FETCH_PERIOD)
        res = evaluate_ticker_quality(sym, meta, hist)
        if res:
            print(f"[{res['grade']}] {sym} - Score: {res['score']} | Setup: {res['setup_type']} | R:R: {res['risk_reward']}")
        else:
            print(f"[-] {sym} did not meet Elite/Strong threshold (Score < 70).")
