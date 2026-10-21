"""
Liquidity Pressure Model (LPM) and its companion lenses (Intensity, Vol Rotation, Phase).

Pure functions only: no network, database, or file access. Input is plain lists/dicts
of IDX Edge PRO broker-summary rows (one list per trading day); output is plain
dicts ready for JSON. Formula reference: ProjectOverview/FEATURE_LPM.md section 4.
"""
import math
import logging

logger = logging.getLogger(__name__)

LPM_PARAMS = {
    # Smart-money weight: ramp from R0 to R1 times the day's average trade value
    "R0": 1.5,
    "R1": 4.0,
    # Storage / fetch horizon (used by the client and routes, not by the math here)
    "history_days": 80,
    "max_sync_fetch_days": 5,
    # Slopes and adaptive threshold: theta_n = max(floor, k * sigma / sqrt(n))
    "slope_fast": 5,
    "slope_slow": 20,
    "theta_k": 1.0,
    "theta_lookback": 60,
    "theta_floor": 0.5,
    # Divergence
    "div_window": 20,
    "div_flat_max_pct": 2.0,
    "div_rally_min_pct": 5.0,
    "hh_recent_days": 5,
    "marker_debounce_days": 5,
    # Intensity (z-score of top-5 trade share vs previous days)
    "intensity_lookback": 20,
    "intensity_min_days": 10,
    "intensity_std_floor": 0.01,
    "intensity_spike_z": 1.5,
    "intensity_extreme_z": 2.5,
    # Vol Rotation (percentile of efficiency vs previous days)
    "vr_lookback": 60,
    "vr_min_days": 10,
    "vr_green_pct": 60.0,
    "vr_yellow_pct": 30.0,
    # Phase reading
    "spike_repeat_window": 10,
    "spike_repeat_min": 2,
    "vr_dominant_window": 5,
    "phase_prep_max_pct": 5.0,
    "phase_hot_min_pct": 5.0,
    "phase_markup_min_pct": 2.0,
    # Thin days: below this many trades (both sides), pressure is scaled down
    "low_liquidity_frq": 50,
    "top_brokers_window": 20,
    "top_brokers_limit": 5,
}

SPIKE_LEVELS = ("SPIKE", "SPIKE_EKSTREM")
VR_SEVERITY = {"HIJAU": 0, "KUNING": 1, "MERAH": 2}

PHASES = {
    "DATA_KURANG": ("Data belum cukup", "Butuh minimal 20 hari bursa untuk membaca tren LPM."),
    "DISTRIBUSI": ("5. Distribusi", "Divergensi negatif. Keramaian dimanfaatkan untuk keluar. Saat paling berbahaya ikut euforia."),
    "MARKDOWN": ("6. Markdown", "LPM turun dan harga tidak menguat. Smart money sedang keluar, belum ada tanda akumulasi."),
    "PERSIAPAN": ("2. Persiapan", "Fase senyap beralih ke fase gerak. Timing terkuat dalam kerangka ini."),
    "SENYAP": ("1. Senyap", "Akumulasi senyap. Sabar, pantau tanda persiapan."),
    "PANAS": ("4. Panas", "Efisiensi menurun di harga tinggi. Rawan jangka pendek meski akumulasi belum habis."),
    "MARKUP": ("3. Markup", "Kenaikan sehat selama perpindahan masih efisien. Pantau pergeseran warna."),
    "NETRAL": ("Netral", "Belum ada pola fase yang jelas."),
}

SECONDARY_NOTES = {
    "PELEPASAN_BERTAHAP": "Pelepasan Bertahap: LPM turun disertai spike. Jangan baca spike sebagai sinyal beli.",
    "BELUM_BERMAKNA": "Belum Bermakna: spike tanpa arah LPM hanya tanda aktivitas.",
}

DISCLAIMER = "Pembacaan perilaku dan probabilitas, bukan rekomendasi beli/jual. Berbasis data broker summary IDX."


# =========================================================================
# 1. DAILY METRICS (one trading day)
# =========================================================================

def smart_weight(r, R0, R1):
    """Linear ramp: 0 at or below R0, 1 at or above R1."""
    return min(1.0, max(0.0, (r - R0) / (R1 - R0)))


def compute_daily_metrics(brokers, params=LPM_PARAMS):
    """
    Compute the per-day context, pressure and lens inputs from one day's broker rows.
    Returns None for a day without trades (empty list, zero turnover or zero frequency).
    """
    if not brokers:
        return None

    total_bval = sum(b.get("bval") or 0 for b in brokers)
    total_sval = sum(b.get("sval") or 0 for b in brokers)
    frequency = sum((b.get("bfrq") or 0) + (b.get("sfrq") or 0) for b in brokers)
    turnover = (total_bval + total_sval) / 2
    if turnover <= 0 or frequency <= 0:
        return None

    avg_trade_value = (total_bval + total_sval) / frequency
    R0, R1 = params["R0"], params["R1"]

    smart_buy = 0.0
    smart_sell = 0.0
    broker_smart_net = {}
    for b in brokers:
        bval, sval = b.get("bval") or 0, b.get("sval") or 0
        bfrq, sfrq = b.get("bfrq") or 0, b.get("sfrq") or 0
        # A side with zero frequency carries no usable trade size, so it gets weight 0
        w_buy = smart_weight((bval / bfrq) / avg_trade_value, R0, R1) if bfrq > 0 else 0.0
        w_sell = smart_weight((sval / sfrq) / avg_trade_value, R0, R1) if sfrq > 0 else 0.0
        smart_buy += w_buy * bval
        smart_sell += w_sell * sval
        if w_buy > 0 or w_sell > 0:
            code = b.get("broker_code") or "?"
            broker_smart_net[code] = broker_smart_net.get(code, 0.0) + w_buy * bval - w_sell * sval

    pressure = (smart_buy - smart_sell) / turnover
    low_liquidity = frequency < params["low_liquidity_frq"]
    if low_liquidity:
        pressure *= frequency / params["low_liquidity_frq"]

    def net_value(b):
        nval = b.get("nval")
        return nval if nval is not None else (b.get("bval") or 0) - (b.get("sval") or 0)

    top5 = sorted(brokers, key=lambda b: abs(net_value(b)), reverse=True)[:5]
    top5_frq = sum((b.get("bfrq") or 0) + (b.get("sfrq") or 0) for b in top5)

    return {
        "turnover": turnover,
        "frequency": frequency,
        "avg_trade_value": avg_trade_value,
        "smart_buy": smart_buy,
        "smart_sell": smart_sell,
        "pressure": pressure,
        "low_liquidity": low_liquidity,
        "vr_efficiency": sum(abs(net_value(b)) for b in brokers) / (2 * turnover),
        "top5_share": top5_frq / frequency,
        "broker_smart_net": broker_smart_net,
    }


# =========================================================================
# 2. LPM LINE, SLOPES & TREND
# =========================================================================

def compute_lpm(pressures):
    """Cumulative line from a virtual 0 before the first day; gap days (None) stay flat."""
    line, level = [], 0.0
    for p in pressures:
        if p is not None:
            level += 100.0 * p
        line.append(level)
    return line


def _window_values(values, end_idx, n):
    return [v for v in values[max(0, end_idx - n + 1):end_idx + 1] if v is not None]


def rolling_slope(pressures, n):
    """
    Slope in LPM points per day = mean of 100 * pressure over the last n days.
    Gap days are left out of the mean; None when fewer than n days exist or more than
    half the window is missing.
    """
    out = []
    for i in range(len(pressures)):
        vals = _window_values(pressures, i, n)
        if i < n - 1 or len(vals) * 2 < n:
            out.append(None)
        else:
            out.append(100.0 * sum(vals) / len(vals))
    return out


def adaptive_theta(pressures, n, params=LPM_PARAMS):
    """
    Threshold for an n-day slope: k standard errors of the daily pressure (in points)
    over the lookback, never below the floor.
    """
    out = []
    for i in range(len(pressures)):
        vals = [100.0 * v for v in _window_values(pressures, i, params["theta_lookback"])]
        sigma = _stdev(vals) if len(vals) >= 2 else 0.0
        out.append(max(params["theta_floor"], params["theta_k"] * sigma / math.sqrt(n)))
    return out


def classify_trend(slope_fast, slope_slow, theta_fast):
    if slope_fast is None or slope_slow is None:
        return "DATA_KURANG"
    if slope_fast > theta_fast:
        return "RISING" if slope_slow > 0 else "TURNING_UP"
    if slope_fast < -theta_fast:
        return "FALLING" if slope_slow < 0 else "TURNING_DOWN"
    return "FLAT"


# =========================================================================
# 3. DIVERGENCE
# =========================================================================

def detect_divergence(closes, idx, slope_slow, theta_slow, params=LPM_PARAMS):
    """
    Price vs LPM divergence at day idx. Returns (status, price_chg_pct, new_high_recent);
    status is None when there is not enough history.
    """
    W, k = params["div_window"], params["hh_recent_days"]
    if idx < W or slope_slow is None:
        return None, None, None
    window = closes[idx - W:idx + 1]
    if any(c is None or c <= 0 for c in window):
        return None, None, None

    price_chg = (closes[idx] / closes[idx - W] - 1) * 100.0
    # A window high set in the last k days counts, so the flag does not blink off the day after a record
    new_high_recent = max(closes[idx - k + 1:idx + 1]) >= max(closes[idx - W:idx - k + 1])

    if price_chg <= params["div_flat_max_pct"] and slope_slow > theta_slow:
        status = "POSITIVE"
    elif (price_chg >= params["div_rally_min_pct"] or new_high_recent) and slope_slow < -theta_slow:
        status = "NEGATIVE"
    else:
        status = "NONE"
    return status, price_chg, new_high_recent


def divergence_markers(statuses, dates, params=LPM_PARAMS):
    """Dates where the status turns POSITIVE/NEGATIVE, skipping repeats of the same type within the debounce window."""
    markers, last_idx = [], {}
    for i, status in enumerate(statuses):
        if status not in ("POSITIVE", "NEGATIVE"):
            continue
        if i > 0 and statuses[i - 1] == status:
            continue
        if status in last_idx and i - last_idx[status] < params["marker_debounce_days"]:
            continue
        markers.append({"date": dates[i], "type": status})
        last_idx[status] = i
    return markers


# =========================================================================
# 4. INTENSITY & VOL ROTATION LENSES
# =========================================================================

def compute_intensity(top5_shares, params=LPM_PARAMS):
    """
    Z-score of today's top-5 trade share against the previous lookback days.
    A z-score is used instead of a plain ratio because the ratio is capped at 1/mean,
    which made the spike thresholds unreachable for stocks with high baseline concentration.
    Returns (z_values, levels) with None where the baseline is too short.
    """
    z_values, levels = [], []
    for i, share in enumerate(top5_shares):
        ref = _previous_values(top5_shares, i, params["intensity_lookback"])
        if share is None or len(ref) < params["intensity_min_days"]:
            z_values.append(None)
            levels.append(None)
            continue
        std = max(_stdev(ref), params["intensity_std_floor"])
        z = (share - sum(ref) / len(ref)) / std
        z_values.append(z)
        if z >= params["intensity_extreme_z"]:
            levels.append("SPIKE_EKSTREM")
        elif z >= params["intensity_spike_z"]:
            levels.append("SPIKE")
        else:
            levels.append("NORMAL")
    return z_values, levels


def compute_vol_rotation(efficiencies, params=LPM_PARAMS):
    """Mid-rank percentile of today's efficiency against the previous lookback days. Returns (percentiles, colors)."""
    percentiles, colors = [], []
    for i, eff in enumerate(efficiencies):
        ref = _previous_values(efficiencies, i, params["vr_lookback"])
        if eff is None or len(ref) < params["vr_min_days"]:
            percentiles.append(None)
            colors.append(None)
            continue
        below = sum(1 for v in ref if v < eff)
        equal = sum(1 for v in ref if v == eff)
        pct = (below + 0.5 * equal) / len(ref) * 100.0
        percentiles.append(pct)
        if pct >= params["vr_green_pct"]:
            colors.append("HIJAU")
        elif pct >= params["vr_yellow_pct"]:
            colors.append("KUNING")
        else:
            colors.append("MERAH")
    return percentiles, colors


def dominant_vr_color(colors):
    """Most frequent color; a tie goes to the more severe color."""
    counts = {}
    for c in colors:
        if c is not None:
            counts[c] = counts.get(c, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda c: (counts[c], VR_SEVERITY[c]))


# =========================================================================
# 5. PHASE READING
# =========================================================================

def classify_phase(trend, divergence, price_chg, spike_count, vr_color, intensity_level, params=LPM_PARAMS):
    """
    Evaluate phases in order and return the first match, plus an optional secondary note.
    price_chg is the 20-day price change in percent (None when unknown).
    """
    def phase(pid, secondary=None):
        label, reading = PHASES[pid]
        return {"id": pid, "label": label, "reading": reading, "secondary": secondary}

    spike_today = intensity_level in SPIKE_LEVELS
    secondary = None
    if trend == "FALLING" and spike_today:
        secondary = SECONDARY_NOTES["PELEPASAN_BERTAHAP"]
    elif spike_today and trend in ("FLAT", "DATA_KURANG"):
        secondary = SECONDARY_NOTES["BELUM_BERMAKNA"]

    if trend == "DATA_KURANG":
        return phase("DATA_KURANG", secondary)

    chg = price_chg if price_chg is not None else 0.0
    known = price_chg is not None
    repeated_spikes = spike_count >= params["spike_repeat_min"]

    if divergence == "NEGATIVE" or (trend == "FALLING" and known and chg >= params["phase_hot_min_pct"]):
        return phase("DISTRIBUSI", secondary)
    if trend == "FALLING":
        return phase("MARKDOWN", secondary)
    if (trend == "RISING" and repeated_spikes and vr_color == "HIJAU"
            and known and chg <= params["phase_prep_max_pct"]):
        return phase("PERSIAPAN", secondary)
    if divergence == "POSITIVE":
        return phase("SENYAP", secondary)
    if known and chg >= params["phase_hot_min_pct"] and (
            (trend in ("RISING", "FLAT") and vr_color in ("KUNING", "MERAH")) or trend == "TURNING_DOWN"):
        return phase("PANAS", secondary)
    if trend == "RISING" and known and chg > params["phase_markup_min_pct"]:
        return phase("MARKUP", secondary)
    return phase("NETRAL", secondary)


# =========================================================================
# 6. BROKERS BEHIND THE LINE & FULL PAYLOAD
# =========================================================================

def top_smart_brokers(daily_metrics, params=LPM_PARAMS):
    """Brokers with the largest absolute weighted net value over the recent window (sign kept)."""
    window = [m for m in daily_metrics[-params["top_brokers_window"]:] if m is not None]
    totals, active = {}, {}
    for m in window:
        for code, value in m["broker_smart_net"].items():
            totals[code] = totals.get(code, 0.0) + value
            active[code] = active.get(code, 0) + 1
    ranked = sorted(totals, key=lambda c: abs(totals[c]), reverse=True)[:params["top_brokers_limit"]]
    return [{"broker_code": c, "net_smart_value": round(totals[c]), "days_active": active[c]} for c in ranked]


def build_lpm(days, params=LPM_PARAMS):
    """
    Full LPM payload from trading days sorted oldest to newest.
    Each day: {"date", "close", optional "open"/"high"/"low", "brokers": list or None}.
    A day whose brokers are None (missing) or carry no trades is a gap.
    """
    if not days:
        return None

    dates = [d["date"] for d in days]
    closes = [d.get("close") for d in days]
    metrics = [compute_daily_metrics(d.get("brokers"), params) for d in days]

    pressures = [m["pressure"] if m else None for m in metrics]
    lpm_line = compute_lpm(pressures)
    n_fast, n_slow = params["slope_fast"], params["slope_slow"]
    slope_fast = rolling_slope(pressures, n_fast)
    slope_slow = rolling_slope(pressures, n_slow)
    theta_fast = adaptive_theta(pressures, n_fast, params)
    theta_slow = adaptive_theta(pressures, n_slow, params)

    intensity, intensity_levels = compute_intensity([m["top5_share"] if m else None for m in metrics], params)
    vr_pct, vr_colors = compute_vol_rotation([m["vr_efficiency"] if m else None for m in metrics], params)

    div_statuses = []
    for i in range(len(days)):
        status, _, _ = detect_divergence(closes, i, slope_slow[i], theta_slow[i], params)
        div_statuses.append(status)

    last = len(days) - 1
    trend = classify_trend(slope_fast[last], slope_slow[last], theta_fast[last])
    div_status, price_chg, new_high = detect_divergence(closes, last, slope_slow[last], theta_slow[last], params)
    spike_window = intensity_levels[-params["spike_repeat_window"]:]
    spike_count = sum(1 for lvl in spike_window if lvl in SPIKE_LEVELS)
    vr_color = dominant_vr_color(vr_colors[-params["vr_dominant_window"]:])
    phase = classify_phase(trend, div_status, price_chg, spike_count, vr_color, intensity_levels[last], params)

    series = []
    for i, d in enumerate(days):
        m = metrics[i]
        series.append({
            "date": d["date"],
            "open": d.get("open"),
            "high": d.get("high"),
            "low": d.get("low"),
            "close": d.get("close"),
            "pressure": _round(pressures[i], 5),
            "lpm": round(lpm_line[i], 2),
            "intensity": _round(intensity[i], 2),
            "intensity_level": intensity_levels[i],
            "vr_efficiency": _round(m["vr_efficiency"], 4) if m else None,
            "vr_percentile": _round(vr_pct[i], 1),
            "vr_color": vr_colors[i],
            "low_liquidity": bool(m and m["low_liquidity"]),
            "gap": m is None,
        })

    gap_days = sum(1 for m in metrics if m is None)
    return {
        "as_of": dates[last],
        "coverage": {"available_days": len(days) - gap_days, "gap_days": gap_days},
        "series": series,
        "trend": {
            "status": trend,
            "slope_5": _round(slope_fast[last], 2),
            "slope_20": _round(slope_slow[last], 2),
            "theta_5": round(theta_fast[last], 2),
            "theta_20": round(theta_slow[last], 2),
        },
        "divergence": {
            "status": div_status,
            "price_chg_20": _round(price_chg, 2),
            "new_high_recent": new_high,
            "markers": divergence_markers(div_statuses, dates, params),
        },
        "phase": phase,
        "top_smart_brokers": top_smart_brokers(metrics, params),
        "params": {
            "R0": params["R0"],
            "R1": params["R1"],
            "theta_k": params["theta_k"],
            "theta_floor": params["theta_floor"],
            "window": params["div_window"],
        },
        "disclaimer": DISCLAIMER,
    }


# =========================================================================
# HELPERS
# =========================================================================

def _previous_values(values, idx, lookback):
    return [v for v in values[max(0, idx - lookback):idx] if v is not None]


def _stdev(values):
    """Population standard deviation (0.0 for fewer than two values)."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _round(value, digits):
    return None if value is None else round(value, digits)
