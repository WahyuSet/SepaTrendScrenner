import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from screener.data_fetcher import DataFetcher
from screener.pre_breakout import PreBreakoutCalculator
from screener.quality_screener import compute_trade_setup

logger = logging.getLogger(__name__)

DB_PATH = os.path.join("data", "cache", "backtest_cache.db")
MASTER_TICKERS_FILE = os.path.join("data", "idx_master_tickers.json")


class SignalBacktestEngine:
    """
    Quantitative Signal Backtesting Engine for Indonesian Equities (IDX).
    
    Evaluates Pre-Breakout (VCP) and Quality Setup triggers over 1–2 years
    with Adaptive Holding Horizons:
    - MOMENTUM_BREAKOUT: 5 – 7 Trading Days
    - PULLBACK_RBS: 10 – 12 Trading Days
    - BASE_BUILDING: 15 – 20 Trading Days
    
    Execution assumptions agreed via /grill-me:
    1. Entry Price: T+1 Open (Next Day Opening price).
    2. Exit Model: Minervini Scale-Out (50% locked at TP1, SL moved to BEP, 50% chasing TP2).
    3. Same-bar Ambiguity: Conservative Worst-Case (SL triggered first if both touched in same day).
    4. Fees: 0.15% buy + 0.25% sell = 0.40% net round-trip broker commission.
    5. Liquidity Filter: 20D Avg Turnover >= Rp 500M & Price > Rp 100.
    """

    BROKER_FEE_PCT = 0.40  # 0.15% buy + 0.25% sell

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self.data_fetcher = DataFetcher(MASTER_TICKERS_FILE)
        self.prebreakout_calc = PreBreakoutCalculator()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_summary (
                    run_id TEXT PRIMARY KEY,
                    period_years INTEGER,
                    total_trades INTEGER,
                    win_trades INTEGER,
                    loss_trades INTEGER,
                    win_rate REAL,
                    profit_factor REAL,
                    payoff_ratio REAL,
                    avg_gain_pct REAL,
                    avg_loss_pct REAL,
                    avg_holding_days REAL,
                    max_drawdown REAL,
                    breakdown_json TEXT,
                    computed_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ticker TEXT,
                    setup_type TEXT,
                    signal_date TEXT,
                    entry_date TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    target_1 REAL,
                    target_2 REAL,
                    exit_date TEXT,
                    exit_price REAL,
                    holding_days INTEGER,
                    status TEXT,
                    gross_return_pct REAL,
                    net_return_pct REAL,
                    is_win INTEGER,
                    mfe_pct REAL,
                    mae_pct REAL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_ticker ON backtest_trades(ticker)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_setup ON backtest_trades(setup_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_run ON backtest_trades(run_id)")
            conn.commit()

    # -------------------------------------------------------------------------
    # 1. OHLCV DATA RETRIEVAL
    # -------------------------------------------------------------------------
    def fetch_ticker_history(self, ticker: str, years: int = 2) -> Optional[pd.DataFrame]:
        """Fetch daily OHLCV from yfinance with fallback."""
        clean = ticker.replace(".JK", "").strip().upper()
        sym = f"{clean}.JK"
        period = f"{years}y"
        try:
            df = yf.download(sym, period=period, interval="1d", progress=False, auto_adjust=False)
            if df is None or df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            df = df.dropna(subset=['Close'])
            if len(df) < 60:
                return None
            return df
        except Exception as e:
            logger.warning(f"Error fetching historical data for {sym}: {e}")
            return None

    # -------------------------------------------------------------------------
    # 2. TICKER-LEVEL SIGNAL DETECTION & SIMULATION
    # -------------------------------------------------------------------------
    def run_ticker_backtest(self, ticker: str, years: int = 2) -> Dict:
        """Run backtest for a single ticker over the requested years."""
        clean = ticker.replace(".JK", "").strip().upper()
        df = self.fetch_ticker_history(clean, years=years)
        if df is None or len(df) < 60:
            return {
                "status": "error",
                "ticker": clean,
                "message": f"Data historis tidak mencukupi untuk {clean}",
                "trades": [],
                "stats": self._empty_stats()
            }

        trades = self._simulate_trades_on_df(clean, df)
        stats = self._compute_stats_from_trades(trades)

        return {
            "status": "success",
            "ticker": clean,
            "company_name": self.data_fetcher.get_ticker_meta(clean).get("name", clean),
            "sector": self.data_fetcher.get_ticker_meta(clean).get("sector", "General"),
            "total_bars": len(df),
            "trades_count": len(trades),
            "stats": stats,
            "trades": trades
        }

    def _simulate_trades_on_df(self, ticker: str, df: pd.DataFrame) -> List[Dict]:
        """Simulate all rolling signals on a single DataFrame."""
        trades = []
        n = len(df)
        i = 50  # Start after initial 50 bars for indicators
        
        while i < n - 3:
            # 1. Check liquidity filter on signal day (20D avg turnover >= 500M and Price > 100)
            curr_close = float(df['Close'].iloc[i])
            if curr_close < 100:
                i += 1
                continue
            
            vol_20 = df['Volume'].iloc[max(0, i-19):i+1]
            close_20 = df['Close'].iloc[max(0, i-19):i+1]
            avg_turnover = float((vol_20 * close_20).mean())
            if avg_turnover < 500_000_000:
                i += 1
                continue

            # 2. Slice strictly up to bar i (No lookahead bias)
            slice_df = df.iloc[:i+1]
            signal = self._detect_signal_at_bar(slice_df)

            if not signal:
                i += 1
                continue

            # 3. Entry is next day Open (T+1 Open)
            entry_bar = df.iloc[i+1]
            entry_date = df.index[i+1].strftime("%Y-%m-%d")
            signal_date = df.index[i].strftime("%Y-%m-%d")
            entry_price = float(entry_bar['Open'])

            if entry_price <= 0:
                i += 1
                continue

            # Skip if opening price gapped up > 6% above signal close (over-chasing filter)
            if entry_price > curr_close * 1.06:
                i += 1
                continue

            setup_type = signal["setup_type"]
            max_horizon = signal["max_horizon"]
            stop_loss = signal["stop_loss"]
            target_1 = signal["target_1"]
            target_2 = signal["target_2"]

            # Safeguard: SL must be strictly below entry
            if stop_loss >= entry_price:
                stop_loss = round(entry_price * 0.94, 0)

            # Re-derive targets based on actual entry_price & risk
            risk_unit = entry_price - stop_loss
            if risk_unit <= 0:
                i += 1
                continue

            target_1 = round(entry_price + (1.5 * risk_unit), 0)
            target_2 = round(entry_price + (2.5 * risk_unit), 0)

            # 4. Simulate Trade Lifecycle from day T+1 onwards
            trade_result, next_i = self._simulate_trade_lifecycle(
                df=df,
                start_bar_idx=i+1,
                entry_date=entry_date,
                signal_date=signal_date,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                setup_type=setup_type,
                max_horizon=max_horizon,
                ticker=ticker
            )

            if trade_result:
                trades.append(trade_result)

            # Advance bar index to end of trade to avoid overlapping entries on same stock
            i = max(i + 1, next_i)

        return trades

    def _detect_signal_at_bar(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Evaluate if bar T satisfies:
        1. Momentum Breakout (5-7D): 50D high breakout with RVOL >= 1.3x
        2. Pullback / RBS (10-12D): Test of rising EMA20/MA50 with RSI bounce
        3. Base Building / VCP (15-20D): Tight consolidation with volume contraction
        """
        close = df['Close']
        high = df['High'] if 'High' in df else close
        low = df['Low'] if 'Low' in df else close
        volume = df['Volume'] if 'Volume' in df else pd.Series([1]*len(df), index=df.index)

        curr_close = float(close.iloc[-1])
        curr_vol = float(volume.iloc[-1])
        vol_ma20 = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else curr_vol
        rvol = (curr_vol / vol_ma20) if vol_ma20 > 0 else 1.0

        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        high_50d = float(high.iloc[-50:].max()) if len(high) >= 50 else float(high.max())
        low_10d = float(low.iloc[-10:].min()) if len(low) >= 10 else float(low.min())

        # Stop loss based on swing low or max -7%
        max_risk_price = round(curr_close * 0.93, 0)
        stop_loss = round(max(low_10d, max_risk_price), 0)

        # -------------------------------------------------------------
        # 1. MOMENTUM BREAKOUT (Horizon: 7 Days)
        # -------------------------------------------------------------
        # Price is within 1.5% of 50D high or breaking out, RVOL >= 1.3, close > EMA20 > EMA50
        is_breakout = (curr_close >= high_50d * 0.985) and (rvol >= 1.3) and (curr_close > ema20 > ema50)
        if is_breakout:
            risk = curr_close - stop_loss
            return {
                "setup_type": "MOMENTUM_BREAKOUT",
                "max_horizon": 7,
                "stop_loss": stop_loss,
                "target_1": round(curr_close + 1.5 * risk, 0),
                "target_2": round(curr_close + 2.5 * risk, 0)
            }

        # -------------------------------------------------------------
        # 2. PULLBACK / RBS (Horizon: 12 Days)
        # -------------------------------------------------------------
        # Uptrend (EMA20 > EMA50), price pulling back within 2.5% of EMA20, volume normal/low
        dist_ema20 = abs(curr_close - ema20) / curr_close
        is_pullback = (ema20 > ema50) and (dist_ema20 <= 0.025) and (curr_close >= ema20 * 0.98) and (rvol <= 1.2)
        if is_pullback:
            sl_pullback = round(min(stop_loss, ema50 * 0.98), 0)
            risk = curr_close - sl_pullback
            return {
                "setup_type": "PULLBACK_RBS",
                "max_horizon": 12,
                "stop_loss": sl_pullback,
                "target_1": round(curr_close + 1.5 * risk, 0),
                "target_2": round(curr_close + 2.5 * risk, 0)
            }

        # -------------------------------------------------------------
        # 3. BASE BUILDING / VCP (Horizon: 20 Days)
        # -------------------------------------------------------------
        # Low volatility consolidation: base width <= 10%, volume dry-up (RVOL < 0.85), close > EMA50
        if len(close) >= 20:
            rolling_high = high.iloc[-15:].max()
            rolling_low = low.iloc[-15:].min()
            base_width_pct = ((rolling_high - rolling_low) / rolling_low) * 100.0 if rolling_low > 0 else 99
            is_base = (base_width_pct <= 10.0) and (rvol <= 0.85) and (curr_close > ema50)
            if is_base:
                sl_base = round(rolling_low * 0.97, 0)
                risk = curr_close - sl_base
                return {
                    "setup_type": "BASE_BUILDING",
                    "max_horizon": 20,
                    "stop_loss": sl_base,
                    "target_1": round(curr_close + 1.5 * risk, 0),
                    "target_2": round(curr_close + 2.5 * risk, 0)
                }

        return None

    def _simulate_trade_lifecycle(
        self,
        df: pd.DataFrame,
        start_bar_idx: int,
        entry_date: str,
        signal_date: str,
        entry_price: float,
        stop_loss: float,
        target_1: float,
        target_2: float,
        setup_type: str,
        max_horizon: int,
        ticker: str
    ) -> Tuple[Optional[Dict], int]:
        """
        Simulate trade holding from start_bar_idx up to max_horizon trading days.
        Implements Minervini 50% scale out and conservative same-bar SL resolution.
        """
        n = len(df)
        end_idx = min(start_bar_idx + max_horizon, n)
        
        current_sl = stop_loss
        tp1_hit = False
        tp2_hit = False
        exit_date = entry_date
        exit_price = entry_price
        exit_status = "EXPIRED_EXIT"
        
        mfe_pct = 0.0  # Max favorable excursion
        mae_pct = 0.0  # Max adverse excursion

        # Portions: portion1 (50%) and portion2 (50%)
        portion1_return = 0.0
        portion2_return = 0.0

        bar_count = 0
        last_evaluated_idx = start_bar_idx

        for k in range(start_bar_idx, end_idx):
            bar_count += 1
            last_evaluated_idx = k
            bar = df.iloc[k]
            b_high = float(bar['High'])
            b_low = float(bar['Low'])
            b_close = float(bar['Close'])
            date_str = df.index[k].strftime("%Y-%m-%d")

            # Track MFE & MAE
            bar_mfe = ((b_high - entry_price) / entry_price) * 100.0
            bar_mae = ((b_low - entry_price) / entry_price) * 100.0
            if bar_mfe > mfe_pct:
                mfe_pct = bar_mfe
            if bar_mae < mae_pct:
                mae_pct = bar_mae

            # -------------------------------------------------------------
            # AMBIGUITY CHECK (Conservative Worst-Case: SL hit first)
            # -------------------------------------------------------------
            target_to_check = target_2 if tp1_hit else target_1
            sl_breached = (b_low <= current_sl)
            tp_breached = (b_high >= target_to_check)

            if sl_breached and tp_breached:
                # Same-bar conflict: Conservative standard assumes SL hit first!
                if not tp1_hit:
                    # Full position stopped out
                    exit_date = date_str
                    exit_price = current_sl
                    exit_status = "SL_HIT"
                    portion1_return = ((current_sl - entry_price) / entry_price) * 100.0
                    portion2_return = portion1_return
                    break
                else:
                    # Runner stopped out at BEP
                    exit_date = date_str
                    exit_price = current_sl
                    exit_status = "TP1_HIT"
                    portion2_return = ((current_sl - entry_price) / entry_price) * 100.0
                    break

            # 1. Stop Loss Check
            if sl_breached:
                exit_date = date_str
                exit_price = current_sl
                if not tp1_hit:
                    exit_status = "SL_HIT"
                    portion1_return = ((current_sl - entry_price) / entry_price) * 100.0
                    portion2_return = portion1_return
                else:
                    exit_status = "TP1_HIT"
                    portion2_return = ((current_sl - entry_price) / entry_price) * 100.0
                break

            # 2. Target 1 Hit (Lock 50%, Move SL to BEP)
            if not tp1_hit and tp_breached:
                tp1_hit = True
                portion1_return = ((target_1 - entry_price) / entry_price) * 100.0
                current_sl = entry_price  # Move SL to BEP
                exit_status = "TP1_HIT"
                exit_date = date_str
                exit_price = target_1
                # If target_2 was also breached immediately in subsequent check:
                if b_high >= target_2:
                    tp2_hit = True
                    portion2_return = ((target_2 - entry_price) / entry_price) * 100.0
                    exit_status = "TP2_HIT"
                    exit_price = target_2
                    break
                continue

            # 3. Target 2 Hit (Runner Reached)
            if tp1_hit and b_high >= target_2:
                tp2_hit = True
                portion2_return = ((target_2 - entry_price) / entry_price) * 100.0
                exit_status = "TP2_HIT"
                exit_date = date_str
                exit_price = target_2
                break

        # If trade reached horizon without hitting terminal SL or TP2:
        if exit_status == "EXPIRED_EXIT" or (tp1_hit and not tp2_hit and exit_status == "TP1_HIT" and b_low > current_sl):
            final_bar = df.iloc[last_evaluated_idx]
            final_close = float(final_bar['Close'])
            final_date = df.index[last_evaluated_idx].strftime("%Y-%m-%d")
            exit_date = final_date
            exit_price = final_close
            remaining_return = ((final_close - entry_price) / entry_price) * 100.0

            if not tp1_hit:
                portion1_return = remaining_return
                portion2_return = remaining_return
                exit_status = "EXPIRED_EXIT"
            else:
                portion2_return = remaining_return
                exit_status = "TP1_HIT"

        # Calculate blended return: 50% portion1 + 50% portion2 - Broker fee
        gross_return_pct = round((0.5 * portion1_return) + (0.5 * portion2_return), 2)
        net_return_pct = round(gross_return_pct - self.BROKER_FEE_PCT, 2)
        is_win = 1 if net_return_pct > 0 else 0

        trade_record = {
            "ticker": ticker,
            "setup_type": setup_type,
            "signal_date": signal_date,
            "entry_date": entry_date,
            "entry_price": round(entry_price, 0),
            "stop_loss": round(stop_loss, 0),
            "target_1": round(target_1, 0),
            "target_2": round(target_2, 0),
            "exit_date": exit_date,
            "exit_price": round(exit_price, 0),
            "holding_days": max(1, bar_count),
            "status": exit_status,
            "gross_return_pct": gross_return_pct,
            "net_return_pct": net_return_pct,
            "is_win": is_win,
            "mfe_pct": round(mfe_pct, 2),
            "mae_pct": round(mae_pct, 2)
        }

        return trade_record, last_evaluated_idx + 1

    # -------------------------------------------------------------------------
    # 3. STATISTICAL METRICS & SUMMARY
    # -------------------------------------------------------------------------
    def _compute_stats_from_trades(self, trades: List[Dict]) -> Dict:
        """Calculate quantitative metrics from a list of simulated trades."""
        total = len(trades)
        if total == 0:
            return self._empty_stats()

        wins = [t for t in trades if t['is_win'] == 1]
        losses = [t for t in trades if t['is_win'] == 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = round((win_count / total) * 100.0, 1)

        gains = [t['net_return_pct'] for t in wins]
        loss_values = [abs(t['net_return_pct']) for t in losses]

        sum_gains = sum(gains)
        sum_losses = sum(loss_values)

        avg_gain = round(float(np.mean(gains)), 2) if gains else 0.0
        avg_loss = round(float(np.mean(loss_values)), 2) if loss_values else 0.0
        profit_factor = round(float(sum_gains / sum_losses), 2) if sum_losses > 0 else (9.99 if sum_gains > 0 else 0.0)
        payoff_ratio = round(float(avg_gain / avg_loss), 2) if avg_loss > 0 else (float(avg_gain) if avg_gain > 0 else 1.0)
        avg_holding = round(float(np.mean([t['holding_days'] for t in trades])), 1)

        # Compute Max Drawdown on cumulative equity curve
        cum_ret = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in trades:
            cum_ret += float(t['net_return_pct'])
            if cum_ret > peak:
                peak = cum_ret
            dd = peak - cum_ret
            if dd > max_dd:
                max_dd = dd

        # Breakdown by setup type
        by_setup = {}
        for s_type in ["MOMENTUM_BREAKOUT", "PULLBACK_RBS", "BASE_BUILDING"]:
            sub_trades = [t for t in trades if t['setup_type'] == s_type]
            s_tot = len(sub_trades)
            s_win = len([t for t in sub_trades if t['is_win'] == 1])
            s_wr = round(float((s_win / s_tot) * 100.0), 1) if s_tot > 0 else 0.0
            s_avg_ret = round(float(np.mean([t['net_return_pct'] for t in sub_trades])), 2) if s_tot > 0 else 0.0
            by_setup[s_type] = {
                "total": s_tot,
                "wins": s_win,
                "win_rate": s_wr,
                "avg_net_return": s_avg_ret
            }

        return {
            "total_trades": total,
            "win_trades": win_count,
            "loss_trades": loss_count,
            "win_rate": float(win_rate),
            "profit_factor": float(profit_factor),
            "payoff_ratio": float(payoff_ratio),
            "avg_gain_pct": float(avg_gain),
            "avg_loss_pct": float(avg_loss),
            "avg_holding_days": float(avg_holding),
            "max_drawdown": round(float(max_dd), 2),
            "breakdown": by_setup
        }

    def _empty_stats(self) -> Dict:
        return {
            "total_trades": 0,
            "win_trades": 0,
            "loss_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "payoff_ratio": 0.0,
            "avg_gain_pct": 0.0,
            "avg_loss_pct": 0.0,
            "avg_holding_days": 0.0,
            "max_drawdown": 0.0,
            "breakdown": {
                "MOMENTUM_BREAKOUT": {"total": 0, "wins": 0, "win_rate": 0.0, "avg_net_return": 0.0},
                "PULLBACK_RBS": {"total": 0, "wins": 0, "win_rate": 0.0, "avg_net_return": 0.0},
                "BASE_BUILDING": {"total": 0, "wins": 0, "win_rate": 0.0, "avg_net_return": 0.0}
            }
        }

    # -------------------------------------------------------------------------
    # 4. BENCHMARK SUMMARY CACHE (PERSISTENT & INSTANT)
    # -------------------------------------------------------------------------
    def get_cached_benchmark_summary(self, years: int = 2) -> Dict:
        """Get pre-computed summary benchmark. If not present, computes a fast representative sample."""
        run_id = f"benchmark_{years}y"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backtest_summary WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if row:
                breakdown = json.loads(row["breakdown_json"]) if row["breakdown_json"] else {}
                return {
                    "status": "success",
                    "run_id": row["run_id"],
                    "period_years": row["period_years"],
                    "total_trades": row["total_trades"],
                    "win_trades": row["win_trades"],
                    "loss_trades": row["loss_trades"],
                    "win_rate": row["win_rate"],
                    "profit_factor": row["profit_factor"],
                    "payoff_ratio": row["payoff_ratio"],
                    "avg_gain_pct": row["avg_gain_pct"],
                    "avg_loss_pct": row["avg_loss_pct"],
                    "avg_holding_days": row["avg_holding_days"],
                    "max_drawdown": row["max_drawdown"],
                    "breakdown": breakdown,
                    "computed_at": row["computed_at"]
                }

        # If cache is empty, compute benchmark on representative liquid IDX universe
        logger.info(f"No cached benchmark found for {run_id}. Computing initial sample...")
        return self.compute_universe_benchmark(years=years, max_tickers=35)

    def compute_universe_benchmark(self, years: int = 2, max_tickers: int = 35) -> Dict:
        run_id = f"benchmark_{years}y"
        tickers = self.data_fetcher.tickers_df['ticker'].tolist() if (self.data_fetcher.tickers_df is not None and not self.data_fetcher.tickers_df.empty) else []
        
        # Prioritize top liquid stocks (Kompas100 / high cap names)
        sample_priority = [
            "BBCA", "BBRI", "BMRI", "BBNI", "ASII", "TLKM", "BRPT", "TPIA", "AMMN", "BREN",
            "MDKA", "MEDC", "PGAS", "ADRO", "PTBA", "INCO", "ANTM", "CPIN", "ICBP", "INDF",
            "KLBF", "MYOR", "UNTR", "GOTO", "ACES", "ERAA", "SMGR", "INTP", "AKRA", "INKP",
            "TKIM", "BRIS", "JSMR", "MAPA", "MAPI"
        ]
        test_tickers = [t for t in sample_priority if t in tickers][:max_tickers]
        if len(test_tickers) < max_tickers:
            for t in tickers:
                if t not in test_tickers:
                    test_tickers.append(t)
                if len(test_tickers) >= max_tickers:
                    break

        all_trades = []
        for ticker in test_tickers:
            df = self.fetch_ticker_history(ticker, years=years)
            if df is not None and len(df) >= 60:
                t_trades = self._simulate_trades_on_df(ticker, df)
                all_trades.extend(t_trades)

        stats = self._compute_stats_from_trades(all_trades)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Persist to SQLite
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO backtest_summary 
                (run_id, period_years, total_trades, win_trades, loss_trades, win_rate,
                 profit_factor, payoff_ratio, avg_gain_pct, avg_loss_pct, avg_holding_days,
                 max_drawdown, breakdown_json, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, years, stats["total_trades"], stats["win_trades"], stats["loss_trades"],
                stats["win_rate"], stats["profit_factor"], stats["payoff_ratio"], stats["avg_gain_pct"],
                stats["avg_loss_pct"], stats["avg_holding_days"], stats["max_drawdown"],
                json.dumps(stats["breakdown"]), now_str
            ))

            # Store recent trades
            cursor.execute("DELETE FROM backtest_trades WHERE run_id = ?", (run_id,))
            for tr in all_trades:
                cursor.execute("""
                    INSERT INTO backtest_trades 
                    (run_id, ticker, setup_type, signal_date, entry_date, entry_price, stop_loss,
                     target_1, target_2, exit_date, exit_price, holding_days, status, gross_return_pct,
                     net_return_pct, is_win, mfe_pct, mae_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id, tr["ticker"], tr["setup_type"], tr["signal_date"], tr["entry_date"],
                    tr["entry_price"], tr["stop_loss"], tr["target_1"], tr["target_2"], tr["exit_date"],
                    tr["exit_price"], tr["holding_days"], tr["status"], tr["gross_return_pct"],
                    tr["net_return_pct"], tr["is_win"], tr["mfe_pct"], tr["mae_pct"]
                ))
            conn.commit()

        return {
            "status": "success",
            "run_id": run_id,
            "period_years": years,
            "total_trades": stats["total_trades"],
            "win_trades": stats["win_trades"],
            "loss_trades": stats["loss_trades"],
            "win_rate": stats["win_rate"],
            "profit_factor": stats["profit_factor"],
            "payoff_ratio": stats["payoff_ratio"],
            "avg_gain_pct": stats["avg_gain_pct"],
            "avg_loss_pct": stats["avg_loss_pct"],
            "avg_holding_days": stats["avg_holding_days"],
            "max_drawdown": stats["max_drawdown"],
            "breakdown": stats["breakdown"],
            "computed_at": now_str,
            "sample_tickers_count": len(test_tickers)
        }

    def get_trades_list(
        self,
        run_id: str = "benchmark_2y",
        setup_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Fetch trades from cache with optional filters."""
        query = "SELECT * FROM backtest_trades WHERE run_id = ?"
        params = [run_id]

        if setup_type and setup_type != "ALL":
            query += " AND setup_type = ?"
            params.append(setup_type)
        if status and status != "ALL":
            if status == "WIN":
                query += " AND is_win = 1"
            elif status == "LOSS":
                query += " AND is_win = 0"
            else:
                query += " AND status = ?"
                params.append(status)

        query += " ORDER BY signal_date DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
