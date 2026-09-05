import numpy as np
import pandas as pd
import logging
from .data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

class PreBreakoutCalculator:
    """
    Screener for Pre-Breakout / Early Stage Bullish Momentum Setups.
    Target: Stocks forming a sound consolidation base with building demand,
            volatility contraction (VCP), volume dry-up (VDU), positive momentum,
            and tight proximity to 50-day resistance.
    """
    def __init__(self, tickers_csv_path="data/idx_tickers.csv", min_turnover_20d=500_000_000):
        self.fetcher = DataFetcher(tickers_csv_path)
        self.min_turnover_20d = min_turnover_20d  # Default Rp 500 Juta avg daily turnover

    @staticmethod
    def get_idx_tick(price):
        """
        Return the official Indonesia Stock Exchange (IDX / BEI) minimum tick size.
        - Price < 200: Rp 1
        - Price 200 - 500: Rp 2
        - Price 500 - 2,000: Rp 5
        - Price 2,000 - 5,000: Rp 10
        - Price >= 5,000: Rp 25
        """
        if price < 200:
            return 1
        elif price < 500:
            return 2
        elif price < 2000:
            return 5
        elif price < 5000:
            return 10
        else:
            return 25

    @staticmethod
    def compute_rsi(series, period=14):
        """Compute standard RSI using Wilder's RMA (Exponential Moving Average)."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        avg_gain = gain.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

    @staticmethod
    def compute_macd(series, fast=12, slow=26, signal=9):
        """Compute MACD Line, Signal Line, and Histogram."""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return macd_line, signal_line, hist

    @staticmethod
    def compute_atr(df, period=14):
        """Compute Average True Range (ATR)."""
        high = df['High']
        low = df['Low']
        close = df['Close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def evaluate_stock(self, ticker, df):
        """
        Evaluate a single stock against the 7 Pre-Breakout Criteria,
        VCP Volatility Contraction, Volume Dry-Up (VDU), and calculate
        automated Pivot Buy, Dynamic Stop Loss, and Risk-to-Reward targets.
        """
        if df is None or df.empty:
            return None

        df = df.dropna(subset=['Close'])
        if len(df) < 50:
            return None

        close = df['Close']
        high = df['High'] if 'High' in df else close
        low = df['Low'] if 'Low' in df else close
        volume = df['Volume'] if 'Volume' in df else pd.Series([0]*len(df), index=df.index)

        curr_price = float(close.iloc[-1])
        if curr_price <= 0 or np.isnan(curr_price):
            return None

        # -------------------------------------------------------------
        # 0. Hard Filter: Liquidity (Avg 20D Daily Turnover >= Rp 500 Juta)
        # -------------------------------------------------------------
        daily_turnover = close * volume
        avg_turnover_20d = float(daily_turnover.iloc[-20:].mean()) if len(daily_turnover) >= 20 else 0.0

        if avg_turnover_20d < self.min_turnover_20d:
            return None

        # -------------------------------------------------------------
        # 1. Moving Averages (EMA 20 & EMA 50)
        # -------------------------------------------------------------
        ema20_series = close.ewm(span=20, adjust=False).mean()
        ema50_series = close.ewm(span=50, adjust=False).mean()

        m20 = float(ema20_series.iloc[-1])
        m50 = float(ema50_series.iloc[-1])

        # K1: Close > EMA 20
        k1 = bool(curr_price > m20)

        # K2: EMA 20 > EMA 50
        k2 = bool(m20 > m50)

        # -------------------------------------------------------------
        # 2. Momentum (RSI 14 & MACD)
        # -------------------------------------------------------------
        rsi_series = self.compute_rsi(close, period=14)
        curr_rsi = float(rsi_series.iloc[-1])

        # K3: RSI 50–70 (Positive Momentum, Not Yet Overbought)
        k3 = bool(50.0 <= curr_rsi <= 70.0)

        macd_line, signal_line, hist = self.compute_macd(close, fast=12, slow=26, signal=9)
        curr_macd = float(macd_line.iloc[-1])
        curr_signal = float(signal_line.iloc[-1])
        curr_hist = float(hist.iloc[-1])

        # K4: MACD Bullish (MACD Line > Signal Line)
        k4 = bool(curr_macd > curr_signal)

        # -------------------------------------------------------------
        # 3. Volume & Demand (Dual-Volume Logic: Surge or Dry-Up)
        # -------------------------------------------------------------
        recent_vol = int(volume.iloc[-1])
        avg_vol_20 = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else float(recent_vol)
        avg_vol_50 = float(volume.iloc[-50:].mean()) if len(volume) >= 50 else float(avg_vol_20)
        rvol = (recent_vol / avg_vol_20) if avg_vol_20 > 0 else 1.0

        # K5: Dual-Volume Logic:
        # A) Demand Surge: RVOL >= 1.2x (Early Accumulation / Pocket Pivot)
        # B) Supply Dry-Up: RVOL <= 0.75x (VCP Base / Supply Exhaustion at Resistance)
        is_vol_surge = bool(rvol >= 1.2)
        is_vol_dryup = bool(rvol <= 0.75)
        k5 = bool(is_vol_surge or is_vol_dryup)

        if is_vol_surge:
            vol_type = "SURGE"
            vol_label = "Demand Surge"
            k5_val = f"{rvol:.2f}x (Surge Demand ⚡)"
        elif is_vol_dryup:
            vol_type = "DRY_UP"
            vol_label = "Supply Dry-Up"
            k5_val = f"{rvol:.2f}x (VCP Dry-Up 💧)"
        else:
            vol_type = "NORMAL"
            vol_label = "Normal"
            k5_val = f"{rvol:.2f}x (Normal Volume)"

        # -------------------------------------------------------------
        # 4. Price Structure: Higher Low
        # -------------------------------------------------------------
        if len(low) >= 20:
            swing_low_recent = float(low.iloc[-10:].min())
            swing_low_prev = float(low.iloc[-20:-10].min())
            k6 = bool(swing_low_recent > swing_low_prev)
            hl_detail = f"Low10D {swing_low_recent:.0f} > Low20D {swing_low_prev:.0f}"
        else:
            k6 = False
            swing_low_recent = float(low.iloc[-1])
            swing_low_prev = float(low.iloc[0])
            hl_detail = "Data < 20 bar"

        # -------------------------------------------------------------
        # 5. Proximity to Resistance: 50-Day High (< 5%)
        # -------------------------------------------------------------
        lookback_res = min(50, len(high))
        high_50d = float(high.iloc[-lookback_res:].max())
        dist_res_pct = ((high_50d - curr_price) / high_50d) * 100.0 if high_50d > 0 else 0.0

        # K7: Distance to 50D Resistance < 5% (and price is at or below resistance)
        k7 = bool(0.0 <= dist_res_pct < 5.0)

        # -------------------------------------------------------------
        # 6. VCP Contraction & Volume Dry-Up (VDU) Index
        # -------------------------------------------------------------
        atr5_s = self.compute_atr(df, period=5)
        atr20_s = self.compute_atr(df, period=20)
        
        atr5 = float(atr5_s.iloc[-1]) if not atr5_s.empty and not np.isnan(atr5_s.iloc[-1]) else 0.0
        atr20 = float(atr20_s.iloc[-1]) if not atr20_s.empty and not np.isnan(atr20_s.iloc[-1]) else 0.0

        atr_ratio = (atr5 / atr20) if (atr20 > 0 and not np.isnan(atr20)) else 1.0
        is_vcp_tight = bool(atr_ratio <= 0.75)

        # VDU: Volume on last bar <= 60% of 50-day average
        is_vdu = bool(recent_vol <= (0.60 * avg_vol_50)) if avg_vol_50 > 0 else False

        if is_vcp_tight and is_vdu:
            vcp_badge = "VCP TIGHT + VDU 💧"
            vcp_label = "Tight Base & Volume Kering"
            vcp_class = "badge-vcp-perfect"
        elif is_vcp_tight:
            vcp_badge = "VCP TIGHT 🎯"
            vcp_label = "Volatility Squeeze"
            vcp_class = "badge-vcp-tight"
        elif is_vdu:
            vcp_badge = "VOLUME DRY-UP 💧"
            vcp_label = "Pasokan Kering"
            vcp_class = "badge-vcp-vdu"
        else:
            vcp_badge = "BASE FORMING"
            vcp_label = "Konsolidasi Standar"
            vcp_class = "badge-vcp-base"

        # -------------------------------------------------------------
        # 7. Automated Pivot Buy, Dynamic Stop Loss & R:R Calculator
        # -------------------------------------------------------------
        tick_size = self.get_idx_tick(high_50d)
        pivot_buy = round(high_50d + tick_size, 0)

        # Stop Loss: Dynamic following lowest swing low of last 10 days, capped at -7% max
        max_risk_price = round(pivot_buy * 0.93, 0)  # Max -7% risk
        if len(low) >= 10:
            base_swing_low = float(low.iloc[-10:].min())
            stop_loss = round(max(base_swing_low, max_risk_price), 0)
        else:
            stop_loss = max_risk_price

        # Fallback safeguard: Stop loss must strictly be below pivot_buy
        if stop_loss >= pivot_buy:
            stop_loss = round(pivot_buy * 0.95, 0)

        risk_pts = pivot_buy - stop_loss
        risk_pct = round(((risk_pts) / pivot_buy) * 100.0, 1)

        # Target 1 (1:2 R:R) & Target 2 (1:3 R:R)
        target_1 = round(pivot_buy + (2.0 * risk_pts), 0)
        target_2 = round(pivot_buy + (3.0 * risk_pts), 0)
        target_1_pct = round(((target_1 - pivot_buy) / pivot_buy) * 100.0, 1)

        # -------------------------------------------------------------
        # Total Score & Qualification Status
        # -------------------------------------------------------------
        criteria = [k1, k2, k3, k4, k5, k6, k7]
        total_score = sum(1 for c in criteria if c)

        # Only include stocks with score >= 5 (Quality Base or Ready)
        if total_score < 5:
            return None

        is_ready = (total_score == 7)
        status = "READY" if is_ready else "FORMING"
        status_label = "READY TO BREAKOUT" if is_ready else "FORMING BASE"

        meta = self.fetcher.get_ticker_meta(ticker)
        clean_ticker = ticker.replace(".JK", "").strip().upper()

        prev_close = float(close.iloc[-2]) if len(close) >= 2 else curr_price
        pct_change_1d = ((curr_price - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0

        return {
            'ticker': clean_ticker,
            'name': meta['name'],
            'sector': meta['sector'],
            'price': curr_price,
            'pct_change_1d': round(pct_change_1d, 2),
            'total_score': total_score,
            'status': status,
            'status_label': status_label,
            'is_ready': is_ready,
            'ema20': round(m20, 1),
            'ema50': round(m50, 1),
            'rsi': round(curr_rsi, 1),
            'macd': round(curr_macd, 2),
            'signal': round(curr_signal, 2),
            'histogram': round(curr_hist, 2),
            'rvol': round(rvol, 2),
            'vol_type': vol_type,
            'vol_label': vol_label,
            'high_50d': round(high_50d, 0),
            'dist_res_pct': round(dist_res_pct, 1),
            'atr_ratio': round(atr_ratio, 2),
            'is_vcp_tight': is_vcp_tight,
            'is_vdu': is_vdu,
            'vcp_badge': vcp_badge,
            'vcp_label': vcp_label,
            'vcp_class': vcp_class,
            'tick_size': tick_size,
            'pivot_buy': pivot_buy,
            'stop_loss': stop_loss,
            'risk_pts': round(risk_pts, 0),
            'risk_pct': risk_pct,
            'target_1': target_1,
            'target_1_pct': target_1_pct,
            'target_2': target_2,
            'rr_ratio': "1:2.0",
            'volume': recent_vol,
            'avg_volume_20': int(avg_vol_20),
            'avg_volume_50': int(avg_vol_50),
            'avg_turnover_20d': int(avg_turnover_20d),
            'criteria': {
                'k1': {'pass': k1, 'title': 'Close > EMA 20', 'val': f'Price {curr_price:.0f} vs EMA20 {m20:.0f}'},
                'k2': {'pass': k2, 'title': 'EMA 20 > EMA 50', 'val': f'EMA20 {m20:.0f} vs EMA50 {m50:.0f}'},
                'k3': {'pass': k3, 'title': 'RSI 50-70 (Momentum)', 'val': f'RSI {curr_rsi:.1f}'},
                'k4': {'pass': k4, 'title': 'MACD Bullish (Line > Signal)', 'val': f'MACD {curr_macd:.2f} > Sig {curr_signal:.2f}'},
                'k5': {'pass': k5, 'title': 'RVOL (Surge >=1.2x atau Dry-Up <=0.75x)', 'val': k5_val},
                'k6': {'pass': k6, 'title': 'Higher Low Base Structure', 'val': hl_detail},
                'k7': {'pass': k7, 'title': 'Jarak ke Resistance 50D < 5%', 'val': f'-{dist_res_pct:.1f}% (High: {high_50d:.0f})'}
            },
            'tradingview_url': f"https://www.tradingview.com/chart/?symbol=IDX:{clean_ticker}"
        }
