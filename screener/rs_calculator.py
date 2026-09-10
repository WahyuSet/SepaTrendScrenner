import numpy as np
import pandas as pd
import yfinance as yf
import logging

logger = logging.getLogger(__name__)

class RSCalculator:
    def __init__(self, benchmark_symbol="^JKSE"):
        self.benchmark_symbol = benchmark_symbol
        self.bench_data = None
        self.bench_perf = None
        self.bench_perf_series = None

    def fetch_benchmark(self, period="2y"):
        """Fetch benchmark data (IHSG / ^JKSE) from yfinance and precalculate perf series."""
        try:
            logger.info(f"Fetching benchmark data for {self.benchmark_symbol}...")
            bench = yf.Ticker(self.benchmark_symbol)
            df = bench.history(period=period, auto_adjust=False)
            if df.empty or len(df) < 252:
                logger.warning(f"Benchmark data length {len(df)} is less than 252 days.")
            
            # Ensure index is timezone-naive for clean date alignment
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
                
            self.bench_data = df
            if not df.empty and 'Close' in df:
                close_s = df['Close'].dropna()
                self.bench_perf_series = self.calc_ibd_perf_series(close_s)
                self.bench_perf = float(self.bench_perf_series.iloc[-1]) if len(self.bench_perf_series) > 0 else None
                logger.info(f"Benchmark perf computed: {self.bench_perf:.4f}")
            else:
                self.bench_perf_series = None
                self.bench_perf = None
            return True
        except Exception as e:
            logger.error(f"Error fetching benchmark {self.benchmark_symbol}: {e}")
            self.bench_data = None
            self.bench_perf_series = None
            self.bench_perf = None
            return False

    @staticmethod
    def calc_ibd_perf_series(close_series):
        """
        Calculate IBD weighted performance score series:
        Formula: 40% 3M (63 bars), 20% 6M (126 bars), 20% 9M (189 bars), 20% 12M (252 bars)
        """
        if len(close_series) < 64:
            return pd.Series([0.0] * len(close_series), index=close_series.index)

        r_3m = close_series.pct_change(63).fillna(0.0)
        r_6m = close_series.pct_change(126).fillna(0.0)
        r_9m = close_series.pct_change(189).fillna(0.0)
        r_12m = close_series.pct_change(252).fillna(0.0)

        return 0.40 * r_3m + 0.20 * r_6m + 0.20 * r_9m + 0.20 * r_12m

    @staticmethod
    def calc_ibd_perf(close_series):
        """Single point IBD performance for the last bar."""
        series = RSCalculator.calc_ibd_perf_series(close_series)
        return float(series.iloc[-1]) if len(series) > 0 else 0.0

    def compute_rs_score(self, stock_close_series):
        """
        Compute RS Rating (1-99) using Percentile Rank over 252 bars as defined
        in the original Minervini SEPA Trend Template.
        
        Formula:
        rs_relative = (1.0 + stock_perf) / max(0.001, (1.0 + bench_perf))
        rs_percentile = ta.percentrank(rs_relative, 252)
        """
        if stock_close_series is None or len(stock_close_series) < 64:
            return 50.0, 0.0

        # Strip timezone if present for clean alignment
        s_close = stock_close_series.copy()
        if s_close.index.tz is not None:
            s_close.index = s_close.index.tz_localize(None)

        stock_perf_s = self.calc_ibd_perf_series(s_close)
        latest_stock_perf = float(stock_perf_s.iloc[-1]) if len(stock_perf_s) > 0 else 0.0

        if self.bench_perf_series is None or self.bench_perf is None:
            # Fallback to neutral 50 when benchmark is unavailable
            return 50.0, latest_stock_perf

        # Align stock and benchmark on dates
        aligned = pd.DataFrame({
            'stock_perf': stock_perf_s
        }).join(
            pd.DataFrame({'bench_perf': self.bench_perf_series}),
            how='left'
        )

        # Forward fill benchmark perf for any dates where stock traded but benchmark was holiday
        aligned['bench_perf'] = aligned['bench_perf'].ffill().fillna(0.0)

        denom = np.maximum(0.001, 1.0 + aligned['bench_perf'].values)
        rs_relative = (1.0 + aligned['stock_perf'].values) / denom

        if len(rs_relative) < 2:
            return 50.0, latest_stock_perf

        # Lookback window (last 252 bars, or all available if less)
        lookback = min(252, len(rs_relative))
        window = rs_relative[-lookback:]
        current_val = rs_relative[-1]

        # ta.percentrank: % of elements in window <= current_val
        percentrank = (window <= current_val).sum() / len(window) * 100.0
        rs_score = float(np.clip(round(percentrank), 1.0, 99.0))

        return rs_score, latest_stock_perf

    @staticmethod
    def calc_ibd_performance_ratio(close_series):
        """
        Calculate single point IBD performance ratio using 4 lookback windows:
        performa = 0.40 * (P_today / P_63d)
                 + 0.20 * (P_today / P_126d)
                 + 0.20 * (P_today / P_189d)
                 + 0.20 * (P_today / P_252d)
        Requires at least 252 bars. Returns float or None.
        """
        if close_series is None or len(close_series) < 252:
            return None

        clean_close = close_series.dropna()
        if len(clean_close) < 252:
            return None

        p0 = float(clean_close.iloc[-1])
        if p0 <= 0 or np.isnan(p0):
            return None

        p63 = float(clean_close.iloc[-64]) if len(clean_close) >= 64 else None
        p126 = float(clean_close.iloc[-127]) if len(clean_close) >= 127 else None
        p189 = float(clean_close.iloc[-190]) if len(clean_close) >= 190 else None
        p252 = float(clean_close.iloc[-253]) if len(clean_close) >= 253 else float(clean_close.iloc[0])

        if any(p is None or p <= 0 or np.isnan(p) for p in [p63, p126, p189, p252]):
            return None

        perf = (
            0.40 * (p0 / p63)
            + 0.20 * (p0 / p126)
            + 0.20 * (p0 / p189)
            + 0.20 * (p0 / p252)
        )
        return float(perf)

    def compute_market_distribution(self, all_stock_data=None, date_str=None):
        """
        Compute RS Score distribution (7 percentiles: P99, P90, P70, P50, P30, P10, P01)
        across all IDX stocks with >= 252 bars history vs IHSG.
        """
        from datetime import datetime

        if self.bench_data is None or self.bench_data.empty:
            logger.info("Fetching IHSG benchmark data...")
            self.fetch_benchmark()

        if self.bench_data is None or 'Close' not in self.bench_data or self.bench_data.empty:
            logger.error("Failed to acquire benchmark data for IHSG.")
            return None

        bench_close = self.bench_data['Close'].dropna()
        perf_bench = self.calc_ibd_performance_ratio(bench_close)
        if perf_bench is None or perf_bench <= 0:
            logger.error(f"Invalid benchmark performance ratio: {perf_bench}")
            return None

        # Determine date from benchmark or current date
        if date_str is None:
            if not bench_close.empty and hasattr(bench_close.index[-1], 'strftime'):
                date_str = bench_close.index[-1].strftime("%Y-%m-%d")
            else:
                date_str = datetime.now().strftime("%Y-%m-%d")

        # If stock data not provided, fetch from DataFetcher
        if all_stock_data is None:
            from .data_fetcher import DataFetcher
            fetcher = DataFetcher()
            all_stock_data = fetcher.fetch_batch_concurrent(max_workers=16, period="2y")

        stock_scores = []
        for ticker, df in all_stock_data.items():
            if df is None or df.empty or 'Close' not in df:
                continue
            close_s = df['Close'].dropna()
            if len(close_s) < 252:
                continue

            perf_stock = self.calc_ibd_performance_ratio(close_s)
            if perf_stock is None or perf_stock <= 0:
                continue

            rs_score = (perf_stock / perf_bench) * 100.0
            if not np.isnan(rs_score) and not np.isinf(rs_score):
                stock_scores.append(float(rs_score))

        if not stock_scores:
            logger.warning("No valid stock RS scores could be calculated.")
            return None

        stock_scores.sort()
        scores_arr = np.array(stock_scores)

        distribution = {
            "pct_99": round(float(np.percentile(scores_arr, 99)), 2),
            "pct_90": round(float(np.percentile(scores_arr, 90)), 2),
            "pct_70": round(float(np.percentile(scores_arr, 70)), 2),
            "pct_50": round(float(np.percentile(scores_arr, 50)), 2),
            "pct_30": round(float(np.percentile(scores_arr, 30)), 2),
            "pct_10": round(float(np.percentile(scores_arr, 10)), 2),
            "pct_01": round(float(np.percentile(scores_arr, 1)), 2),
        }

        output = {
            "date": date_str,
            "market": "IDX",
            "total_stocks": len(stock_scores),
            "benchmark": "IHSG",
            "distribution": distribution
        }

        logger.info(f"RS distribution calculated for {len(stock_scores)} stocks on {date_str}: {distribution}")
        return output

