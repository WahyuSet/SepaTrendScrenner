import os
import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from screener.calculator import SEPACalculator
from screener.rsi_divergence import RSIDivergenceCalculator
from screener.pre_breakout import PreBreakoutCalculator
from screener.idx_api_client import IDXApiClient
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

idx_client = IDXApiClient()

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "scan_result.json")
RSI_CACHE_FILE = os.path.join(CACHE_DIR, "rsi_div_result.json")
PREBREAKOUT_CACHE_FILE = os.path.join(CACHE_DIR, "pre_breakout_result.json")
TICKERS_FILE = os.path.join(os.path.dirname(__file__), "data", "idx_tickers.csv")

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
        max_workers = 10
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

        # Sort: total_score DESC, dist_res_pct ASC (closest to breakout first), rvol DESC
        pb_results.sort(key=lambda x: (x['total_score'], -x['dist_res_pct'], x['rvol']), reverse=True)

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
    """Render main application page."""
    return render_template("index.html")

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
        "stats": stats
    })

# =========================================================================
# IDX EDGE PRO API ENDPOINTS (ON-DEMAND & CACHED)
# =========================================================================

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
    flow = request.args.get("flow", "all")
    force = request.args.get("force", "false").lower() == "true"
    try:
        data = idx_client.get_broker_summary(ticker, flow=flow, force_refresh=force)
        quota = idx_client.get_quota_status()
        if not data:
            return jsonify({"status": "error", "message": f"Broker summary not found for {ticker}"}), 404
        return jsonify({"status": "success", "data": data, "quota": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/idx/broker-accumulation/<ticker>", methods=["GET"])
@admin_required
def get_idx_broker_accum(ticker):
    """Get historical broker accumulation time series for a ticker."""
    top = int(request.args.get("top", 3))
    force = request.args.get("force", "false").lower() == "true"
    try:
        data = idx_client.get_broker_accumulation(ticker, top=top, force_refresh=force)
        quota = idx_client.get_quota_status()
        if not data:
            return jsonify({"status": "error", "message": f"Accumulation data not found for {ticker}"}), 404
        return jsonify({"status": "success", "data": data, "quota": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/idx/financials/<ticker>", methods=["GET"])
@admin_required
def get_idx_financials(ticker):
    """Get financial statements and YoY EPS growth for a ticker."""
    force = request.args.get("force", "false").lower() == "true"
    try:
        data = idx_client.get_financial_statements(ticker, force_refresh=force)
        quota = idx_client.get_quota_status()
        if not data:
            return jsonify({"status": "error", "message": f"Financials not found for {ticker}"}), 404
        return jsonify({"status": "success", "data": data, "quota": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/idx/analysis/<ticker>", methods=["GET"])
@admin_required
def get_idx_analysis(ticker):
    """Get comprehensive automated analysis and trading plan for a ticker."""
    force = request.args.get("force", "false").lower() == "true"
    try:
        data = idx_client.get_comprehensive_analysis(ticker, force_refresh=force)
        quota = idx_client.get_quota_status()
        if not data:
            return jsonify({"status": "error", "message": f"Analysis not found for {ticker}"}), 404
        return jsonify({"status": "success", "data": data, "quota": quota})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
