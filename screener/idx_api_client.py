import os
import json
import sqlite3
import logging
import requests
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class IDXApiClient:
    """Client for IDX Edge API (stock.arjum.com) with smart SQLite caching and daily quota tracking."""

    BASE_URL = "https://stock.arjum.com"
    API_KEY = "sk_live_pHzfNvhf-prFU2zXdclByx0tBdS8UyYOTKid3LY_lms"
    DAILY_LIMIT = 1000

    def __init__(self, db_path="data/cache/idx_api_cache.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize cache and quota tracking tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Daily quota tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quota_usage (
                    date TEXT PRIMARY KEY,
                    request_count INTEGER DEFAULT 0
                )
            """)
            # Broker Summary Cache (TTL 1 trading day)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_broker_summary (
                    ticker TEXT,
                    date TEXT,
                    flow TEXT,
                    data TEXT,
                    cached_at TEXT,
                    PRIMARY KEY (ticker, date, flow)
                )
            """)
            # Broker Accumulation Cache (TTL 1 trading day)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_broker_accum (
                    ticker TEXT,
                    date TEXT,
                    data TEXT,
                    cached_at TEXT,
                    PRIMARY KEY (ticker, date)
                )
            """)
            # Financial Statements Cache (TTL 14 days)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_financials (
                    ticker TEXT PRIMARY KEY,
                    data TEXT,
                    cached_at TEXT,
                    expires_at TEXT
                )
            """)
            # Comprehensive Analysis Cache (TTL 1 day)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_analysis (
                    ticker TEXT,
                    date TEXT,
                    data TEXT,
                    cached_at TEXT,
                    PRIMARY KEY (ticker, date)
                )
            """)
            conn.commit()

    def get_quota_status(self):
        """Get today's quota usage and remaining requests."""
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT request_count FROM quota_usage WHERE date = ?", (today,))
            row = cursor.fetchone()
            used = row["request_count"] if row else 0

        remaining = max(0, self.DAILY_LIMIT - used)
        percent_used = round((used / self.DAILY_LIMIT) * 100, 1)
        return {
            "date": today,
            "used": used,
            "remaining": remaining,
            "limit": self.DAILY_LIMIT,
            "percent_used": percent_used
        }

    def _record_request(self):
        """Record an API request to the quota tracker."""
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO quota_usage (date, request_count) 
                VALUES (?, 1)
                ON CONFLICT(date) DO UPDATE SET request_count = request_count + 1
            """, (today,))
            conn.commit()

    def _clean_ticker(self, ticker):
        """Clean ticker string (e.g. 'BBCA.JK' -> 'BBCA')."""
        if not ticker or not isinstance(ticker, str):
            return ""
        clean = ticker.replace(".JK", "").strip().upper()
        if not re.match(r'^[A-Z]{4}$', clean):
            logger.warning(f"Invalid IDX ticker format rejected: '{clean}'")
            return ""
        return clean

    def _make_request(self, endpoint, params=None):
        """Make HTTP GET request to API with quota check and header authentication."""
        quota = self.get_quota_status()
        if quota["remaining"] <= 0:
            raise RuntimeError(f"Daily API quota limit ({self.DAILY_LIMIT} reqs) has been reached for today.")

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "X-API-Key": self.API_KEY,
            "Accept": "application/json"
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=12)
            self._record_request()
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"API Error {resp.status_code} for {url}: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"HTTP Request failed for {url}: {e}")
            return None

    # =========================================================================
    # 1. BROKER SUMMARY (BANDARMOLOGI)
    # =========================================================================
    def get_broker_summary(self, ticker, flow="all", force_refresh=False):
        """Fetch and analyze Broker Summary with caching and concentration scoring."""
        ticker = self._clean_ticker(ticker)
        if not ticker:
            return None
        today = datetime.now().strftime("%Y-%m-%d")

        # Check Cache
        if not force_refresh:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT data FROM cache_broker_summary 
                    WHERE ticker = ? AND date = ? AND flow = ?
                """, (ticker, today, flow))
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row["data"])
                    except Exception:
                        pass

        # Fetch from API with all_data=true to return all buyers & sellers
        raw = self._make_request(f"/api/broker-summary/{ticker}", params={"all_data": "true", "flow": flow})
        if not raw or "brokers" not in raw:
            return None

        # Analyze Bandarmologi
        analyzed = self._analyze_broker_summary(ticker, raw, flow)

        # Save to Cache
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache_broker_summary (ticker, date, flow, data, cached_at)
                VALUES (?, ?, ?, ?, ?)
            """, (ticker, today, flow, json.dumps(analyzed), datetime.now().isoformat()))
            conn.commit()

        return analyzed

    def _analyze_broker_summary(self, ticker, raw, flow):
        """Calculate Top 1, 3, 5 concentration and status."""
        brokers = raw.get("brokers", [])
        
        # Sort buyers (nval > 0 descending) and sellers (nval < 0 ascending)
        buyers = [b for b in brokers if b.get("nval", 0) > 0]
        sellers = [b for b in brokers if b.get("nval", 0) < 0]

        buyers.sort(key=lambda x: x.get("nval", 0), reverse=True)
        sellers.sort(key=lambda x: x.get("nval", 0))

        total_bval = sum(b.get("bval", 0) for b in brokers)
        total_sval = sum(b.get("sval", 0) for b in brokers)
        total_turnover = (total_bval + total_sval) / 2 if total_bval or total_sval else 0

        # Top 1, 3, 5 Net Buyers
        top1_buy = buyers[0]["nval"] if len(buyers) >= 1 else 0
        top3_buy = sum(b["nval"] for b in buyers[:3])
        top5_buy = sum(b["nval"] for b in buyers[:5])

        # Top 1, 3, 5 Net Sellers (absolute)
        top1_sell = abs(sellers[0]["nval"]) if len(sellers) >= 1 else 0
        top3_sell = abs(sum(b["nval"] for b in sellers[:3]))
        top5_sell = abs(sum(b["nval"] for b in sellers[:5]))

        # Concentration ratio against total buy/sell value
        top3_buy_ratio = round((top3_buy / total_bval * 100), 1) if total_bval > 0 else 0.0
        top3_sell_ratio = round((top3_sell / total_sval * 100), 1) if total_sval > 0 else 0.0

        # Classification Status
        status = "NEUTRAL"
        status_label = "Neutral"
        status_class = "neutral"

        if top3_buy > 0 and (top3_buy > top3_sell * 1.5 or top3_buy_ratio >= 40.0):
            status = "BIG_ACCUM"
            status_label = "Big Accumulation"
            status_class = "success"
        elif top3_buy > top3_sell * 1.1 or top3_buy_ratio >= 25.0:
            status = "NORMAL_ACCUM"
            status_label = "Normal Accumulation"
            status_class = "accent"
        elif top3_sell > 0 and (top3_sell > top3_buy * 1.5 or top3_sell_ratio >= 40.0):
            status = "BIG_DIST"
            status_label = "Big Distribution"
            status_class = "danger"
        elif top3_sell > top3_buy * 1.1 or top3_sell_ratio >= 25.0:
            status = "NORMAL_DIST"
            status_label = "Normal Distribution"
            status_class = "warning"

        return {
            "stock_code": ticker,
            "flow": flow,
            "latest_date": raw.get("latest_date"),
            "status": status,
            "status_label": status_label,
            "status_class": status_class,
            "total_turnover": total_turnover,
            "total_bval": total_bval,
            "total_sval": total_sval,
            "top3_buy_val": top3_buy,
            "top3_sell_val": top3_sell,
            "top3_buy_ratio": top3_buy_ratio,
            "top3_sell_ratio": top3_sell_ratio,
            "top_buyers": [
                {
                    "code": b.get("broker_code"),
                    "name": b.get("broker_name"),
                    "nval": b.get("nval"),
                    "bval": b.get("bval"),
                    "nvol": b.get("nvol")
                } for b in buyers[:5]
            ],
            "top_sellers": [
                {
                    "code": b.get("broker_code"),
                    "name": b.get("broker_name"),
                    "nval": b.get("nval"),
                    "sval": b.get("sval"),
                    "nvol": b.get("nvol")
                } for b in sellers[:5]
            ]
        }

    # =========================================================================
    # 2. BROKER ACCUMULATION (HISTORICAL TREND)
    # =========================================================================
    def get_broker_accumulation(self, ticker, top=3, force_refresh=False):
        """Fetch historical accumulation time series with caching."""
        ticker = self._clean_ticker(ticker)
        if not ticker:
            return None
        today = datetime.now().strftime("%Y-%m-%d")

        if not force_refresh:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT data FROM cache_broker_accum 
                    WHERE ticker = ? AND date = ?
                """, (ticker, today))
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row["data"])
                    except Exception:
                        pass

        raw = self._make_request(f"/api/broker-accumulation/{ticker}", params={"top": top})
        if not raw:
            return None

        top_buyers = raw.get("top_buyers", [])
        top_sellers = raw.get("top_sellers", [])
        series = raw.get("series", [])

        # Aggregate daily net flow for top buyers
        top_buyer_codes = [b.get("broker_code") for b in top_buyers]
        daily_map = {}
        for s in series:
            if s.get("broker_code") in top_buyer_codes:
                for pt in s.get("points", []):
                    dt = pt.get("date")
                    daily_map[dt] = daily_map.get(dt, 0) + pt.get("nval", 0)

        sorted_dates = sorted(daily_map.keys())
        daily_series = [{"date": dt, "accum_val": daily_map[dt]} for dt in sorted_dates[-7:]]

        # Calculate overall accumulation trend
        tot_buy = sum(b.get("total_nval", 0) for b in top_buyers)
        tot_sell = sum(abs(s.get("total_nval", 0)) for s in top_sellers)
        recent_sum = sum(daily_map[dt] for dt in sorted_dates[-5:]) if sorted_dates else 0

        if tot_buy > tot_sell * 1.1 or recent_sum > 0:
            trend = "UPTREND_ACCUM"
            trend_label = "📈 Accumulation Uptrend"
        elif tot_sell > tot_buy * 1.1 or recent_sum < 0:
            trend = "DOWNTREND_DIST"
            trend_label = "📉 Distribution Downtrend"
        else:
            trend = "NEUTRAL"
            trend_label = "→ Neutral Trend"

        payload = {
            "stock_code": ticker,
            "start_date": raw.get("start_date"),
            "end_date": raw.get("end_date"),
            "top_buyers": top_buyers,
            "top_sellers": top_sellers,
            "series": daily_series,
            "trend": trend,
            "trend_label": trend_label,
            "tot_buy": tot_buy,
            "tot_sell": tot_sell
        }

        # Cache
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache_broker_accum (ticker, date, data, cached_at)
                VALUES (?, ?, ?, ?)
            """, (ticker, today, json.dumps(payload), datetime.now().isoformat()))
            conn.commit()

        return payload

    # =========================================================================
    # 3. FINANCIAL STATEMENTS & EPS GROWTH (SEPA FUNDAMENTALS)
    # =========================================================================
    def get_financial_statements(self, ticker, period="quarterly", limit=8, force_refresh=False):
        """Fetch financial statements with 14-day caching and calculate YoY EPS growth."""
        ticker = self._clean_ticker(ticker)
        if not ticker:
            return None

        # Check Cache
        if not force_refresh:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT data, expires_at FROM cache_financials 
                    WHERE ticker = ?
                """, (ticker,))
                row = cursor.fetchone()
                if row:
                    expires = datetime.fromisoformat(row["expires_at"])
                    if datetime.now() < expires:
                        try:
                            return json.loads(row["data"])
                        except Exception:
                            pass

        raw = self._make_request(f"/api/financial-statements/{ticker}", params={
            "report_type": "INCOME_STATEMENT",
            "period": period,
            "limit": limit
        })
        if not raw or "items" not in raw:
            return None

        parsed = self._parse_financials(ticker, raw)

        # Cache with 14 days expiration
        expires_at = (datetime.now() + timedelta(days=14)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache_financials (ticker, data, cached_at, expires_at)
                VALUES (?, ?, ?, ?)
            """, (ticker, json.dumps(parsed), datetime.now().isoformat(), expires_at))
            conn.commit()

        return parsed

    def _parse_financials(self, ticker, raw):
        """Parse quarterly items, extract EPS, net profit, and calculate YoY EPS growth."""
        items = raw.get("items", [])
        parsed_items = []

        for it in items:
            year = str(it.get("year", ""))
            quarter = str(it.get("quarter", ""))
            label = it.get("label", f"Q{quarter} {year}")
            data = it.get("data", {})

            # Net profit (laba_rugi)
            net_profit = data.get("laba_rugi")
            if net_profit is None:
                net_profit = data.get("laba_rugi_dari_operasi_yang_dilanjutkan", 0)

            # EPS extraction
            eps_val = None
            eps_data = data.get("laba_rugi_per_saham")
            if isinstance(eps_data, (int, float)):
                eps_val = float(eps_data)
            elif isinstance(eps_data, dict):
                sub = eps_data.get("laba_per_saham_dasar_diatribusikan_kepada_pemilik_entitas_induk", {})
                if isinstance(sub, dict):
                    eps_val = sub.get("laba_rugi_per_saham_dasar_dari_operasi_yang_dilanjutkan")
                    if eps_val is None:
                        eps_val = sub.get("total")
                if eps_val is None:
                    eps_val = eps_data.get("total")

            parsed_items.append({
                "year": year,
                "quarter": quarter,
                "label": label,
                "net_profit": net_profit,
                "eps": eps_val
            })

        # Calculate YoY EPS Growth
        yoy_growth = None
        sepa_certified = False

        if len(parsed_items) >= 2:
            latest = parsed_items[0]
            # Find item with same quarter in previous year
            target_year = str(int(latest["year"]) - 1) if latest["year"].isdigit() else ""
            same_q_last_year = next((x for x in parsed_items if x["year"] == target_year and x["quarter"] == latest["quarter"]), None)

            # Fallback to the 4th item if available (quarterly series)
            if not same_q_last_year and len(parsed_items) >= 4:
                same_q_last_year = parsed_items[3]

            if latest.get("eps") is not None and same_q_last_year and same_q_last_year.get("eps") is not None:
                base_eps = same_q_last_year["eps"]
                if base_eps != 0:
                    yoy_growth = round(((latest["eps"] - base_eps) / abs(base_eps)) * 100, 1)
                    if yoy_growth >= 20.0:
                        sepa_certified = True

        return {
            "stock_code": ticker,
            "period": raw.get("period", "quarterly"),
            "items": parsed_items,
            "latest_eps": parsed_items[0]["eps"] if parsed_items else None,
            "latest_net_profit": parsed_items[0]["net_profit"] if parsed_items else None,
            "yoy_eps_growth": yoy_growth,
            "sepa_certified": sepa_certified
        }

    # =========================================================================
    # 4. COMPREHENSIVE ANALYSIS (AI VERDICT)
    # =========================================================================
    def get_comprehensive_analysis(self, ticker, force_refresh=False):
        """Fetch and parse comprehensive analysis markdown text."""
        ticker = self._clean_ticker(ticker)
        if not ticker:
            return None
        today = datetime.now().strftime("%Y-%m-%d")

        if not force_refresh:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT data FROM cache_analysis 
                    WHERE ticker = ? AND date = ?
                """, (ticker, today))
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row["data"])
                    except Exception:
                        pass

        raw = self._make_request(f"/api/analysis/{ticker}")
        if not raw or "output" not in raw:
            return None

        parsed = self._parse_analysis_output(ticker, raw.get("output", ""))

        # Cache
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache_analysis (ticker, date, data, cached_at)
                VALUES (?, ?, ?, ?)
            """, (ticker, today, json.dumps(parsed), datetime.now().isoformat()))
            conn.commit()

        return parsed

    def _parse_analysis_output(self, ticker, text):
        """Extract key metrics (Support/Resistance, Signals, Targets) from analysis output."""
        pivots = {}
        # Daily: R2 Rp6.917 | R1 Rp6.808 | P Rp6.742 | S1 Rp6.633 | S2 Rp6.567
        pivot_match = re.search(r"Daily:\s*R2\s*(Rp[\d\.\,]+)\s*\|\s*R1\s*(Rp[\d\.\,]+)\s*\|\s*P\s*(Rp[\d\.\,]+)\s*\|\s*S1\s*(Rp[\d\.\,]+)\s*\|\s*S2\s*(Rp[\d\.\,]+)", text, re.IGNORECASE)
        if pivot_match:
            pivots = {
                "r2": pivot_match.group(1),
                "r1": pivot_match.group(2),
                "p": pivot_match.group(3),
                "s1": pivot_match.group(4),
                "s2": pivot_match.group(5)
            }

        # Score & Sinyal Utama
        score_match = re.search(r"Score:\s*\*\*([^\*]+)\*\*", text, re.IGNORECASE)
        score = score_match.group(1).strip() if score_match else None

        signal_verdict = None
        signal_desc = None
        signal_line = re.search(r"Score:\s*\*\*[^\*]+\*\*\s*—\s*([^\n\r]+)", text)
        if signal_line:
            raw_sig = signal_line.group(1).strip()
            parts = [p.strip() for p in raw_sig.split("—")]
            signal_verdict = parts[0].replace("*", "") if parts else raw_sig
            signal_desc = parts[1] if len(parts) > 1 else ""
        else:
            sig_alt = re.search(r"Sinyal Utama\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
            if sig_alt:
                signal_verdict = sig_alt.group(1).strip()

        # Rekomendasi Trading Tactical Plan
        recom_action = None
        jika_punya = None
        jika_belum_punya = None
        stop_loss = None

        recom_idx = text.find("**📋 REKOMENDASI**")
        if recom_idx != -1:
            recom_section = text[recom_idx:]
            act_match = re.search(r"\*\*📋 REKOMENDASI\*\*\s*\n\s*([^\n\r]+)", recom_section)
            if act_match:
                recom_action = act_match.group(1).replace("*", "").strip()
            punya_match = re.search(r"Jika sudah punya:\s*([^\n\r]+)", recom_section, re.IGNORECASE)
            if punya_match:
                jika_punya = punya_match.group(1).strip()
            belum_match = re.search(r"Jika belum punya:\s*([^\n\r]+)", recom_section, re.IGNORECASE)
            if belum_match:
                jika_belum_punya = belum_match.group(1).strip()
            sl_match = re.search(r"Stop Loss:\s*([^\n\r]+)", recom_section, re.IGNORECASE)
            if sl_match:
                stop_loss = sl_match.group(1).strip()

        # Entry & Target Matches
        entry_match = re.search(r"Entry Area\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        target1_match = re.search(r"Target 1\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        target2_match = re.search(r"Target 2\s*:\s*([^\n\r]+)", text, re.IGNORECASE)

        trading_plan = {
            "action": recom_action or signal_verdict or "MONITOR",
            "score": score,
            "signal_desc": signal_desc,
            "jika_belum_punya": jika_belum_punya or (entry_match.group(1).strip() if entry_match else "Tunggu konfirmasi breakout di atas pivot/R1"),
            "jika_punya": jika_punya or "Pasang trailing stop sesuai toleransi risiko",
            "stop_loss": stop_loss or pivots.get("s2") or pivots.get("s1") or "—",
            "target1": target1_match.group(1).strip() if target1_match else (pivots.get("r1") or "—"),
            "target2": target2_match.group(1).strip() if target2_match else (pivots.get("r2") or "—")
        }

        # Akumulasi text
        accum_match = re.search(r"Akumulasi\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        accum_text = accum_match.group(1).strip() if accum_match else None

        return {
            "stock_code": ticker,
            "raw_output": text,
            "pivots": pivots,
            "main_signal": signal_verdict or recom_action or "MONITOR",
            "accum_text": accum_text,
            "trading_plan": trading_plan
        }
