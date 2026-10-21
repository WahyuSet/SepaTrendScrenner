"""
LPM orchestration: trading calendar from yfinance, broker history from IDXApiClient,
sync fetch of the newest days, and the background backfill thread.
The math lives in screener/lpm.py; the routes in app.py only translate to HTTP.
"""
import time
import logging
import threading

import yfinance as yf

from .lpm import LPM_PARAMS, build_lpm

logger = logging.getLogger(__name__)

PRICE_CACHE_TTL_SEC = 600
MAX_BACKFILL_DAYS = 250


class LPMDataError(Exception):
    """Price data for the ticker is unavailable, so there is no trading calendar to work with."""


class LPMQuotaError(Exception):
    """Not enough quota left above the reserve to start a backfill."""


def load_daily_prices(ticker, period="1y"):
    """Daily OHLCV bars from yfinance as plain dicts, oldest first."""
    df = yf.Ticker(f"{ticker}.JK").history(period=period, auto_adjust=False)
    if df is None or df.empty:
        return []
    df = df.dropna(subset=["Close"])
    return [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]),
        }
        for idx, row in df.iterrows()
    ]


class LPMService:
    def __init__(self, client, price_loader=load_daily_prices):
        self.client = client
        self.price_loader = price_loader
        self._price_cache = {}
        self._cache_lock = threading.Lock()
        self._threads = {}

    # -------------------------------------------------------------------------
    # Trading calendar
    # -------------------------------------------------------------------------
    def trading_days(self, ticker, n):
        """The last n final trading days (today only after 17:00 WIB) as OHLCV bars."""
        period = "2y" if n > 200 else "1y"
        key = (ticker, period)
        with self._cache_lock:
            cached = self._price_cache.get(key)
        if cached and time.time() - cached[0] < PRICE_CACHE_TTL_SEC:
            bars = cached[1]
        else:
            bars = self.price_loader(ticker, period)
            with self._cache_lock:
                self._price_cache[key] = (time.time(), bars)
        if not bars:
            raise LPMDataError(f"Data harga harian {ticker} tidak tersedia, jadi kalender hari bursa tidak bisa disusun.")
        final = [b for b in bars if self.client.is_day_final(b["date"])]
        return final[-n:]

    @staticmethod
    def _fetchable(bars):
        # Zero-volume bars (suspension, no trade) have no broker data; skip them to save quota
        return [b["date"] for b in bars if b.get("volume")]

    # -------------------------------------------------------------------------
    # GET /api/idx/lpm/<ticker>
    # -------------------------------------------------------------------------
    def get_lpm(self, ticker):
        bars = self.trading_days(ticker, LPM_PARAMS["history_days"])
        dates = [b["date"] for b in bars]
        fetchable = self._fetchable(bars)

        synced = self._sync_newest(ticker, fetchable)
        stored = self.client.load_broker_daily(ticker, dates)

        days = []
        for bar in bars:
            row = stored.get(bar["date"])
            brokers = row["brokers"] if row and row["status"] == "ok" else None
            days.append({**bar, "brokers": brokers})

        payload = build_lpm(days)
        missing = self.client.missing_broker_days(ticker, fetchable)
        payload["ticker"] = ticker
        payload["coverage"].update({
            "requested_days": len(dates),
            "missing_days": len(missing),
            "synced_days": synced,
            "complete": not missing,
            "has_history": any(r["status"] == "ok" for r in stored.values()),
        })
        payload["backfill"] = self.client.get_lpm_job(ticker)
        return payload

    def _sync_newest(self, ticker, fetchable):
        """
        Fetch trading days newer than the latest stored day, at most max_sync_fetch_days.
        Nothing is fetched for a ticker without history (the user starts a backfill explicitly)
        or while its backfill is running (that thread is already fetching).
        """
        stored = self.client.load_broker_daily(ticker, fetchable)
        known = [d for d, r in stored.items() if r["status"] in ("ok", "empty")]
        if not known or self.client.get_lpm_job(ticker)["state"] == "running":
            return 0

        latest = max(known)
        newer = [d for d in self.client.missing_broker_days(ticker, fetchable) if d > latest]
        fetched = 0
        for date in newer[:LPM_PARAMS["max_sync_fetch_days"]]:
            try:
                result = self.client.get_broker_daily(ticker, date)
            except RuntimeError:
                break
            if result and result["fetched"]:
                fetched += 1
        return fetched

    # -------------------------------------------------------------------------
    # POST /api/idx/lpm/<ticker>/backfill
    # -------------------------------------------------------------------------
    def start_backfill(self, ticker, days=None):
        n = days or LPM_PARAMS["history_days"]
        n = max(LPM_PARAMS["slope_slow"], min(MAX_BACKFILL_DAYS, n))
        fetchable = self._fetchable(self.trading_days(ticker, n))
        missing = self.client.missing_broker_days(ticker, fetchable)
        if not missing:
            return {"status": "complete", "missing_days": 0, "estimated_requests": 0}

        reserve = LPM_PARAMS["quota_reserve"]
        remaining = self.client.get_quota_status()["remaining"]
        if remaining - 1 < reserve:
            raise LPMQuotaError(
                f"Sisa kuota hari ini {remaining} request. Backfill dihentikan supaya cadangan "
                f"{reserve} request tetap tersedia untuk fitur lain. Coba lagi besok."
            )

        if not self.client.claim_lpm_job(ticker, len(missing)):
            job = self.client.get_lpm_job(ticker)
            return {"status": "running", "missing_days": job["total"] - job["done"], "estimated_requests": 0}

        thread = threading.Thread(target=self._run_backfill, args=(ticker, fetchable), daemon=True)
        self._threads[ticker] = thread
        thread.start()
        return {
            "status": "started",
            "missing_days": len(missing),
            "estimated_requests": min(len(missing), remaining - reserve),
        }

    def _run_backfill(self, ticker, dates):
        requested = 0

        def on_progress(done, total, date, result):
            nonlocal requested
            if result and result["fetched"]:
                requested += 1
            self.client.update_lpm_job(ticker, done=done, total=total, requested=requested)

        try:
            summary = self.client.backfill_broker_daily(ticker, dates, on_progress=on_progress)
            stopped = summary["stopped_reason"] in ("quota_reserve", "quota_exhausted")
            self.client.update_lpm_job(ticker, state="stopped_quota" if stopped else "done",
                                       requested=summary["requested"])
        except Exception as e:
            logger.exception(f"LPM backfill failed for {ticker}")
            self.client.update_lpm_job(ticker, state="error", last_error=str(e))
