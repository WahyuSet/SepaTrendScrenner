import os
import json
import time
import threading
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, Response
from screener.calculator import SEPACalculator
from screener.rsi_divergence import RSIDivergenceCalculator
from screener.pre_breakout import PreBreakoutCalculator
from screener.market_regime import MarketRegimeEvaluator
from screener.quality_screener import (
    run_quality_scan,
    get_cached_quality_results,
    get_quality_scan_status
)
from screener.journal_db import (
    get_all_watchlist,
    get_watchlist_tickers,
    add_to_watchlist,
    remove_from_watchlist,
    calculate_position_sizing,
    get_all_trades,
    get_trade_by_id,
    add_trade,
    close_trade,
    delete_trade,
    get_journal_stats,
    get_settings,
    save_settings,
    export_trades_to_csv,
    backup_to_json,
    restore_from_json
)
from screener.idx_api_client import IDXApiClient
from screener.backtest_engine import SignalBacktestEngine
from screener.auth import (
    get_secret_key,
    get_session_durations,
    verify_credentials,
    is_rate_limited,
    record_failed_attempt,
    clear_failed_attempts,
    get_remaining_lockout_seconds,
    admin_required
)

app = Flask(__name__)
app.secret_key = get_secret_key()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

idx_client = IDXApiClient()
backtest_engine = SignalBacktestEngine()

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "scan_result.json")
RSI_CACHE_FILE = os.path.join(CACHE_DIR, "rsi_div_result.json")
PREBREAKOUT_CACHE_FILE = os.path.join(CACHE_DIR, "pre_breakout_result.json")
MARKET_REGIME_CACHE_FILE = os.path.join(CACHE_DIR, "market_regime.json")
TICKERS_FILE = os.path.join(os.path.dirname(__file__), "data", "idx_master_tickers.json")
MASTER_TICKERS_FILE = os.path.join(os.path.dirname(__file__), "data", "idx_master_tickers.json")

def load_master_tickers():
    """Load master list of 941 IDX listed companies."""
    if os.path.exists(MASTER_TICKERS_FILE):
        try:
            with open(MASTER_TICKERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading master tickers: {e}")
    return []

MASTER_TICKERS_LIST = load_master_tickers()
VALID_IDX_TICKERS = {item["ticker"] for item in MASTER_TICKERS_LIST} if MASTER_TICKERS_LIST else set()
IDX_TICKER_META = {item["ticker"]: item for item in MASTER_TICKERS_LIST} if MASTER_TICKERS_LIST else {}

def is_valid_idx_ticker(ticker):
    """Check if ticker is a valid IDX common stock symbol."""
    if not ticker or not isinstance(ticker, str):
        return False
    clean = ticker.replace(".JK", "").strip().upper()
    return clean in VALID_IDX_TICKERS

def get_idx_market_status():
    """Get current IDX market trading status based on Jakarta time (WIB / UTC+7)."""
    jakarta_tz = timezone(timedelta(hours=7))
    now = datetime.now(jakarta_tz)
    weekday = now.weekday()  # 0 = Monday, 6 = Sunday
    t_min = now.hour * 60 + now.minute

    if weekday in (5, 6):
        return {
            "status": "closed",
            "label": "IDX Closed",
            "detail": "Pasar Libur (Akhir Pekan)",
            "is_open": False
        }

    is_friday = (weekday == 4)
    s1_end = 11 * 60 + 30 if is_friday else 12 * 60
    s2_start = 14 * 60 if is_friday else 13 * 60 + 30

    if t_min < 8 * 60 + 45:
        return {"status": "closed", "label": "IDX Closed", "detail": "Buka Sesi 1 jam 09:00 WIB", "is_open": False}
    elif t_min < 9 * 60:
        return {"status": "break", "label": "IDX Pre-Open", "detail": "Pra-Pembukaan (08:45 - 08:59 WIB)", "is_open": False}
    elif t_min < s1_end:
        return {"status": "open", "label": "IDX Open (Sesi 1)", "detail": "Perdagangan Sesi 1 Aktif", "is_open": True}
    elif t_min < s2_start:
        return {"status": "break", "label": "IDX Break", "detail": "Istirahat Siang Pasar", "is_open": False}
    elif t_min < 15 * 60 + 50:
        return {"status": "open", "label": "IDX Open (Sesi 2)", "detail": "Perdagangan Sesi 2 Aktif", "is_open": True}
    elif t_min <= 16 * 60 + 15:
        return {"status": "break", "label": "IDX Pre-Close", "detail": "Pra-Penutupan (15:50 - 16:15 WIB)", "is_open": False}
    else:
        return {"status": "closed", "label": "IDX Closed", "detail": "Pasar Tutup", "is_open": False}

# Global scan status state
scan_state = {
    "is_scanning": False,
    "progress_current": 0,
    "progress_total": 0,
    "current_ticker": "",
    "started_at": None,
    "error": None
}

scan_lock = threading.Lock()

def load_cached_results():
    """Load SEPA results from cache JSON file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
    return None

def save_cached_results(data):
    """Save SEPA results to cache JSON file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}")

def load_rsi_cached_results():
    """Load RSI Divergence results from cache JSON file."""
    if os.path.exists(RSI_CACHE_FILE):
        try:
            with open(RSI_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading RSI cache: {e}")
    return None

def save_rsi_cached_results(data):
    """Save RSI Divergence results to cache JSON file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(RSI_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving RSI cache: {e}")

def load_prebreakout_cached_results():
    """Load Pre-Breakout results from cache JSON file."""
    if os.path.exists(PREBREAKOUT_CACHE_FILE):
        try:
            with open(PREBREAKOUT_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading Pre-Breakout cache: {e}")
    return None

def save_prebreakout_cached_results(data):
    """Save Pre-Breakout results to cache JSON file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(PREBREAKOUT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving Pre-Breakout cache: {e}")

def load_market_regime_cached_results():
    """Load Market Regime from cache JSON file."""
    if os.path.exists(MARKET_REGIME_CACHE_FILE):
        try:
            with open(MARKET_REGIME_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading Market Regime cache: {e}")
    regime_eval = MarketRegimeEvaluator(cache_dir=CACHE_DIR)
    return regime_eval.get_cached_or_default()

def background_scan_worker():
    """Background worker that performs the screening on all IDX tickers (SEPA + RSI + Pre-Breakout)."""
    global scan_state
    try:
        with scan_lock:
            scan_state["is_scanning"] = True
            scan_state["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            scan_state["error"] = None

        calc = SEPACalculator(tickers_csv_path=TICKERS_FILE)
        
        # Step 1: Benchmark
        scan_state["current_ticker"] = "IHSG (^JKSE)"
        calc.rs_calc.fetch_benchmark()

        # Step 2: Fetch tickers
        tickers = calc.fetcher.tickers_df['ticker'].tolist() if calc.fetcher.tickers_df is not None else []
        scan_state["progress_total"] = len(tickers)
        scan_state["progress_current"] = 0

        # Concurrent fetch with progress tracking
        results = []
        all_data = {}
        max_workers = 16
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(calc.fetcher.fetch_single_ticker, t, "2y"): t
                for t in tickers
            }

            for future in as_completed(future_to_ticker):
                try:
                    t, df, err = future.result()
                    scan_state["progress_current"] += 1
                    scan_state["current_ticker"] = t
                    if df is not None:
                        clean = df.dropna(subset=["Close"])
                        if len(clean) >= 50:
                            all_data[t] = clean
                except Exception as ex:
                    print(f"Error processing future: {ex}")

        # Step 3: Evaluate SEPA Criteria
        scan_state["current_ticker"] = "Evaluasi SEPA Trend..."
        for ticker, df in all_data.items():
            eval_res = calc.evaluate_stock(ticker, df)
            if eval_res is not None:
                results.append(eval_res)

        # Sort: total_score desc, rs_score desc, dist_low_pct desc
        results.sort(key=lambda x: (x['total_score'], x['rs_score'], x['dist_low_pct']), reverse=True)

        confirmed_count = sum(1 for r in results if r['status'] == 'CONFIRMED')
        watchlist_count = sum(1 for r in results if r['status'] == 'WATCHLIST')

        time_str = datetime.now().strftime("%d %b %Y, %H:%M WIB")
        iso_time = datetime.now().isoformat()

        payload = {
            "timestamp": time_str,
            "iso_timestamp": iso_time,
            "stats": {
                "total_universe": len(tickers),
                "total_scanned": len(results),
                "confirmed_count": confirmed_count,
                "watchlist_count": watchlist_count,
                "unqualified_count": len(results) - (confirmed_count + watchlist_count)
            },
            "results": results
        }
        save_cached_results(payload)

        # Step 4: Evaluate RSI Divergence (using pre-downloaded all_data, zero extra latency)
        scan_state["current_ticker"] = "Evaluasi RSI Divergence..."
        rsi_calc = RSIDivergenceCalculator(tickers_csv_path=TICKERS_FILE)
        rsi_results = []

        for ticker, df in all_data.items():
            rsi_res = rsi_calc.detect_divergence(ticker, df)
            if rsi_res is not None:
                rsi_results.append(rsi_res)

        # Sort: bars_ago ASC (freshest first), then RSI ASC (most oversold)
        rsi_results.sort(key=lambda x: (x['bars_ago'], x['rsi']))

        reg_bull_count = sum(1 for r in rsi_results if r['divergence_type'] == 'REGULAR_BULL')
        hid_bull_count = sum(1 for r in rsi_results if r['divergence_type'] == 'HIDDEN_BULL')

        rsi_payload = {
            "timestamp": time_str,
            "iso_timestamp": iso_time,
            "stats": {
                "total_universe": len(tickers),
                "total_scanned": len(all_data),
                "total_divergences": len(rsi_results),
                "regular_bull_count": reg_bull_count,
                "hidden_bull_count": hid_bull_count
            },
            "results": rsi_results
        }
        save_rsi_cached_results(rsi_payload)

        # Step 5: Evaluate Pre-Breakout Setups (using pre-downloaded all_data, zero extra network latency)
        scan_state["current_ticker"] = "Evaluasi Pre-Breakout Setup..."
        pb_calc = PreBreakoutCalculator(tickers_csv_path=TICKERS_FILE, min_turnover_20d=500_000_000)
        pb_results = []

        for ticker, df in all_data.items():
            pb_res = pb_calc.evaluate_stock(ticker, df)
            if pb_res is not None:
                pb_results.append(pb_res)

        # Sort: total_score DESC, is_vcp_tight DESC, is_vdu DESC, dist_res_pct ASC (closest first), rvol DESC
        pb_results.sort(key=lambda x: (x['total_score'], x['is_vcp_tight'], x['is_vdu'], -x['dist_res_pct'], x['rvol']), reverse=True)

        ready_count = sum(1 for r in pb_results if r['status'] == 'READY')
        forming_count = sum(1 for r in pb_results if r['status'] == 'FORMING')

        pb_payload = {
            "timestamp": time_str,
            "iso_timestamp": iso_time,
            "stats": {
                "total_universe": len(tickers),
                "total_scanned": len(all_data),
                "total_setups": len(pb_results),
                "ready_count": ready_count,
                "forming_count": forming_count
            },
            "results": pb_results
        }
        save_prebreakout_cached_results(pb_payload)

        # Step 6: Evaluate Market Regime & Cross-Reference SEPA + VCP
        scan_state["current_ticker"] = "Evaluasi Market Regime IHSG..."
        regime_eval = MarketRegimeEvaluator(cache_dir=CACHE_DIR)
        regime_eval.evaluate(df=calc.rs_calc.bench_data)

        # Cross-reference SEPA Confirmed with Pre-Breakout Ready
        ready_pb_tickers = set(r['ticker'] for r in pb_results if r['status'] == 'READY')
        for r in results:
            if r['status'] == 'CONFIRMED' and r['ticker'] in ready_pb_tickers:
                r['is_sepa_vcp_ready'] = True
                r['sepa_vcp_badge'] = '⭐ SEPA + VCP READY'
            else:
                r['is_sepa_vcp_ready'] = False
                r['sepa_vcp_badge'] = None

        # Re-save SEPA results with cross-referenced badge
        save_cached_results(payload)

        # Step 7: Evaluate Quality Setup across 941 IDX Universe
        scan_state["current_ticker"] = "Evaluasi Quality Setup (941 IDX)..."
        try:
            run_quality_scan(max_workers=16, preloaded_data=all_data)
        except Exception as qe:
            print(f"Quality scan worker warning: {qe}")

    except Exception as e:
        scan_state["error"] = str(e)
        print(f"Scan worker failed: {e}")
    finally:
        with scan_lock:
            scan_state["is_scanning"] = False
            scan_state["current_ticker"] = ""

# =========================================================================
# AUTHENTICATION & SESSION ROUTES
# =========================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    """Render login page (GET) or authenticate admin credentials (POST)."""
    if request.method == "GET":
        if session.get("is_admin"):
            return redirect(url_for("index"))
        return render_template("login.html")

    # POST handling
    data = request.get_json(silent=True) or request.form
    username = data.get("username", "").strip()
    password = data.get("password", "")
    remember = str(data.get("remember", "false")).lower() in ["true", "1", "on"]

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()

    # 1. Check Rate Limit
    if is_rate_limited(client_ip):
        rem_sec = get_remaining_lockout_seconds(client_ip)
        rem_min = max(1, (rem_sec + 59) // 60)
        return jsonify({
            "status": "error",
            "code": "RATE_LIMITED",
            "message": f"Terlalu banyak percobaan gagal. Silakan coba lagi dalam {rem_min} menit."
        }), 429

    # 2. Verify Credentials
    if not verify_credentials(username, password):
        record_failed_attempt(client_ip)
        return jsonify({
            "status": "error",
            "code": "INVALID_CREDENTIALS",
            "message": "Username atau password yang Anda masukkan salah."
        }), 401

    # 3. Successful Login
    clear_failed_attempts(client_ip)
    standard_days, remember_days = get_session_durations()
    session_days = remember_days if remember else standard_days

    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=session_days)
    session["is_admin"] = True
    session["username"] = username
    session["login_time"] = datetime.now().isoformat()

    next_url = request.args.get("next") or "/"
    return jsonify({
        "status": "success",
        "message": "Login berhasil.",
        "redirect": next_url
    })

@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear active admin session and redirect to login."""
    session.clear()
    return redirect(url_for("login"))

@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Check current session status."""
    return jsonify({
        "is_authenticated": bool(session.get("is_admin")),
        "username": session.get("username", None)
    })

# =========================================================================
# PROTECTED APPLICATION & SCREENER ROUTES
# =========================================================================

@app.route("/")
@admin_required
def index():
    """Render main application page with initial scan and market status."""
    cached = load_cached_results()
    last_scan_time = cached.get("timestamp") if cached else None
    market_status = get_idx_market_status()
    return render_template("index.html", last_scan_time=last_scan_time, market_status=market_status)

@app.route("/api/results", methods=["GET"])
@admin_required
def get_results():
    """Get the most recent cached screening results."""
    cached = load_cached_results()
    if cached:
        return jsonify({"status": "success", "data": cached})
    return jsonify({
        "status": "empty",
        "data": {
            "timestamp": None,
            "stats": {"total_universe": 0, "total_scanned": 0, "confirmed_count": 0, "watchlist_count": 0, "unqualified_count": 0},
            "results": []
        }
    })

@app.route("/api/rsi-divergence", methods=["GET"])
@admin_required
def get_rsi_results():
    """Get the most recent cached RSI Divergence screening results."""
    cached = load_rsi_cached_results()
    if cached:
        return jsonify({"status": "success", "data": cached})
    return jsonify({
        "status": "empty",
        "data": {
            "timestamp": None,
            "stats": {
                "total_universe": 0,
                "total_scanned": 0,
                "total_divergences": 0,
                "regular_bull_count": 0,
                "hidden_bull_count": 0
            },
            "results": []
        }
    })

@app.route("/api/pre-breakout", methods=["GET"])
@admin_required
def get_prebreakout_results():
    """Get the most recent cached Pre-Breakout screening results."""
    cached = load_prebreakout_cached_results()
    if cached:
        return jsonify({"status": "success", "data": cached})
    return jsonify({
        "status": "empty",
        "data": {
            "timestamp": None,
            "stats": {
                "total_universe": 0,
                "total_scanned": 0,
                "total_setups": 0,
                "ready_count": 0,
                "forming_count": 0
            },
            "results": []
        }
    })

@app.route("/api/market-regime", methods=["GET"])
@admin_required
def get_market_regime():
    """Get current IHSG Market Regime status and exposure recommendation."""
    data = load_market_regime_cached_results()
    return jsonify({"status": "success", "data": data})

@app.route("/api/scan", methods=["POST"])
@admin_required
def trigger_scan():
    """Trigger a new scan in background thread."""
    global scan_state
    if scan_state["is_scanning"]:
        return jsonify({"status": "running", "message": "Scan is already in progress"}), 409

    t = threading.Thread(target=background_scan_worker, daemon=True)
    t.start()
    return jsonify({"status": "started", "message": "Screening initiated in background"})

@app.route("/api/status", methods=["GET"])
@admin_required
def get_status():
    """Get current scanning progress and status."""
    cached = load_cached_results()
    last_scan_time = cached.get("timestamp") if cached else None
    stats = cached.get("stats") if cached else None

    return jsonify({
        "is_scanning": scan_state["is_scanning"],
        "progress_current": scan_state["progress_current"],
        "progress_total": scan_state["progress_total"],
        "current_ticker": scan_state["current_ticker"],
        "started_at": scan_state["started_at"],
        "error": scan_state["error"],
        "last_scan_time": last_scan_time,
        "market_status": get_idx_market_status(),
        "stats": stats
    })

# =========================================================================
# QUALITY SETUP SCREENER API ENDPOINTS
# =========================================================================

@app.route("/api/quality-setup", methods=["GET"])
@app.route("/api/results/quality-setup", methods=["GET"])
@admin_required
def get_quality_setup_results():
    """Get the cached Quality Setup screening results (Elite & Strong)."""
    cached = get_cached_quality_results()
    if cached:
        return jsonify({"status": "success", "data": cached})
    return jsonify({
        "status": "empty",
        "data": {
            "scan_time": None,
            "total_scanned": 0,
            "passed_count": 0,
            "elite_count": 0,
            "strong_count": 0,
            "breakout_count": 0,
            "pullback_count": 0,
            "avg_rr": 0,
            "data": []
        }
    })

@app.route("/api/scan/quality-setup", methods=["POST"])
@admin_required
def trigger_quality_scan():
    """Trigger Quality Setup scan over 941 IDX stocks in background."""
    status = get_quality_scan_status()
    if status["is_scanning"]:
        return jsonify({"status": "running", "message": "Quality Setup scan is already in progress"}), 409

    t = threading.Thread(target=run_quality_scan, kwargs={"max_workers": 16}, daemon=True)
    t.start()
    return jsonify({"status": "started", "message": "Quality Setup scan initiated in background"})

@app.route("/api/status/quality-setup", methods=["GET"])
@admin_required
def get_quality_status():
    """Get status of Quality Setup scan."""
    return jsonify(get_quality_scan_status())

# =========================================================================
# IDX EDGE PRO API ENDPOINTS (ON-DEMAND & CACHED)
# =========================================================================

@app.route("/api/idx/tickers", methods=["GET"])
@admin_required
def get_idx_master_tickers():
    """Get master list of 941 IDX listed companies for autocomplete and client validation."""
    return jsonify({
        "status": "success",
        "count": len(MASTER_TICKERS_LIST),
        "data": MASTER_TICKERS_LIST
    })

@app.route("/api/idx/quota", methods=["GET"])
@admin_required
def get_idx_quota():
    """Get current daily API quota usage and remaining count."""
    try:
        quota = idx_client.get_quota_status()
        return jsonify({"status": "success", "data": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/idx/broker-summary/<ticker>", methods=["GET"])
@admin_required
def get_idx_broker_summary(ticker):
    """Get broker summary and Bandarmologi metrics for a ticker."""
    clean_ticker = ticker.replace(".JK", "").strip().upper()
    if not is_valid_idx_ticker(clean_ticker):
        return jsonify({
            "status": "error",
            "message": f"Ticker '{clean_ticker}' tidak terdaftar di Bursa Efek Indonesia (IDX)"
        }), 404

    flow = request.args.get("flow", "all")
    force = request.args.get("force", "false").lower() == "true"
    try:
        data = idx_client.get_broker_summary(clean_ticker, flow=flow, force_refresh=force)
        quota = idx_client.get_quota_status()
        if not data:
            return jsonify({"status": "error", "message": f"Broker summary not found for {clean_ticker}"}), 404
        return jsonify({"status": "success", "data": data, "quota": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/idx/broker-accumulation/<ticker>", methods=["GET"])
@admin_required
def get_idx_broker_accum(ticker):
    """Get historical broker accumulation time series for a ticker."""
    clean_ticker = ticker.replace(".JK", "").strip().upper()
    if not is_valid_idx_ticker(clean_ticker):
        return jsonify({
            "status": "error",
            "message": f"Ticker '{clean_ticker}' tidak terdaftar di Bursa Efek Indonesia (IDX)"
        }), 404

    top = int(request.args.get("top", 3))
    force = request.args.get("force", "false").lower() == "true"
    try:
        data = idx_client.get_broker_accumulation(clean_ticker, top=top, force_refresh=force)
        quota = idx_client.get_quota_status()
        if not data:
            return jsonify({"status": "error", "message": f"Accumulation data not found for {clean_ticker}"}), 404
        return jsonify({"status": "success", "data": data, "quota": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/idx/financials/<ticker>", methods=["GET"])
@admin_required
def get_idx_financials(ticker):
    """Get financial statements and YoY EPS growth for a ticker."""
    clean_ticker = ticker.replace(".JK", "").strip().upper()
    if not is_valid_idx_ticker(clean_ticker):
        return jsonify({
            "status": "error",
            "message": f"Ticker '{clean_ticker}' tidak terdaftar di Bursa Efek Indonesia (IDX)"
        }), 404

    force = request.args.get("force", "false").lower() == "true"
    try:
        data = idx_client.get_financial_statements(clean_ticker, force_refresh=force)
        quota = idx_client.get_quota_status()
        if not data:
            return jsonify({"status": "error", "message": f"Financials not found for {clean_ticker}"}), 404
        return jsonify({"status": "success", "data": data, "quota": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/idx/analysis/<ticker>", methods=["GET"])
@admin_required
def get_idx_analysis(ticker):
    """Get comprehensive automated analysis and trading plan for a ticker."""
    clean_ticker = ticker.replace(".JK", "").strip().upper()
    if not is_valid_idx_ticker(clean_ticker):
        return jsonify({
            "status": "error",
            "message": f"Ticker '{clean_ticker}' tidak terdaftar di Bursa Efek Indonesia (IDX)"
        }), 404

    force = request.args.get("force", "false").lower() == "true"
    try:
        data = idx_client.get_comprehensive_analysis(clean_ticker, force_refresh=force)
        quota = idx_client.get_quota_status()
        if not data:
            return jsonify({"status": "error", "message": f"Analysis not found for {clean_ticker}"}), 404
        return jsonify({"status": "success", "data": data, "quota": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# =========================================================================
# WATCHLIST & TRADE JOURNAL API ENDPOINTS (SQLITE BACKED)
# =========================================================================

@app.route("/api/watchlist", methods=["GET"])
@admin_required
def api_get_watchlist():
    """Get all pinned stocks in personal watchlist with active tickers set."""
    try:
        items = get_all_watchlist()
        tickers = list(get_watchlist_tickers())
        return jsonify({"status": "success", "data": items, "tickers": tickers, "total": len(items)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/watchlist/pin", methods=["POST"])
@admin_required
def api_pin_stock():
    """Add or update stock in personal watchlist."""
    data = request.get_json(silent=True) or request.form
    ticker = data.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"status": "error", "message": "Ticker diperlukan"}), 400

    name = data.get("name", ticker)
    sector = data.get("sector", "General")
    source = data.get("source", "Manual")
    notes = data.get("notes", "")

    try:
        item = add_to_watchlist(ticker, name, sector, source, notes)
        tickers = list(get_watchlist_tickers())
        return jsonify({"status": "success", "data": item, "tickers": tickers, "message": f"{ticker} ditambahkan ke Watchlist"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/watchlist/unpin/<ticker>", methods=["DELETE"])
@admin_required
def api_unpin_stock(ticker):
    """Remove stock from personal watchlist."""
    clean_ticker = ticker.replace(".JK", "").strip().upper()
    try:
        removed = remove_from_watchlist(clean_ticker)
        tickers = list(get_watchlist_tickers())
        return jsonify({"status": "success", "removed": removed, "tickers": tickers, "message": f"{clean_ticker} dihapus dari Watchlist"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/calculator/position-sizing", methods=["POST"])
@admin_required
def api_calc_position_sizing():
    """Calculate Minervini position sizing and risk allocation."""
    data = request.get_json(silent=True) or request.form
    try:
        capital = float(data.get("portfolio_capital", 100000000))
        risk_pct = float(data.get("risk_pct", 1.0))
        entry = float(data.get("entry_price", 0))
        sl = float(data.get("stop_loss", 0))
        t1 = float(data.get("target_1")) if data.get("target_1") else None
        t2 = float(data.get("target_2")) if data.get("target_2") else None
        max_cap = float(data.get("max_cap_pct", 20.0))
        buy_fee = float(data.get("buy_fee_pct", 0.15))
        sell_fee = float(data.get("sell_fee_pct", 0.25))
        fee_enabled = str(data.get("fee_enabled", "true")).lower() in ["true", "1", "on"]

        res = calculate_position_sizing(
            portfolio_capital=capital,
            risk_pct=risk_pct,
            entry_price=entry,
            stop_loss=sl,
            target_1=t1,
            target_2=t2,
            max_cap_pct=max_cap,
            buy_fee_pct=buy_fee,
            sell_fee_pct=sell_fee,
            fee_enabled=fee_enabled
        )
        return jsonify({"status": "success", "data": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/journal", methods=["GET"])
@admin_required
def api_get_journal():
    """Get trade journal entries with optional status filter."""
    status_filter = request.args.get("status", "ALL")
    try:
        trades = get_all_trades(status_filter)
        stats = get_journal_stats()
        return jsonify({"status": "success", "data": trades, "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/journal/entry", methods=["POST"])
@admin_required
def api_add_journal_entry():
    """Create a new open trade entry."""
    data = request.get_json(silent=True) or request.form
    ticker = data.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"status": "error", "message": "Ticker diperlukan"}), 400

    try:
        trade = add_trade(
            ticker=ticker,
            name=data.get("name", ticker),
            sector=data.get("sector", "General"),
            buy_date=data.get("buy_date", datetime.now().strftime("%Y-%m-%d")),
            buy_price=float(data.get("buy_price", 0)),
            lots=int(data.get("lots", 1)),
            stop_loss=float(data.get("stop_loss")) if data.get("stop_loss") else None,
            target_1=float(data.get("target_1")) if data.get("target_1") else None,
            target_2=float(data.get("target_2")) if data.get("target_2") else None,
            setup_type=data.get("setup_type", "Breakout"),
            notes=data.get("notes", ""),
            chart_url=data.get("chart_url", ""),
            broker_fee_enabled=str(data.get("broker_fee_enabled", "true")).lower() in ["true", "1", "on"]
        )
        stats = get_journal_stats()
        return jsonify({"status": "success", "data": trade, "stats": stats, "message": f"Transaksi {ticker} berhasil dicatat"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/journal/close/<int:trade_id>", methods=["PUT", "POST"])
@admin_required
def api_close_trade(trade_id):
    """Close an open trade."""
    data = request.get_json(silent=True) or request.form
    exit_date = data.get("exit_date", datetime.now().strftime("%Y-%m-%d"))
    try:
        exit_price = float(data.get("exit_price", 0))
        exit_reason = data.get("exit_reason", "MANUAL")
        notes = data.get("notes", "")

        closed = close_trade(trade_id, exit_date, exit_price, exit_reason, notes)
        stats = get_journal_stats()
        return jsonify({"status": "success", "data": closed, "stats": stats, "message": f"Posisi #{trade_id} berhasil ditutup"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/journal/<int:trade_id>", methods=["DELETE"])
@admin_required
def api_delete_trade(trade_id):
    """Delete a trade from the journal."""
    try:
        deleted = delete_trade(trade_id)
        stats = get_journal_stats()
        return jsonify({"status": "success", "deleted": deleted, "stats": stats, "message": f"Transaksi #{trade_id} dihapus"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/journal/stats", methods=["GET"])
@admin_required
def api_get_journal_stats():
    """Get portfolio journal statistics."""
    try:
        stats = get_journal_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/journal/export/csv", methods=["GET"])
@admin_required
def api_export_journal_csv():
    """Download trade journal as CSV file."""
    try:
        csv_data = export_trades_to_csv()
        filename = f"tirexxz_trade_journal_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/journal/backup", methods=["GET"])
@admin_required
def api_backup_journal_json():
    """Download complete backup as JSON."""
    try:
        backup = backup_to_json()
        filename = f"tirexxz_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        return Response(
            json.dumps(backup, indent=2, ensure_ascii=False),
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/journal/restore", methods=["POST"])
@admin_required
def api_restore_journal_json():
    """Restore database from uploaded JSON backup."""
    try:
        if "file" in request.files:
            file = request.files["file"]
            content = file.read().decode("utf-8")
            data = json.loads(content)
        else:
            data = request.get_json(silent=True) or {}

        result = restore_from_json(data)
        stats = get_journal_stats()
        return jsonify({"status": "success", "result": result, "stats": stats, "message": "Data berhasil dipulihkan"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/api/settings/money-management", methods=["GET", "POST"])
@admin_required
def api_money_management_settings():
    """Get or save user money management settings."""
    if request.method == "GET":
        return jsonify({"status": "success", "data": get_settings()})

    data = request.get_json(silent=True) or request.form
    try:
        saved = save_settings(data)
        return jsonify({"status": "success", "data": saved, "message": "Pengaturan berhasil disimpan"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# =========================================================================
# SIGNAL BACKTEST & ACCURACY LAB API ENDPOINTS
# =========================================================================
@app.route("/api/backtest/summary", methods=["GET"])
def api_backtest_summary():
    """Return pre-computed or on-demand benchmark backtest statistics."""
    try:
        years = int(request.args.get("years", 2))
        summary = backtest_engine.get_cached_benchmark_summary(years=years)
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Backtest summary error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/backtest/ticker", methods=["GET"])
def api_backtest_ticker():
    """Run on-demand backtest for a specific ticker over requested period."""
    ticker = request.args.get("symbol", "").strip().upper()
    if not ticker:
        return jsonify({"status": "error", "message": "Parameter symbol wajib diisi"}), 400
    try:
        years = int(request.args.get("years", 2))
        res = backtest_engine.run_ticker_backtest(ticker, years=years)
        return jsonify(res)
    except Exception as e:
        logger.error(f"Backtest ticker error for {ticker}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/backtest/trades", methods=["GET"])
def api_backtest_trades():
    """Get list of historical backtested trades with optional filters."""
    try:
        run_id = request.args.get("run_id", "benchmark_2y")
        setup = request.args.get("setup", "ALL")
        status = request.args.get("status", "ALL")
        limit = int(request.args.get("limit", 100))
        trades = backtest_engine.get_trades_list(run_id=run_id, setup_type=setup, status=status, limit=limit)
        return jsonify({"status": "success", "count": len(trades), "trades": trades})
    except Exception as e:
        logger.error(f"Backtest trades error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/backtest/recompute", methods=["POST"])
@admin_required
def api_backtest_recompute():
    """Trigger re-computation of benchmark sample."""
    try:
        data = request.get_json(silent=True) or {}
        years = int(data.get("years", 2))
        max_tickers = int(data.get("max_tickers", 35))
        res = backtest_engine.compute_universe_benchmark(years=years, max_tickers=max_tickers)
        return jsonify({"status": "success", "data": res, "message": "Benchmark berhasil dihitung ulang"})
    except Exception as e:
        logger.error(f"Recompute error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
