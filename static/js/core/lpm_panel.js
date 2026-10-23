/**
 * ============================================================================
 * LPM (LIQUIDITY PRESSURE MODEL) & SMART MONEY VIEW (templates/views/view_lpm.html)
 * Data: GET /api/idx/lpm (stored tickers), GET /api/idx/lpm/<ticker>,
 *       backfill: POST .../backfill + polling .../status
 * Chart: lightweight-charts 5.x with three native panes (price, LPM, daily lens)
 * Spec: ProjectOverview/FEATURE_LPM.md sections 6–7
 * ============================================================================
 */

const LPM_POLL_MS = 2000;
const LPM_REFRESH_EVERY_POLLS = 5; // redraw the line every ~10s while a backfill fills it
const LPM_QUOTA_RESERVE = 200;
const LPM_MIN_DAYS = 20;

const LPM_LAST_TICKER_KEY = "lpm:lastTicker";

const lpmCache = {}; // ticker -> { data, quota }
let lpmTickerOptionsReady = false;
const lpmState = {
  ticker: null,
  data: null,
  quota: null,
  lens: "intensity",
  chart: null,
  series: null,
  lensPriceLine: null,
  resizeObserver: null,
  pollTimer: null,
  pollCount: 0,
  requestSeq: 0,
};

const LPM_TREND = {
  RISING: { text: "Naik", tone: "pos", sub: "Kemiringan 5 hari naik, dikonfirmasi 20 hari" },
  FALLING: { text: "Turun", tone: "neg", sub: "Kemiringan 5 hari turun, dikonfirmasi 20 hari" },
  TURNING_UP: { text: "Mulai naik", tone: "pos", sub: "5 hari naik, 20 hari belum ikut naik" },
  TURNING_DOWN: { text: "Mulai turun", tone: "warn", sub: "5 hari turun, 20 hari belum ikut turun" },
  FLAT: { text: "Datar", tone: "neutral", sub: "Kemiringan 5 hari di dalam ambang noise" },
  DATA_KURANG: { text: "Data belum cukup", tone: "neutral", sub: "" },
};

const LPM_DIVERGENCE = {
  POSITIVE: { text: "Akumulasi senyap", tone: "pos" },
  NEGATIVE: { text: "Distribusi terselubung", tone: "neg" },
  NONE: { text: "Tidak ada", tone: "neutral" },
};

const LPM_PHASE_TONE = {
  SENYAP: "pos", PERSIAPAN: "pos", MARKUP: "pos",
  PANAS: "warn", DISTRIBUSI: "neg", MARKDOWN: "neg",
  NETRAL: "neutral", DATA_KURANG: "neutral",
};

const LPM_LENS_NOTE = {
  intensity: "Intensity: z-score porsi transaksi 5 broker paling aktif dibanding 20 hari sebelumnya. Garis putus-putus = ambang spike (1,5); batang paling pekat = spike ekstrem (≥ 2,5). Lensa ini menunjukkan kapan, bukan arah.",
  vr: "Vol Rotation: porsi turnover yang benar-benar berpindah tangan secara net, dibanding 60 hari sebelumnya. Hijau = efisien, kuning = efisiensi mulai turun, merah = ramai tapi perpindahan nyata rendah.",
};

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

function lpmEl(id) {
  return document.getElementById(id);
}

function lpmToken(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function lpmWithAlpha(color, alpha) {
  if (!color) return color;
  const hexMatch = /^#?([0-9a-f]{6})$/i.exec(color.trim());
  if (hexMatch) {
    const n = parseInt(hexMatch[1], 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
  }
  const rgbMatch = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/i.exec(color.trim());
  if (rgbMatch) {
    return `rgba(${rgbMatch[1]}, ${rgbMatch[2]}, ${rgbMatch[3]}, ${alpha})`;
  }
  return color;
}

function lpmFmt(value, digits = 1, signed = false) {
  if (value === null || value === undefined || isNaN(value)) return "--";
  const text = new Intl.NumberFormat("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
  return signed && value > 0 ? `+${text}` : text;
}

function lpmQuotaLow(quota) {
  return quota && quota.remaining - 1 < LPM_QUOTA_RESERVE;
}

function lpmSetTone(el, tone) {
  el.classList.remove("lpm-tone-pos", "lpm-tone-neg", "lpm-tone-warn", "lpm-tone-neutral");
  el.classList.add(`lpm-tone-${tone || "neutral"}`);
}

function lpmTimeKey(time) {
  if (!time) return null;
  if (typeof time === "string") return time;
  if (typeof time === "object" && time.year) {
    return `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`;
  }
  return null;
}

function lpmStorageGet() {
  try {
    return localStorage.getItem(LPM_LAST_TICKER_KEY);
  } catch (e) {
    return null;
  }
}

function lpmStorageSet(ticker) {
  try {
    localStorage.setItem(LPM_LAST_TICKER_KEY, ticker);
  } catch (e) {
    // Remembering the last stock is a convenience only
  }
}

// ----------------------------------------------------------------------------
// 0. Page: picker, stored-history list, navigation from other screens
// ----------------------------------------------------------------------------

function initLpmPage() {
  if (!lpmTickerOptionsReady) lpmTickerOptionsReady = fillLpmTickerOptions();
  loadLpmStoredList();
  if (!lpmState.ticker) {
    const last = lpmStorageGet();
    if (last) selectLpmTicker(last);
  }
}

/** Open the LPM page for a ticker from anywhere (e.g. the stock detail modal). */
function openLpmPage(ticker) {
  const clean = (ticker || "").trim().toUpperCase().replace(".JK", "");
  if (!clean) return;
  if (typeof closeStockDetailModal === "function") closeStockDetailModal();
  lpmStorageSet(clean);
  switchScreener("lpm");
  if (lpmState.ticker !== clean) selectLpmTicker(clean);
}

function fillLpmTickerOptions() {
  const map = window.idxMasterTickersMap || {};
  const tickers = Object.keys(map);
  if (!tickers.length) return false; // master list still loading; retried on next visit
  const frag = document.createDocumentFragment();
  tickers.sort().forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.label = map[t].name || "";
    frag.appendChild(opt);
  });
  lpmEl("lpm-ticker-options").replaceChildren(frag);
  return true;
}

function submitLpmTicker(event) {
  event.preventDefault();
  const input = lpmEl("lpm-ticker-input");
  const clean = input.value.trim().toUpperCase().replace(".JK", "");
  const error = lpmEl("lpm-picker-error");
  const map = window.idxMasterTickersMap || {};

  let message = "";
  if (!/^[A-Z]{4}$/.test(clean)) {
    message = "Kode saham terdiri dari 4 huruf, misalnya BBCA.";
  } else if (Object.keys(map).length && !map[clean]) {
    message = `Kode ${clean} tidak terdaftar di Bursa Efek Indonesia.`;
  }
  error.textContent = message;
  error.classList.toggle("hidden", !message);
  input.setAttribute("aria-invalid", message ? "true" : "false");
  if (!message) selectLpmTicker(clean);
}

function selectLpmTicker(ticker) {
  lpmEl("lpm-picker-error").classList.add("hidden");
  lpmEl("lpm-ticker-input").value = ticker;
  lpmEl("lpm-intro").classList.add("hidden");
  lpmEl("lpm-panel").classList.remove("hidden");
  lpmEl("lpm-panel-ticker").textContent = ticker;
  const meta = (window.idxMasterTickersMap || {})[ticker];
  lpmEl("lpm-panel-name").textContent = meta && meta.name ? meta.name : "";
  lpmStorageSet(ticker);
  markActiveStoredChip(ticker);
  loadLpmPanel(ticker);
}

function refreshLpmPage() {
  if (lpmState.ticker) loadLpmPanel(lpmState.ticker, true);
  loadLpmStoredList();
}

async function loadLpmStoredList() {
  const container = lpmEl("lpm-stored-list");
  try {
    const body = await fetch("/api/idx/lpm").then((r) => r.json());
    if (body.status !== "success") throw new Error(body.message || "respons tidak valid");
    const badge = document.getElementById("badge-lpm");
    if (badge) badge.textContent = String(body.data.length);
    if (!container) return;

    container.replaceChildren();
    if (!body.data.length) {
      const empty = document.createElement("span");
      empty.className = "lpm-stored-empty";
      empty.textContent = "Belum ada. Saham yang historinya sudah diambil akan muncul di sini.";
      container.appendChild(empty);
      return;
    }
    body.data.forEach((row) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "lpm-stored-chip";
      chip.dataset.ticker = row.ticker;
      chip.title = `Data terakhir ${row.last_date}`;
      const code = document.createElement("span");
      code.className = "lpm-stored-code";
      code.textContent = row.ticker;
      const days = document.createElement("span");
      days.className = "lpm-stored-days";
      days.textContent = `${row.days} hari`;
      chip.append(code, days);
      chip.addEventListener("click", () => selectLpmTicker(row.ticker));
      container.appendChild(chip);
    });
    markActiveStoredChip(lpmState.ticker);
  } catch (err) {
    console.error("LPM stored list error:", err);
    if (container) container.textContent = "Daftar histori tersimpan tidak bisa dimuat. Kode saham tetap bisa diketik di atas.";
  }
}

function markActiveStoredChip(ticker) {
  document.querySelectorAll(".lpm-stored-chip").forEach((chip) => {
    const active = chip.dataset.ticker === ticker;
    chip.classList.toggle("active", active);
    chip.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

// Sidebar badge = number of stocks with stored history (no quota used)
document.addEventListener("DOMContentLoaded", () => {
  fetch("/api/idx/lpm")
    .then((r) => r.json())
    .then((body) => {
      const badge = document.getElementById("badge-lpm");
      if (badge && body.status === "success") badge.textContent = String(body.data.length);
    })
    .catch(() => {});
});

// ----------------------------------------------------------------------------
// 1. Panel loading
// ----------------------------------------------------------------------------

async function loadLpmPanel(ticker, force = false, silent = false) {
  if (!ticker) return;
  if (lpmState.ticker !== ticker) {
    destroyLpmPanel();
    lpmState.ticker = ticker;
  }

  if (!force && lpmCache[ticker]) {
    renderLpm(lpmCache[ticker].data, lpmCache[ticker].quota);
    if (lpmCache[ticker].data.backfill && lpmCache[ticker].data.backfill.state === "running") startLpmPolling();
    return;
  }

  const seq = ++lpmState.requestSeq;
  if (!silent) showLpmView("loading");

  try {
    const resp = await fetch(`/api/idx/lpm/${ticker}`);
    const body = await resp.json().catch(() => ({}));
    if (seq !== lpmState.requestSeq || lpmState.ticker !== ticker) return;

    if (!resp.ok || body.status !== "success") {
      if (!silent) showLpmError(body.message || `Server membalas status ${resp.status}.`);
      return;
    }
    lpmCache[ticker] = { data: body.data, quota: body.quota };
    if (body.quota && typeof updateSidebarQuota === "function") updateSidebarQuota(body.quota);
    renderLpm(body.data, body.quota);
    if (body.data.backfill && body.data.backfill.state === "running" && !lpmState.pollTimer) startLpmPolling();
  } catch (err) {
    console.error("LPM fetch error:", err);
    if (seq === lpmState.requestSeq && !silent) {
      showLpmError("Server tidak bisa dihubungi. Periksa koneksi, lalu coba lagi.");
    }
  }
}

function destroyLpmPanel() {
  stopLpmPolling();
  if (lpmState.resizeObserver) {
    lpmState.resizeObserver.disconnect();
    lpmState.resizeObserver = null;
  }
  if (lpmState.chart) {
    lpmState.chart.remove();
  }
  lpmState.chart = null;
  lpmState.series = null;
  lpmState.lensPriceLine = null;
  lpmState.data = null;
  lpmState.ticker = null;
  lpmState.requestSeq++;
}

function setLpmLens(lens) {
  lpmState.lens = lens;
  document.querySelectorAll(".lpm-toggle-btn").forEach((btn) => {
    const active = btn.dataset.lens === lens;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
  lpmEl("lpm-lens-note").textContent = LPM_LENS_NOTE[lens];
  if (lpmState.data && lpmState.series) applyLensData(lpmState.data.series);
  renderLpmLegend(null);
}

// ----------------------------------------------------------------------------
// 2. View states
// ----------------------------------------------------------------------------

function showLpmView(view) {
  lpmEl("lpm-loading").classList.toggle("hidden", view !== "loading");
  lpmEl("lpm-state").classList.toggle("hidden", view !== "state");
  lpmEl("lpm-content").classList.toggle("hidden", view !== "content");
  lpmEl("lpm-coverage").classList.toggle("hidden", view === "loading" || view === "error");
}

function showLpmState(title, desc, actionLabel, onAction, disabled = false) {
  lpmEl("lpm-state-title").textContent = title;
  lpmEl("lpm-state-desc").textContent = desc;
  const btn = lpmEl("lpm-state-action");
  btn.classList.toggle("hidden", !actionLabel);
  btn.textContent = actionLabel || "";
  btn.disabled = disabled;
  btn.onclick = onAction || null;
}

function showLpmError(message) {
  const ticker = lpmState.ticker;
  showLpmState(
    "LPM belum bisa ditampilkan",
    message,
    "Coba lagi",
    () => loadLpmPanel(ticker, true)
  );
  showLpmView("error");
  lpmEl("lpm-state").classList.remove("hidden");
}

// ----------------------------------------------------------------------------
// 3. Render
// ----------------------------------------------------------------------------

function renderLpm(data, quota) {
  lpmState.data = data;
  lpmState.quota = quota;
  const job = data.backfill || { state: "idle" };
  const cov = data.coverage;

  if (!cov.has_history) {
    renderLpmEmpty(data, quota, job);
  } else {
    showLpmView("content");
    renderLpmSummary(data);
    renderLpmChart(data);
    renderLpmBrokers(data.top_smart_brokers || []);
  }
  renderLpmCoverage(data, quota, job);
}

function renderLpmEmpty(data, quota, job) {
  const cov = data.coverage;
  showLpmView("state");
  if (job.state === "running") {
    showLpmState(
      `Mengambil histori broker ${data.ticker}`,
      `Proses berjalan di latar belakang. Garis LPM mulai bisa dibaca setelah ${LPM_MIN_DAYS} hari bursa terisi; halaman ini memperbarui diri otomatis.`,
      null,
      null
    );
    return;
  }
  const estimate = quota ? Math.min(cov.missing_days, Math.max(0, quota.remaining - LPM_QUOTA_RESERVE)) : cov.missing_days;
  const low = lpmQuotaLow(quota);
  showLpmState(
    `Belum ada histori LPM untuk ${data.ticker}`,
    low
      ? `LPM butuh broker summary per hari bursa (${cov.missing_days} hari). Sisa kuota hari ini (${quota.remaining}) tinggal cadangan ${LPM_QUOTA_RESERVE} request untuk fitur lain, jadi histori baru bisa diambil besok.`
      : `LPM butuh broker summary per hari bursa. Mengambil ${cov.missing_days} hari memakai sekitar ${estimate} request dari kuota harian (sisa ${quota ? quota.remaining : "--"}). Proses berjalan di latar belakang dan berhenti sendiri sebelum menyentuh cadangan ${LPM_QUOTA_RESERVE} request.`,
    low ? "Kuota hari ini tidak cukup" : `Ambil histori ${cov.requested_days} hari`,
    low ? null : startLpmBackfill,
    low
  );
}

function renderLpmSummary(data) {
  const trend = data.trend;
  const t = LPM_TREND[trend.status] || LPM_TREND.FLAT;
  const trendEl = lpmEl("lpm-trend");
  trendEl.textContent = t.text;
  lpmSetTone(trendEl, t.tone);
  lpmEl("lpm-trend-sub").textContent = trend.status === "DATA_KURANG"
    ? `${data.coverage.available_days} dari minimal ${LPM_MIN_DAYS} hari tersimpan`
    : t.sub;

  const div = data.divergence;
  const divEl = lpmEl("lpm-divergence");
  const d = div.status ? LPM_DIVERGENCE[div.status] : null;
  divEl.textContent = d ? d.text : "--";
  lpmSetTone(divEl, d ? d.tone : "neutral");
  lpmEl("lpm-divergence-sub").textContent = div.price_chg_20 === null || div.price_chg_20 === undefined
    ? "Butuh 20 hari data"
    : `Harga 20 hari ${lpmFmt(div.price_chg_20, 1, true)}%${div.status ? "" : " · tren belum terbaca"}`;

  const phaseEl = lpmEl("lpm-phase");
  phaseEl.textContent = data.phase.label;
  lpmSetTone(phaseEl, LPM_PHASE_TONE[data.phase.id]);
  lpmEl("lpm-phase-sub").textContent = `Per ${data.as_of}`;

  // With fewer than 20 stored days the 20-day slope is not a structural reading yet
  const enough = trend.status !== "DATA_KURANG";
  lpmEl("lpm-slopes").textContent = `${lpmFmt(trend.slope_5, 1, true)} / ${enough ? lpmFmt(trend.slope_20, 1, true) : "--"}`;
  lpmEl("lpm-slopes-sub").textContent = enough
    ? `poin/hari · ambang ±${lpmFmt(trend.theta_5)} / ±${lpmFmt(trend.theta_20)}`
    : `poin/hari · 20H butuh ${LPM_MIN_DAYS} hari tersimpan`;

  lpmEl("lpm-reading").textContent = data.phase.reading;
  const secondary = lpmEl("lpm-secondary");
  secondary.textContent = data.phase.secondary || "";
  secondary.classList.toggle("hidden", !data.phase.secondary);
}

function renderLpmBrokers(brokers) {
  const tbody = lpmEl("lpm-brokers-body");
  tbody.replaceChildren();
  if (!brokers.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 3;
    td.className = "lpm-empty-cell";
    td.textContent = "Belum ada broker dengan ukuran transaksi khas pelaku besar di 20 hari terakhir.";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }
  brokers.forEach((b) => {
    const tr = document.createElement("tr");
    const code = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "broker-badge";
    badge.textContent = b.broker_code;
    code.appendChild(badge);

    const value = document.createElement("td");
    value.className = `text-right mono ${b.net_smart_value >= 0 ? "lpm-tone-pos" : "lpm-tone-neg"}`;
    value.textContent = `${b.net_smart_value >= 0 ? "Beli " : "Jual "}${formatRupiahShort(Math.abs(b.net_smart_value))}`;

    const days = document.createElement("td");
    days.className = "text-right mono";
    days.textContent = b.days_active;

    tr.append(code, value, days);
    tbody.appendChild(tr);
  });
}

function renderLpmCoverage(data, quota, job) {
  const cov = data.coverage;
  const btn = lpmEl("lpm-backfill-btn");
  const note = lpmEl("lpm-coverage-note");
  const low = lpmQuotaLow(quota);

  lpmEl("lpm-coverage-text").textContent =
    `${cov.available_days} dari ${cov.requested_days} hari bursa tersedia · sisa kuota ${quota ? quota.remaining : "--"}`;

  const running = job.state === "running";
  const showButton = cov.has_history && !cov.complete && !running;
  btn.classList.toggle("hidden", !showButton);
  if (showButton) {
    const estimate = quota ? Math.min(cov.missing_days, Math.max(0, quota.remaining - LPM_QUOTA_RESERVE)) : cov.missing_days;
    btn.textContent = job.state === "error" ? "Coba lengkapi lagi" : `Lengkapi histori (±${estimate} request)`;
    btn.disabled = low;
  }

  let message = "";
  if (job.state === "stopped_quota") {
    message = `Pengambilan histori berhenti di ${job.done} dari ${job.total} hari karena sisa kuota menyentuh cadangan ${LPM_QUOTA_RESERVE} request. Lanjutkan besok.`;
  } else if (job.state === "error") {
    message = `Pengambilan histori gagal: ${job.last_error || "penyebab tidak diketahui"}.`;
  } else if (showButton && low) {
    message = `Sisa kuota hari ini tinggal cadangan ${LPM_QUOTA_RESERVE} request untuk fitur lain. Histori bisa dilengkapi besok.`;
  } else if (cov.has_history && cov.missing_days > 0 && !running) {
    message = `${cov.missing_days} hari bursa belum diambil; hari itu tampil abu-abu di chart.`;
  }
  note.textContent = message;
  note.classList.toggle("hidden", !message);

  renderLpmProgress(job);
}

function renderLpmProgress(job) {
  const wrap = lpmEl("lpm-progress");
  const running = job && job.state === "running";
  wrap.classList.toggle("hidden", !running);
  if (!running) return;
  const pct = job.total ? Math.round((job.done / job.total) * 100) : 0;
  lpmEl("lpm-progress-bar").style.width = `${pct}%`;
  wrap.setAttribute("aria-valuenow", String(pct));
  lpmEl("lpm-coverage-text").textContent = `Mengambil histori: ${job.done} dari ${job.total} hari (${job.requested || 0} request)`;
}

// ----------------------------------------------------------------------------
// 4. Chart
// ----------------------------------------------------------------------------

function ensureLpmChart() {
  if (lpmState.chart) return true;
  const container = lpmEl("lpm-chart");
  const LC = window.LightweightCharts;
  if (!LC) {
    container.textContent = "Library chart gagal dimuat (CDN unpkg tidak terjangkau). Angka di kartu atas tetap berlaku.";
    container.classList.add("lpm-chart-failed");
    return false;
  }
  container.classList.remove("lpm-chart-failed");
  container.replaceChildren();

  const border = lpmToken("--border-subtle");
  const gridColor = lpmToken("--chart-grid") || border;
  const textColor = lpmToken("--chart-text") || lpmToken("--text-muted");
  const chart = LC.createChart(container, {
    autoSize: true,
    layout: {
      background: { type: "solid", color: lpmToken("--bg-secondary") },
      textColor: textColor,
      fontFamily: lpmToken("--font-sans"),
      fontSize: 11,
      panes: { separatorColor: border, enableResize: false },
    },
    grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
    rightPriceScale: { borderColor: border },
    // LPM shares the price pane on its own left axis (points), price stays on the right (Rupiah)
    leftPriceScale: { visible: true, borderColor: border },
    timeScale: { borderColor: border, rightOffset: 2 },
    localization: { locale: "id-ID" },
  });

  const up = lpmToken("--chart-up") || lpmToken("--status-confirmed-text");
  const down = lpmToken("--chart-down") || lpmToken("--status-fail-text");
  const candle = chart.addSeries(LC.CandlestickSeries, {
    upColor: up, downColor: down, wickUpColor: up, wickDownColor: down,
    borderVisible: false, priceLineVisible: false,
    priceFormat: { type: "price", precision: 0, minMove: 1 },
  }, 0);
  const line = chart.addSeries(LC.LineSeries, {
    color: lpmToken("--chart-series-1") || lpmToken("--text-primary"), lineWidth: 2, priceLineVisible: false,
    priceScaleId: "left",
    priceFormat: { type: "price", precision: 1, minMove: 0.1 },
  }, 0);
  const lens = chart.addSeries(LC.HistogramSeries, {
    priceLineVisible: false, lastValueVisible: false,
    priceFormat: { type: "price", precision: 2, minMove: 0.01 },
  }, 1);
  const markers = LC.createSeriesMarkers(candle, []);

  const panes = chart.panes();
  [75, 25].forEach((factor, i) => panes[i] && panes[i].setStretchFactor(factor));

  chart.subscribeCrosshairMove((param) => renderLpmLegend(lpmTimeKey(param.time)));

  // The page may still be laying out when the chart is created; fitting at that width squeezes
  // all bars into the right edge, so fit again whenever the container settles on a new width
  let lastWidth = 0;
  lpmState.resizeObserver = new ResizeObserver((entries) => {
    const width = Math.round(entries[0].contentRect.width);
    if (width > 0 && width !== lastWidth) {
      lastWidth = width;
      chart.timeScale().fitContent();
    }
  });
  lpmState.resizeObserver.observe(container);

  lpmState.chart = chart;
  lpmState.series = { candle, line, lens, markers };
  return true;
}

function renderLpmChart(data) {
  lpmEl("lpm-lens-note").textContent = LPM_LENS_NOTE[lpmState.lens];
  if (!ensureLpmChart()) return;
  const { candle, line, markers } = lpmState.series;
  const muted = lpmToken("--text-muted");
  const up = lpmToken("--chart-up") || lpmToken("--status-confirmed-text");
  const down = lpmToken("--chart-down") || lpmToken("--status-fail-text");
  const rows = data.series;

  candle.setData(rows
    .filter((s) => s.open !== null && s.close !== null)
    .map((s) => ({ time: s.date, open: s.open, high: s.high, low: s.low, close: s.close })));

  line.setData(rows.map((s) => (s.gap ? { time: s.date, value: s.lpm, color: muted } : { time: s.date, value: s.lpm })));

  markers.setMarkers((data.divergence.markers || []).map((m) => {
    const positive = m.type === "POSITIVE";
    return {
      time: m.date,
      position: positive ? "belowBar" : "aboveBar",
      shape: positive ? "arrowUp" : "arrowDown",
      color: positive ? up : down,
      text: positive ? "Akumulasi" : "Distribusi",
    };
  }));

  applyLensData(rows);
  lpmState.chart.timeScale().fitContent();
  // The price axis takes its width only after the first draw; fit once more against the final plot width
  requestAnimationFrame(() => lpmState.chart && lpmState.chart.timeScale().fitContent());
  renderLpmLegend(null);
}

function updateLpmChartTheme() {
  if (!lpmState.chart || !lpmState.series) return;
  const border = lpmToken("--border-subtle");
  const gridColor = lpmToken("--chart-grid") || border;
  const textColor = lpmToken("--chart-text") || lpmToken("--text-muted");
  const bg = lpmToken("--bg-secondary");
  const up = lpmToken("--chart-up") || lpmToken("--status-confirmed-text");
  const down = lpmToken("--chart-down") || lpmToken("--status-fail-text");
  const seriesColor = lpmToken("--chart-series-1") || lpmToken("--text-primary");

  lpmState.chart.applyOptions({
    layout: {
      background: { type: "solid", color: bg },
      textColor: textColor,
      panes: { separatorColor: border },
    },
    grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
    rightPriceScale: { borderColor: border },
    leftPriceScale: { borderColor: border },
    timeScale: { borderColor: border },
  });

  if (lpmState.series.candle) {
    lpmState.series.candle.applyOptions({
      upColor: up,
      downColor: down,
      wickUpColor: up,
      wickDownColor: down,
    });
  }

  if (lpmState.series.line) {
    lpmState.series.line.applyOptions({
      color: seriesColor,
    });
  }

  if (lpmState.data) {
    renderLpmChart(lpmState.data);
  }
}

document.addEventListener("themechange", updateLpmChartTheme);

function applyLensData(rows) {
  const LC = window.LightweightCharts;
  const { lens } = lpmState.series;
  const muted = lpmToken("--text-muted");

  if (lpmState.lensPriceLine) {
    lens.removePriceLine(lpmState.lensPriceLine);
    lpmState.lensPriceLine = null;
  }

  if (lpmState.lens === "intensity") {
    const base = lpmToken("--status-div-hid-text");
    const colors = { NORMAL: lpmWithAlpha(base, 0.3), SPIKE: lpmWithAlpha(base, 0.65), SPIKE_EKSTREM: base };
    lens.setData(rows.map((s) => (s.intensity === null
      ? { time: s.date }
      : { time: s.date, value: s.intensity, color: colors[s.intensity_level] || muted })));
    lpmState.lensPriceLine = lens.createPriceLine({
      price: 1.5, color: muted, lineWidth: 1, lineStyle: LC.LineStyle.Dashed, axisLabelVisible: false,
    });
  } else {
    const colors = {
      HIJAU: lpmToken("--status-confirmed-text"),
      KUNING: lpmToken("--status-watchlist-text"),
      MERAH: lpmToken("--status-fail-text"),
    };
    lens.setData(rows.map((s) => (s.vr_efficiency === null
      ? { time: s.date }
      : { time: s.date, value: s.vr_efficiency, color: colors[s.vr_color] || muted })));
  }
}

function renderLpmLegend(dateKey) {
  const legend = lpmEl("lpm-legend");
  const rows = lpmState.data ? lpmState.data.series : [];
  if (!rows.length) {
    legend.textContent = "";
    return;
  }
  const row = (dateKey && rows.find((s) => s.date === dateKey)) || rows[rows.length - 1];
  const parts = [row.date, `Close ${lpmFmt(row.close, 0)}`];
  if (row.gap) {
    parts.push("data broker belum ada");
  } else {
    parts.push(`LPM ${lpmFmt(row.lpm, 1)}`, `Pressure ${lpmFmt(row.pressure * 100, 1, true)}`);
    if (lpmState.lens === "intensity") {
      parts.push(row.intensity === null ? "Intensity --" : `Intensity ${lpmFmt(row.intensity, 2, true)}${row.intensity_level && row.intensity_level !== "NORMAL" ? ` (${row.intensity_level === "SPIKE" ? "spike" : "spike ekstrem"})` : ""}`);
    } else {
      parts.push(row.vr_percentile === null ? "Vol Rotation --" : `Vol Rotation persentil ${lpmFmt(row.vr_percentile, 0)} (${row.vr_color.toLowerCase()})`);
    }
    if (row.low_liquidity) parts.push("transaksi tipis");
  }
  legend.textContent = parts.join(" · ");
}

// ----------------------------------------------------------------------------
// 5. Backfill & polling
// ----------------------------------------------------------------------------

async function startLpmBackfill() {
  const ticker = lpmState.ticker;
  if (!ticker) return;
  const buttons = [lpmEl("lpm-backfill-btn"), lpmEl("lpm-state-action")];
  buttons.forEach((b) => { b.disabled = true; });

  try {
    const resp = await fetch(`/api/idx/lpm/${ticker}/backfill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const body = await resp.json().catch(() => ({}));
    if (ticker !== lpmState.ticker) return;
    if (body.quota && typeof updateSidebarQuota === "function") updateSidebarQuota(body.quota);

    if (!resp.ok) {
      const note = lpmEl("lpm-coverage-note");
      note.textContent = body.message || `Backfill tidak bisa dimulai (status ${resp.status}).`;
      note.classList.remove("hidden");
      lpmEl("lpm-coverage").classList.remove("hidden");
      buttons.forEach((b) => { b.disabled = resp.status === 409; });
      return;
    }

    if (body.status === "complete") {
      loadLpmPanel(ticker, true);
      return;
    }

    const job = { state: "running", done: 0, total: body.missing_days, requested: 0 };
    if (lpmState.data) {
      lpmState.data.backfill = job;
      renderLpm(lpmState.data, body.quota || lpmState.quota);
    }
    startLpmPolling();
  } catch (err) {
    console.error("LPM backfill start error:", err);
    buttons.forEach((b) => { b.disabled = false; });
    const note = lpmEl("lpm-coverage-note");
    note.textContent = "Server tidak bisa dihubungi, backfill belum dimulai. Coba lagi.";
    note.classList.remove("hidden");
  }
}

function startLpmPolling() {
  stopLpmPolling();
  const ticker = lpmState.ticker;
  lpmState.pollCount = 0;
  lpmState.pollTimer = setInterval(() => pollLpmStatus(ticker), LPM_POLL_MS);
  pollLpmStatus(ticker);
}

function stopLpmPolling() {
  if (lpmState.pollTimer) clearInterval(lpmState.pollTimer);
  lpmState.pollTimer = null;
}

async function pollLpmStatus(ticker) {
  if (ticker !== lpmState.ticker) {
    stopLpmPolling();
    return;
  }
  try {
    const job = await fetch(`/api/idx/lpm/${ticker}/status`).then((r) => r.json());
    if (ticker !== lpmState.ticker) return;
    if (job.quota) {
      lpmState.quota = job.quota;
      if (typeof updateSidebarQuota === "function") updateSidebarQuota(job.quota);
    }

    if (job.state !== "running") {
      stopLpmPolling();
      delete lpmCache[ticker];
      loadLpmPanel(ticker, true);
      loadLpmStoredList();
      return;
    }

    if (lpmState.data) lpmState.data.backfill = job;
    renderLpmProgress(job);
    lpmState.pollCount += 1;
    if (lpmState.pollCount % LPM_REFRESH_EVERY_POLLS === 0) {
      loadLpmPanel(ticker, true, true);
    }
  } catch (err) {
    // A missed poll is harmless; the next tick tries again
    console.warn("LPM status poll failed:", err);
  }
}
