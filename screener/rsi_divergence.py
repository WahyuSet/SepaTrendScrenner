import numpy as np
import pandas as pd
import logging
from .data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

class RSIDivergenceCalculator:
    def __init__(self, tickers_csv_path="data/idx_tickers.csv", rsi_period=14, lb_left=5, lb_right=5, range_lower=5, range_upper=60):
        self.fetcher = DataFetcher(tickers_csv_path)
        self.rsi_period = rsi_period
        self.lb_left = lb_left
        self.lb_right = lb_right
        self.range_lower = range_lower
        self.range_upper = range_upper

    @staticmethod
    def compute_rsi(series, period=14):
        """Compute standard RSI using Wilder's Exponential Moving Average (matches Pine Script ta.rsi)."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        avg_gain = gain.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0)

    def detect_divergence(self, ticker, df, max_bars_ago=5):
        """
        Detect Regular Bullish and Hidden Bullish Divergence on RSI(14) vs Price.
        df must contain 'Close', 'Low', 'High', 'Volume'.
        """
        if df is None or df.empty:
            return None

        df = df.dropna(subset=['Close'])
        if len(df) < (self.rsi_period + self.lb_left + self.lb_right + self.range_lower):
            return None

        close = df['Close']
        low = df['Low']
        high = df['High'] if 'High' in df else close
        volume = df['Volume'] if 'Volume' in df else pd.Series([0]*len(df), index=df.index)

        curr_price = float(close.iloc[-1])
        if curr_price <= 0 or np.isnan(curr_price):
            return None

        rsi_series = self.compute_rsi(close, period=self.rsi_period)
        n = len(df)
        osc_vals = rsi_series.values
        low_vals = low.values

        pivots = [] # (bar_index, pivot_rsi, pivot_low)
        signals = []

        for i in range(self.lb_left + self.lb_right, n):
            p = i - self.lb_right
            cand_rsi = osc_vals[p]

            # Check pivot low condition on RSI
            is_pl = True
            for k in range(1, self.lb_left + 1):
                if osc_vals[p - k] <= cand_rsi:
                    is_pl = False
                    break

            if is_pl:
                for m in range(1, self.lb_right + 1):
                    if osc_vals[p + m] < cand_rsi:
                        is_pl = False
                        break

            if is_pl:
                cand_low = low_vals[p]
                if len(pivots) > 0:
                    prev_i, prev_rsi, prev_low = pivots[-1]
                    bars_since = i - prev_i

                    if self.range_lower <= bars_since <= self.range_upper:
                        bars_ago = (n - 1) - i
                        
                        # 1. Regular Bullish: Price Lower Low & RSI Higher Low (Bullish Reversal)
                        if cand_low < prev_low and cand_rsi > prev_rsi:
                            signals.append({
                                'bar_idx': i,
                                'bars_ago': bars_ago,
                                'type': 'REGULAR_BULL',
                                'label': 'Regular Bullish',
                                'pivot_rsi': round(float(cand_rsi), 1),
                                'prev_pivot_rsi': round(float(prev_rsi), 1),
                                'pivot_low': round(float(cand_low), 0),
                                'prev_pivot_low': round(float(prev_low), 0),
                                'bars_between_pivots': bars_since
                            })
                        # 2. Hidden Bullish: Price Higher Low & RSI Lower Low (Bullish Continuation)
                        elif cand_low > prev_low and cand_rsi < prev_rsi:
                            signals.append({
                                'bar_idx': i,
                                'bars_ago': bars_ago,
                                'type': 'HIDDEN_BULL',
                                'label': 'Hidden Bullish',
                                'pivot_rsi': round(float(cand_rsi), 1),
                                'prev_pivot_rsi': round(float(prev_rsi), 1),
                                'pivot_low': round(float(cand_low), 0),
                                'prev_pivot_low': round(float(prev_low), 0),
                                'bars_between_pivots': bars_since
                            })

                pivots.append((i, cand_rsi, cand_low))

        # Filter recent signals within max_bars_ago (default 5 bars, prioritizing freshest signal)
        recent_signals = [s for s in signals if s['bars_ago'] <= max_bars_ago]
        if not recent_signals:
            return None

        # Take the most recent divergence signal
        latest_sig = recent_signals[-1]

        meta = self.fetcher.get_ticker_meta(ticker)
        clean_ticker = ticker.replace(".JK", "").strip().upper()

        current_rsi = round(float(osc_vals[-1]), 1)
        recent_vol = int(volume.iloc[-1]) if not volume.empty else 0
        avg_vol_20 = int(volume.iloc[-20:].mean()) if len(volume) >= 20 else recent_vol

        prev_close = float(close.iloc[-2]) if len(close) >= 2 else curr_price
        pct_change_1d = ((curr_price - prev_close) / prev_close) * 100.0 if prev_close > 0 else 0.0

        recency_text = "Hari Ini" if latest_sig['bars_ago'] == 0 else f"{latest_sig['bars_ago']} Hari Lalu"

        return {
            'ticker': clean_ticker,
            'name': meta['name'],
            'sector': meta['sector'],
            'price': curr_price,
            'pct_change_1d': round(pct_change_1d, 2),
            'rsi': current_rsi,
            'divergence_type': latest_sig['type'],
            'divergence_label': latest_sig['label'],
            'bars_ago': latest_sig['bars_ago'],
            'recency_text': recency_text,
            'pivot_rsi': latest_sig['pivot_rsi'],
            'prev_pivot_rsi': latest_sig['prev_pivot_rsi'],
            'pivot_low': latest_sig['pivot_low'],
            'prev_pivot_low': latest_sig['prev_pivot_low'],
            'bars_between': latest_sig['bars_between_pivots'],
            'volume': recent_vol,
            'avg_volume_20': avg_vol_20,
            'tradingview_url': f"https://www.tradingview.com/chart/?symbol=IDX:{clean_ticker}"
        }
