import os
import json
import logging
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketRegimeEvaluator:
    """
    Evaluator for General Market Health (IHSG / ^JKSE) based on Mark Minervini
    and William O'Neil market regime classification rules.
    """
    def __init__(self, benchmark_symbol="^JKSE", cache_dir="data/cache"):
        self.benchmark_symbol = benchmark_symbol
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "market_regime.json")

    def evaluate(self, df=None, period="2y", force_fetch=False):
        """
        Evaluate market regime using benchmark dataframe or by downloading ^JKSE.
        Returns a dictionary with comprehensive status, levels, and exposure guidance.
        """
        if df is None or df.empty or force_fetch:
            try:
                logger.info(f"Downloading benchmark {self.benchmark_symbol} for market regime...")
                ticker = yf.Ticker(self.benchmark_symbol)
                df = ticker.history(period=period, auto_adjust=False)
            except Exception as e:
                logger.error(f"Failed to fetch {self.benchmark_symbol}: {e}")
                return self.get_cached_or_default()

        if df is None or df.empty:
            return self.get_cached_or_default()

        df = df.dropna(subset=['Close'])
        if len(df) < 200:
            logger.warning("Insufficient benchmark bars for market regime evaluation (<200).")
            return self.get_cached_or_default()

        close = df['Close']
        curr_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else curr_close
        chg_pts = curr_close - prev_close
        chg_pct = (chg_pts / prev_close) * 100.0 if prev_close > 0 else 0.0

        # Moving Averages
        ma20_s = close.rolling(20).mean()
        ma50_s = close.rolling(50).mean()
        ma200_s = close.rolling(200).mean()

        m20 = float(ma20_s.iloc[-1])
        m50 = float(ma50_s.iloc[-1])
        m200 = float(ma200_s.iloc[-1])

        # Slope of MA50 (over last 20 bars)
        m50_prev20 = float(ma50_s.iloc[-21]) if len(ma50_s) >= 21 else m50
        m50_slope_up = bool(m50 > m50_prev20)

        # Distances to MAs
        dist_ma20_pct = ((curr_close - m20) / m20) * 100.0 if m20 > 0 else 0.0
        dist_ma50_pct = ((curr_close - m50) / m50) * 100.0 if m50 > 0 else 0.0
        dist_ma200_pct = ((curr_close - m200) / m200) * 100.0 if m200 > 0 else 0.0

        # Regime Logic
        if curr_close > m50 and m50 > m200 and curr_close > m200 and m50_slope_up:
            regime = "CONFIRMED_UPTREND"
            regime_label = "CONFIRMED UPTREND"
            color = "green"
            badge_class = "badge-regime-green"
            exposure_pct = 100
            exposure_label = "Exposure 100% (Agresif Buy Breakout)"
            action_desc = "IHSG berada di atas MA50 & MA200 dengan tren menanjak kuat. Pasar kondusif untuk membeli saham Stage 2 breakout."
        elif curr_close > m200:
            regime = "UPTREND_PRESSURE"
            regime_label = "UPTREND UNDER PRESSURE"
            color = "yellow"
            badge_class = "badge-regime-yellow"
            exposure_pct = 50
            exposure_label = "Exposure 50% (Selektif & Stop Loss Ketat)"
            action_desc = "IHSG di bawah MA50 atau mengalami koreksi jangka pendek, namun masih di atas MA200. Bersikap selektif, kurangi alokasi modal dan perketat stop loss."
        else:
            regime = "MARKET_CORRECTION"
            regime_label = "MARKET IN CORRECTION"
            color = "red"
            badge_class = "badge-regime-red"
            exposure_pct = 0
            exposure_label = "Cash is King / 0-25% Defensive"
            action_desc = "IHSG berada di bawah MA200 (fase bearish / koreksi tajam). Risiko false breakout sangat tinggi, utamakan memegang uang tunai (cash)."

        payload = {
            "symbol": self.benchmark_symbol,
            "name": "Indeks Harga Saham Gabungan (IHSG)",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_close": round(curr_close, 2),
            "prev_close": round(prev_close, 2),
            "chg_pts": round(chg_pts, 2),
            "chg_pct": round(chg_pct, 2),
            "ma20": round(m20, 2),
            "ma50": round(m50, 2),
            "ma200": round(m200, 2),
            "dist_ma20_pct": round(dist_ma20_pct, 2),
            "dist_ma50_pct": round(dist_ma50_pct, 2),
            "dist_ma200_pct": round(dist_ma200_pct, 2),
            "m50_slope_up": m50_slope_up,
            "regime": regime,
            "regime_label": regime_label,
            "color": color,
            "badge_class": badge_class,
            "exposure_pct": exposure_pct,
            "exposure_label": exposure_label,
            "action_desc": action_desc
        }

        self.save_cache(payload)
        return payload

    def save_cache(self, payload):
        """Save regime evaluation to cache JSON."""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save market regime cache: {e}")

    def get_cached_or_default(self):
        """Load from cache or return neutral fallback."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read market regime cache: {e}")

        return {
            "symbol": self.benchmark_symbol,
            "name": "Indeks Harga Saham Gabungan (IHSG)",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_close": 0.0,
            "prev_close": 0.0,
            "chg_pts": 0.0,
            "chg_pct": 0.0,
            "ma20": 0.0,
            "ma50": 0.0,
            "ma200": 0.0,
            "dist_ma20_pct": 0.0,
            "dist_ma50_pct": 0.0,
            "dist_ma200_pct": 0.0,
            "m50_slope_up": False,
            "regime": "UPTREND_PRESSURE",
            "regime_label": "DATA TERBATAS",
            "color": "yellow",
            "badge_class": "badge-regime-yellow",
            "exposure_pct": 50,
            "exposure_label": "Exposure 50%",
            "action_desc": "Menunggu kalkulasi data bursa terkini."
        }
