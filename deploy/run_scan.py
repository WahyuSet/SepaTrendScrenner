#!/usr/bin/env python3
# ==============================================================================
# TIREXXZ SCRENNER - STANDALONE CRON SCAN RUNNER
# Script ini dirancang untuk dijalankan otomatis oleh Linux Cron Job
# Jadwal: Senin - Jumat Jam 18:00 WIB
# ==============================================================================

import os
import sys
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Pastikan path root project ada di sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from screener.calculator import SEPACalculator
from screener.rsi_divergence import RSIDivergenceCalculator
from screener.pre_breakout import PreBreakoutCalculator

CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
TICKERS_FILE = os.path.join(BASE_DIR, "data", "idx_tickers.csv")
LOG_FILE = os.path.join(BASE_DIR, "data", "cron_scan.log")

def log_msg(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Failed to write to log file: {e}")

def save_json(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    tmp_path = file_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # Atomic replace to prevent file corruption during read
    os.replace(tmp_path, file_path)

def main():
    start_time = time.time()
    log_msg("=== MEMULAI CRON AUTO-SCAN HARIAN (TIREXXZ SCRENNER) ===")

    calc = SEPACalculator(tickers_csv_path=TICKERS_FILE)

    # 1. Fetch Benchmark IHSG
    log_msg("1/5 Mengunduh data benchmark IHSG (^JKSE)...")
    calc.rs_calc.fetch_benchmark()

    # 2. Ambil daftar ticker
    tickers = calc.fetcher.tickers_df['ticker'].tolist() if calc.fetcher.tickers_df is not None else []
    log_msg(f"2/5 Mengunduh data historis untuk {len(tickers)} universe saham IDX...")

    all_data = {}
    max_workers = 10

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(calc.fetcher.fetch_single_ticker, t, "2y"): t
            for t in tickers
        }
        for future in as_completed(future_to_ticker):
            try:
                t, df, err = future.result()
                if df is not None:
                    clean = df.dropna(subset=["Close"])
                    if len(clean) >= 50:
                        all_data[t] = clean
            except Exception as ex:
                pass

    log_msg(f"Data valid terkumpul: {len(all_data)}/{len(tickers)} emiten.")

    time_str = datetime.now().strftime("%d %b %Y, %H:%M WIB")
    iso_time = datetime.now().isoformat()

    # 3. Evaluasi SEPA Criteria
    log_msg("3/5 Mengevaluasi 8 Kriteria SEPA Trend...")
    sepa_results = []
    for ticker, df in all_data.items():
        eval_res = calc.evaluate_stock(ticker, df)
        if eval_res is not None:
            sepa_results.append(eval_res)

    sepa_results.sort(key=lambda x: (x['total_score'], x['rs_score'], x['dist_low_pct']), reverse=True)
    confirmed_count = sum(1 for r in sepa_results if r['status'] == 'CONFIRMED')
    watchlist_count = sum(1 for r in sepa_results if r['status'] == 'WATCHLIST')

    sepa_payload = {
        "timestamp": time_str,
        "iso_timestamp": iso_time,
        "stats": {
            "total_universe": len(tickers),
            "total_scanned": len(sepa_results),
            "confirmed_count": confirmed_count,
            "watchlist_count": watchlist_count,
            "unqualified_count": len(sepa_results) - (confirmed_count + watchlist_count)
        },
        "results": sepa_results
    }
    save_json(os.path.join(CACHE_DIR, "scan_result.json"), sepa_payload)
    log_msg(f"SEPA Selesai: {confirmed_count} Confirmed, {watchlist_count} Watchlist.")

    # 4. Evaluasi RSI Divergence
    log_msg("4/5 Mengevaluasi RSI Divergences...")
    rsi_calc = RSIDivergenceCalculator(tickers_csv_path=TICKERS_FILE)
    rsi_results = []
    for ticker, df in all_data.items():
        rsi_res = rsi_calc.detect_divergence(ticker, df)
        if rsi_res is not None:
            rsi_results.append(rsi_res)

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
    save_json(os.path.join(CACHE_DIR, "rsi_div_result.json"), rsi_payload)
    log_msg(f"RSI Selesai: {len(rsi_results)} divergensi ditemukan ({reg_bull_count} Regular, {hid_bull_count} Hidden).")

    # 5. Evaluasi Pre-Breakout Setups
    log_msg("5/5 Mengevaluasi Pre-Breakout Setups...")
    pb_calc = PreBreakoutCalculator(tickers_csv_path=TICKERS_FILE, min_turnover_20d=500_000_000)
    pb_results = []
    for ticker, df in all_data.items():
        pb_res = pb_calc.evaluate_stock(ticker, df)
        if pb_res is not None:
            pb_results.append(pb_res)

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
    save_json(os.path.join(CACHE_DIR, "pre_breakout_result.json"), pb_payload)
    log_msg(f"Pre-Breakout Selesai: {ready_count} READY to Breakout, {forming_count} FORMING.")

    duration = round(time.time() - start_time, 2)
    log_msg(f"=== CRON SCAN SELESAI SUKSES DALAM {duration} DETIK ===\n")

if __name__ == "__main__":
    main()
