import json

CACHE_PATH = 'data/cache/pre_breakout_result.json'

with open(CACHE_PATH, 'r', encoding='utf-8') as f:
    payload = json.load(f)

results = payload.get('results', [])
updated_results = []

for r in results:
    curr_price = r['price']
    m20 = r['ema20']
    m50 = r['ema50']
    curr_rsi = r['rsi']
    curr_macd = r['macd']
    curr_signal = r['signal']
    rvol = r['rvol']
    high_50d = r['high_50d']
    dist_res_pct = r['dist_res_pct']
    recent_vol = r['volume']

    # K1: Close > EMA 20
    k1 = bool(curr_price > m20)

    # K2: EMA 20 > EMA 50
    k2 = bool(m20 > m50)

    # K3: RSI 50-70
    k3 = bool(50.0 <= curr_rsi <= 70.0)

    # K4: MACD > Signal
    k4 = bool(curr_macd > curr_signal)

    # K5: Dual-Volume Logic
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

    # K6 & K7 from existing pass status
    k6 = r['criteria']['k6']['pass']
    hl_detail = r['criteria']['k6']['val']

    k7 = bool(0.0 <= dist_res_pct < 5.0)

    total_score = sum([k1, k2, k3, k4, k5, k6, k7])
    if total_score < 5:
        continue

    is_ready = (total_score == 7)
    status = "READY" if is_ready else "FORMING"
    status_label = "READY TO BREAKOUT" if is_ready else "FORMING BASE"

    r['total_score'] = total_score
    r['status'] = status
    r['status_label'] = status_label
    r['is_ready'] = is_ready
    r['vol_type'] = vol_type
    r['vol_label'] = vol_label

    r['criteria']['k1'] = {'pass': k1, 'title': 'Close > EMA 20', 'val': f'Price {curr_price:.0f} vs EMA20 {m20:.0f}'}
    r['criteria']['k2'] = {'pass': k2, 'title': 'EMA 20 > EMA 50', 'val': f'EMA20 {m20:.0f} vs EMA50 {m50:.0f}'}
    r['criteria']['k3'] = {'pass': k3, 'title': 'RSI 50-70 (Momentum)', 'val': f'RSI {curr_rsi:.1f}'}
    r['criteria']['k4'] = {'pass': k4, 'title': 'MACD Bullish (Line > Signal)', 'val': f'MACD {curr_macd:.2f} > Sig {curr_signal:.2f}'}
    r['criteria']['k5'] = {'pass': k5, 'title': 'RVOL (Surge >=1.2x atau Dry-Up <=0.75x)', 'val': k5_val}
    r['criteria']['k6'] = {'pass': k6, 'title': 'Higher Low Base Structure', 'val': hl_detail}
    r['criteria']['k7'] = {'pass': k7, 'title': 'Jarak ke Resistance 50D < 5%', 'val': f'-{dist_res_pct:.1f}% (High: {high_50d:.0f})'}

    updated_results.append(r)

# Sort: total_score DESC, dist_res_pct ASC, rvol DESC
updated_results.sort(key=lambda x: (x['total_score'], -x['dist_res_pct'], x['rvol']), reverse=True)

ready_count = sum(1 for r in updated_results if r['status'] == 'READY')
forming_count = sum(1 for r in updated_results if r['status'] == 'FORMING')

payload['stats']['total_setups'] = len(updated_results)
payload['stats']['ready_count'] = ready_count
payload['stats']['forming_count'] = forming_count
payload['results'] = updated_results

with open(CACHE_PATH, 'w', encoding='utf-8') as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)

print(f"Updated Pre-Breakout cache saved successfully!")
print(f"Total Setups: {len(updated_results)}")
print(f"Ready: {ready_count} stocks")
print(f"Forming: {forming_count} stocks")
print("Top 5 Ready stocks:")
for s in updated_results[:5]:
    print(f" - {s['ticker']} ({s['name']}): Score {s['total_score']}/7, Dist -{s['dist_res_pct']}%, RVOL {s['rvol']}x ({s['vol_label']})")
