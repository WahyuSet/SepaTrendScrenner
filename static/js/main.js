// ============================================================================
// SIDEBAR & IDX MARKET STATUS CONTROLLERS
// ============================================================================

function updateSidebarLastScan(timeStr) {
  const el = document.getElementById('sidebar-last-scan');
  if (!el) return;
  if (timeStr && timeStr !== 'Belum pernah scan') {
    el.textContent = timeStr;
    el.title = `Scan terakhir: ${timeStr}`;
  }
}

function calculateClientIDXMarketStatus() {
  // Asia/Jakarta (UTC+7)
  const now = new Date();
  const jakartaStr = now.toLocaleString("en-US", { timeZone: "Asia/Jakarta" });
  const jkt = new Date(jakartaStr);

  const day = jkt.getDay(); // 0 = Sun, 6 = Sat
  const hour = jkt.getHours();
  const minute = jkt.getMinutes();
  const tMin = hour * 60 + minute;

  if (day === 0 || day === 6) {
    return {
      status: 'closed',
      label: 'IDX Closed',
      detail: 'Pasar Libur (Akhir Pekan)'
    };
  }

  const isFriday = (day === 5);
  const s1End = isFriday ? (11 * 60 + 30) : (12 * 60);
  const s2Start = isFriday ? (14 * 60) : (13 * 60 + 30);

  if (tMin < 8 * 60 + 45) {
    return { status: 'closed', label: 'IDX Closed', detail: 'Buka Sesi 1 jam 09:00 WIB' };
  } else if (tMin < 9 * 60) {
    return { status: 'break', label: 'IDX Pre-Open', detail: 'Pra-Pembukaan (08:45 - 08:59 WIB)' };
  } else if (tMin < s1End) {
    return { status: 'open', label: 'IDX Open (Sesi 1)', detail: 'Perdagangan Sesi 1 Aktif' };
  } else if (tMin < s2Start) {
    return { status: 'break', label: 'IDX Break', detail: 'Istirahat Siang Pasar Saham' };
  } else if (tMin < 15 * 60 + 50) {
    return { status: 'open', label: 'IDX Open (Sesi 2)', detail: 'Perdagangan Sesi 2 Aktif' };
  } else if (tMin <= 16 * 60 + 15) {
    return { status: 'break', label: 'IDX Pre-Close', detail: 'Pra-Penutupan (15:50 - 16:15 WIB)' };
  } else {
    return { status: 'closed', label: 'IDX Closed', detail: 'Pasar Tutup (Buka kembali 09:00 WIB)' };
  }
}

function updateIDXMarketStatusUI(serverStatus = null) {
  const pill = document.getElementById('sidebar-market-pill');
  const text = document.getElementById('sidebar-market-text');
  if (!pill || !text) return;

  const info = serverStatus || calculateClientIDXMarketStatus();

  pill.className = `system-status-pill ${info.status || 'closed'}`;
  text.textContent = info.label || 'IDX Closed';
  pill.title = info.detail || 'Status Perdagangan Bursa Efek Indonesia';
}

document.addEventListener('DOMContentLoaded', () => {
  initSliderVisuals();
  updateIDXMarketStatusUI();
  // Keep market status real-time every 30 seconds
  setInterval(updateIDXMarketStatusUI, 30000);

  checkScanStatus();

  // Initial load of cached results across all four screeners + market regime + RS distribution
  loadMarketRegime();
  loadRsDistribution();
  loadCachedResults();
  loadRsiResults();
  loadPreBreakoutResults();
  loadQualityResults();
  loadWatchlistAndJournal();
  if (typeof loadBacktestData === 'function') loadBacktestData();

  const btnRefreshRs = document.getElementById('btn-refresh-rs-dist');
  if (btnRefreshRs) {
    btnRefreshRs.addEventListener('click', handleRefreshRsDistribution);
  }

  const btnCopyAllRs = document.getElementById('btn-copy-all-rs');
  if (btnCopyAllRs) {
    btnCopyAllRs.addEventListener('click', handleCopyAllRsDistribution);
  }

  initRsChipsCopyEvents();
});

async function loadMarketRegime() {
  const banner = document.getElementById('market-regime-banner');
  if (!banner) return;

  try {
    const res = await fetch('/api/market-regime');
    if (res.status === 401) return;
    const json = await res.json();
    if (json.status === 'success' && json.data) {
      renderMarketRegime(json.data);
    }
  } catch (err) {
    console.error('Failed to load market regime:', err);
  }
}

function renderMarketRegime(data) {
  const banner = document.getElementById('market-regime-banner');
  if (!banner) return;

  banner.className = `market-regime-card regime-${data.color || 'yellow'}`;

  const badge = document.getElementById('regime-badge');
  if (badge) {
    badge.textContent = data.regime_label || 'UPTREND UNDER PRESSURE';
    badge.className = `regime-pill ${data.badge_class || 'badge-regime-yellow'}`;
  }

  const ihsgVal = document.getElementById('regime-ihsg-val');
  if (ihsgVal) {
    ihsgVal.textContent = data.current_close ? data.current_close.toLocaleString('id-ID', { minimumFractionDigits: 2 }) : '--';
  }

  const ihsgChg = document.getElementById('regime-ihsg-chg');
  if (ihsgChg) {
    const sign = data.chg_pts >= 0 ? '+' : '';
    const chgClass = data.chg_pts >= 0 ? 'pos' : 'neg';
    ihsgChg.className = `regime-chg ${chgClass}`;
    ihsgChg.textContent = `${sign}${data.chg_pts ? data.chg_pts.toFixed(2) : '0.00'} (${sign}${data.chg_pct ? data.chg_pct.toFixed(2) : '0.00'}%)`;
  }

  const maInfo = document.getElementById('regime-ma-info');
  if (maInfo) {
    const sign50 = data.dist_ma50_pct >= 0 ? '+' : '';
    const sign200 = data.dist_ma200_pct >= 0 ? '+' : '';
    maInfo.textContent = `MA50: ${data.ma50 ? data.ma50.toLocaleString('id-ID') : '--'} (${sign50}${data.dist_ma50_pct}%) | MA200: ${data.ma200 ? data.ma200.toLocaleString('id-ID') : '--'} (${sign200}${data.dist_ma200_pct}%)`;
  }

  const exposureVal = document.getElementById('regime-exposure-val');
  if (exposureVal) {
    exposureVal.textContent = data.exposure_label || 'Exposure 50%';
    exposureVal.className = `exposure-value exposure-${data.color || 'yellow'}`;
  }

  const actionDesc = document.getElementById('regime-action-desc');
  if (actionDesc) {
    actionDesc.textContent = data.action_desc || '';
  }

  const timeEl = document.getElementById('regime-updated-time');
  if (timeEl) {
    timeEl.textContent = `Update: ${data.updated_at || '--'}`;
  }
}

async function loadRsDistribution() {
  const container = document.getElementById('regime-rs-row');
  if (!container) return;

  try {
    const res = await fetch('/api/rs-distribution');
    if (res.status === 401) return;
    const json = await res.json();
    if (json.status === 'success' && json.data) {
      renderRsDistribution(json.data);
    }
  } catch (err) {
    console.error('Failed to load RS distribution:', err);
  }
}

function renderRsDistribution(data) {
  if (!data || !data.distribution) return;

  const totalStocks = document.getElementById('rs-dist-total-stocks');
  if (totalStocks) {
    totalStocks.textContent = data.total_stocks || '--';
  }

  const dateEl = document.getElementById('rs-dist-date');
  if (dateEl) {
    dateEl.textContent = data.date || '--';
  }

  const dist = data.distribution;
  const pMap = {
    'p99': dist.pct_99,
    'p90': dist.pct_90,
    'p70': dist.pct_70,
    'p50': dist.pct_50,
    'p30': dist.pct_30,
    'p10': dist.pct_10,
    'p01': dist.pct_01
  };

  for (const [key, val] of Object.entries(pMap)) {
    const el = document.getElementById(`rs-val-${key}`);
    if (el) {
      el.textContent = (val !== undefined && val !== null) ? Number(val).toFixed(2) : '--';
    }
  }
}

async function handleRefreshRsDistribution() {
  const btn = document.getElementById('btn-refresh-rs-dist');
  const label = document.getElementById('rs-refresh-label');
  if (btn) btn.classList.add('spinning');
  if (label) label.textContent = 'Menghitung...';

  if (typeof showToast === 'function') {
    showToast('info', 'Memulai kalkulasi distribusi RS Score seluruh IDX...', 4000);
  }

  try {
    const res = await fetch('/api/rs-distribution/refresh', { method: 'POST' });
    const json = await res.json();
    if (json.status === 'success' && json.data) {
      renderRsDistribution(json.data);
      if (typeof showToast === 'function') {
        showToast('success', `Distribusi RS diperbarui untuk ${json.data.total_stocks} saham!`);
      }
    } else {
      if (typeof showToast === 'function') {
        showToast('error', json.message || 'Gagal menghitung distribusi RS');
      }
    }
  } catch (err) {
    console.error('Error refreshing RS distribution:', err);
    if (typeof showToast === 'function') {
      showToast('error', 'Koneksi gagal saat refresh distribusi RS');
    }
  } finally {
    if (btn) btn.classList.remove('spinning');
    if (label) label.textContent = 'Refresh RS';
  }
}

function initRsChipsCopyEvents() {
  const chips = document.querySelectorAll('.regime-rs-chips .rs-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const pct = chip.getAttribute('data-pct') || 'RS';
      const targetId = chip.getAttribute('data-target');
      const valEl = targetId ? document.getElementById(targetId) : chip.querySelector('.rs-chip-val');
      const val = valEl ? valEl.textContent.trim() : '';

      if (!val || val === '--') return;

      chip.classList.add('copied');
      setTimeout(() => chip.classList.remove('copied'), 400);

      if (typeof copyToClipboard === 'function') {
        copyToClipboard(val, `📋 RS Score ${pct}: ${val} tersalin ke clipboard!`);
      }
    });
  });
}

function handleCopyAllRsDistribution() {
  const pMap = ['p99', 'p90', 'p70', 'p50', 'p30', 'p10', 'p01'];
  const labels = {'p99': 'P99', 'p90': 'P90', 'p70': 'P70', 'p50': 'P50 (Med)', 'p30': 'P30', 'p10': 'P10', 'p01': 'P01'};
  const lines = [];

  pMap.forEach(k => {
    const el = document.getElementById(`rs-val-${k}`);
    const v = el ? el.textContent.trim() : '--';
    lines.push(`${labels[k]}: ${v}`);
  });

  const totalStocks = document.getElementById('rs-dist-total-stocks')?.textContent || '--';
  const dateStr = document.getElementById('rs-dist-date')?.textContent || '--';
  const text = `Distribusi RS Score IDX (vs IHSG) - ${dateStr} (Semesta: ${totalStocks} Saham)\n` + lines.join(' | ');

  const btn = document.getElementById('btn-copy-all-rs');
  const label = document.getElementById('copy-all-rs-label');
  if (label) label.textContent = 'Tersalin!';
  setTimeout(() => {
    if (label) label.textContent = 'Salin Semua';
  }, 1500);

  if (typeof copyToClipboard === 'function') {
    copyToClipboard(text, '📋 7 Titik Distribusi RS Score IDX berhasil disalin!');
  }
}

function initSliderVisuals() {
  const slider = document.getElementById('score-slider');
  if (slider) {
    updateSliderBackground(slider.value);
  }
}

function updateSliderBackground(val) {
  const pct = ((val - 1) / 7) * 100;
  const slider = document.getElementById('score-slider');
  if (slider) {
    slider.style.background = `linear-gradient(to right, var(--brand-lime) 0%, var(--brand-lime) ${pct}%, var(--bg-tertiary) ${pct}%, var(--bg-tertiary) 100%)`;
  }
}

function switchScreener(screenerId) {
  // Hide all views
  ['view-sepa', 'view-rsi-div', 'view-prebreakout', 'view-quality', 'view-watchlist', 'view-backtest'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.classList.remove('active');
      el.classList.add('hidden');
    }
  });

  // Remove active from all nav items / tabs
  ['nav-sepa', 'nav-rsi-div', 'nav-prebreakout', 'nav-quality', 'nav-watchlist', 'nav-backtest'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });

  if (screenerId === 'sepa') {
    document.getElementById('view-sepa')?.classList.remove('hidden');
    document.getElementById('view-sepa')?.classList.add('active');
    document.getElementById('nav-sepa')?.classList.add('active');
  } else if (screenerId === 'rsi-div') {
    document.getElementById('view-rsi-div')?.classList.remove('hidden');
    document.getElementById('view-rsi-div')?.classList.add('active');
    document.getElementById('nav-rsi-div')?.classList.add('active');
  } else if (screenerId === 'prebreakout') {
    document.getElementById('view-prebreakout')?.classList.remove('hidden');
    document.getElementById('view-prebreakout')?.classList.add('active');
    document.getElementById('nav-prebreakout')?.classList.add('active');
  } else if (screenerId === 'quality' || screenerId === 'quality-setup') {
    document.getElementById('view-quality')?.classList.remove('hidden');
    document.getElementById('view-quality')?.classList.add('active');
    document.getElementById('nav-quality')?.classList.add('active');
  } else if (screenerId === 'watchlist' || screenerId === 'journal') {
    document.getElementById('view-watchlist')?.classList.remove('hidden');
    document.getElementById('view-watchlist')?.classList.add('active');
    document.getElementById('nav-watchlist')?.classList.add('active');
    loadWatchlistAndJournal();
  } else if (screenerId === 'backtest' || screenerId === 'lab') {
    document.getElementById('view-backtest')?.classList.remove('hidden');
    document.getElementById('view-backtest')?.classList.add('active');
    document.getElementById('nav-backtest')?.classList.add('active');
    if (typeof loadBacktestData === 'function') {
      loadBacktestData();
    }
  }
}

function refreshActiveScreener() {
  updateIDXMarketStatusUI();
  Promise.all([
    loadMarketRegime(),
    loadCachedResults(),
    loadRsiResults(),
    loadPreBreakoutResults(),
    loadQualityResults(),
    loadWatchlistAndJournal(),
    checkScanStatus()
  ]).then(() => {
    showToast('✓ Data berhasil dimuat ulang dari server!');
  });
}
