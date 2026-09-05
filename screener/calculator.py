import numpy as np
import pandas as pd
import logging
from .rs_calculator import RSCalculator
from .data_fetcher import DataFetcher

logger = logging.getLogger(__name__)

class SEPACalculator:
    def __init__(self, tickers_csv_path="data/idx_tickers.csv", benchmark_symbol="^JKSE"):
        self.fetcher = DataFetcher(tickers_csv_path)
        self.rs_calc = RSCalculator(benchmark_symbol)
        self.len_52w = 252
        self.pct_above_low = 25.0
        self.pct_within_high = 25.0
        self.len_slope_min = 22
        self.len_slope_ideal = 88
        self.rs_threshold = 70.0

    def evaluate_stock(self, ticker, df):
        """
        Evaluate a single stock's historical price data against 8 Minervini SEPA criteria.
        df must contain 'Close', 'High', 'Low', 'Volume'.
        """
        if df is None or df.empty:
            return None

        df = df.dropna(subset=['Close'])

        # Check minimal data requirement
        if len(df) < self.len_52w:
            logger.debug(f"{ticker} has {len(df)} bars, less than {self.len_52w}")
            return None

        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume'] if 'Volume' in df else pd.Series([0]*len(df))

        # Current Price
        curr_price = float(close.iloc[-1])
        if curr_price <= 0 or np.isnan(curr_price):
            return None

        # 1. Moving Averages
        ma50_series = close.rolling(window=50).mean()
        ma150_series = close.rolling(window=150).mean()
        ma200_series = close.rolling(window=200).mean()

        m50 = float(ma50_series.iloc[-1])
        m150 = float(ma150_series.iloc[-1])
        m200 = float(ma200_series.iloc[-1])

        if any(np.isnan(v) for v in [m50, m150, m200]):
            logger.debug(f"{ticker} has NaN in Moving Averages, skipping.")
            return None

        # 2. MA200 Slope Lookback (Min 22 bars ~1 mo, Ideal 88 bars ~4-5 mo)
        m200_slope_min_ok = False
        m200_slope_ideal_ok = False
        
        if len(ma200_series) >= self.len_slope_min + 1:
            idx_min = -(self.len_slope_min + 1)
            if not np.isnan(ma200_series.iloc[idx_min]):
                m200_slope_min_ok = bool(m200 > ma200_series.iloc[idx_min])

        if len(ma200_series) >= self.len_slope_ideal + 1:
            idx_ideal = -(self.len_slope_ideal + 1)
            if not np.isnan(ma200_series.iloc[idx_ideal]):
                m200_slope_ideal_ok = bool(m200 > ma200_series.iloc[idx_ideal])

        m200_up = m200_slope_ideal_ok or m200_slope_min_ok

        slope_label = "Ideal (>4-5m)" if m200_slope_ideal_ok else ("Min (>1m)" if m200_slope_min_ok else "Flat/Down")

        # 3. 52-Week High / Low
        high_52w = float(high.iloc[-self.len_52w:].max())
        low_52w = float(low.iloc[-self.len_52w:].min())

        dist_low_pct = ((curr_price - low_52w) / low_52w) * 100.0 if low_52w > 0 else 0.0
        dist_high_pct = ((high_52w - curr_price) / high_52w) * 100.0 if high_52w > 0 else 0.0

        # 4. RS Rating vs IHSG (Percentile Rank over 252 bars)
        rs_score, stock_perf = self.rs_calc.compute_rs_score(close)

        # 5. Evaluate 8 Criteria (Mark Minervini SEPA Template)
        # C1: Price > MA150 and Price > MA200
        c1 = bool(curr_price > m150 and curr_price > m200)

        # C2: MA150 > MA200
        c2 = bool(m150 > m200)

        # C3: MA200 Trending Up (Slope min or ideal)
        c3 = bool(m200_up)

        # C4: MA50 > MA150 and MA50 > MA200
        c4 = bool(m50 > m150 and m50 > m200)

        # C5: Price > MA50
        c5 = bool(curr_price > m50)

        # C6: Price >= 25% Above 52W Low
        c6 = bool(dist_low_pct >= self.pct_above_low)

        # C7: Price within 25% of 52W High (<= 25% distance)
        c7 = bool(dist_high_pct <= self.pct_within_high)

        # C8: RS Rating >= 70 (Original Minervini Trend Template condition)
        c8 = bool(rs_score >= self.rs_threshold)

        criteria = [c1, c2, c3, c4, c5, c6, c7, c8]
        total_score = sum(1 for c in criteria if c)

        is_stage2 = (total_score == 8)
        status = "CONFIRMED" if is_stage2 else ("WATCHLIST" if total_score >= 6 else "UNQUALIFIED")

        meta = self.fetcher.get_ticker_meta(ticker)
        clean_ticker = ticker.replace(".JK", "").strip().upper()

        # Volume info
        recent_vol = int(volume.iloc[-1]) if not volume.empty else 0
        avg_vol_20 = int(volume.iloc[-20:].mean()) if len(volume) >= 20 else recent_vol

        # 1-Day change %
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
            'is_stage2': is_stage2,
            'is_sepa_vcp_ready': False,
            'sepa_vcp_badge': None,
            'rs_score': rs_score,
            'stock_perf': round(stock_perf * 100, 2),
            'dist_low_pct': round(dist_low_pct, 1),
            'dist_high_pct': round(dist_high_pct, 1),
            'high_52w': high_52w,
            'low_52w': low_52w,
            'ma50': round(m50, 2),
            'ma150': round(m150, 2),
            'ma200': round(m200, 2),
            'slope_label': slope_label,
            'volume': recent_vol,
            'avg_volume_20': avg_vol_20,
            'criteria': {
                'c1': {'pass': c1, 'title': 'Harga > MA150 & MA200', 'val': f'Price {curr_price:.0f} vs MA150 {m150:.0f}, MA200 {m200:.0f}'},
                'c2': {'pass': c2, 'title': 'MA150 > MA200', 'val': f'MA150 {m150:.0f} vs MA200 {m200:.0f}'},
                'c3': {'pass': c3, 'title': 'MA200 Trending Up', 'val': slope_label},
                'c4': {'pass': c4, 'title': 'MA50 > MA150 & MA200', 'val': f'MA50 {m50:.0f} vs MA150 {m150:.0f}, MA200 {m200:.0f}'},
                'c5': {'pass': c5, 'title': 'Harga > MA50', 'val': f'Price {curr_price:.0f} vs MA50 {m50:.0f}'},
                'c6': {'pass': c6, 'title': '>= 25% Di Atas 52W Low', 'val': f'+{dist_low_pct:.1f}% (Low: {low_52w:.0f})'},
                'c7': {'pass': c7, 'title': '<= 25% Dari 52W High', 'val': f'-{dist_high_pct:.1f}% (High: {high_52w:.0f})'},
                'c8': {'pass': c8, 'title': 'RS Rating >= 70 vs IHSG', 'val': f'{rs_score:.0f}/100 (Perf: {stock_perf*100:+.1f}%)'}
            },
            'tradingview_url': f"https://www.tradingview.com/chart/?symbol=IDX:{clean_ticker}"
        }

    def run_full_scan(self, max_workers=10, period="2y"):
        """Run scan across all tickers in the dataset."""
        logger.info("Initializing benchmark data...")
        self.rs_calc.fetch_benchmark(period=period)

        logger.info("Fetching batch stock data...")
        all_data = self.fetcher.fetch_batch_concurrent(max_workers=max_workers, period=period)

        results = []
        for ticker, df in all_data.items():
            evaluated = self.evaluate_stock(ticker, df)
            if evaluated is not None:
                results.append(evaluated)

        # Sort results by total_score DESC, then rs_score DESC, then dist_low_pct DESC
        results.sort(key=lambda x: (x['total_score'], x['rs_score'], x['dist_low_pct']), reverse=True)

        logger.info(f"Scan complete. Evaluated {len(results)} stocks.")
        return results
