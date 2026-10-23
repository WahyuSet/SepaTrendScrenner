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
  const errBox = document.getElementById('regime-error-state');
  const topRow = banner.querySelector('.regime-top-row');

  try {
    const res = await fetch('/api/market-regime');
    if (res.status === 401) return;
    const json = await res.json();
    if (json.status === 'success' && json.data) {
      if (errBox) errBox.classList.add('hidden');
      if (topRow) topRow.classList.remove('hidden');
      renderMarketRegime(json.data);
    } else {
      throw new Error((json && json.message) || 'Gagal memuat status pasar');
    }
  } catch (err) {
    console.error('Failed to load market regime:', err);
    banner.classList.remove('regime-loading');
    if (errBox) errBox.classList.remove('hidden');
    if (topRow) topRow.classList.add('hidden');
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
        copyToClipboard(val, `RS Score ${pct}: ${val} tersalin ke clipboard!`);
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
    copyToClipboard(text, '7 Titik Distribusi RS Score IDX berhasil disalin!');
  }
}

// ============================================================================
// SCREENER ROUTING CONFIGURATION (Design.md §9, UI_REFACTOR_PLAN Fase 9)
// ============================================================================

const SCREENER_CONFIG = {
  'sepa': { viewId: 'view-sepa', navId: 'nav-sepa' },
  'rsi-div': { viewId: 'view-rsi-div', navId: 'nav-rsi-div' },
  'prebreakout': { viewId: 'view-prebreakout', navId: 'nav-prebreakout' },
  'quality': { viewId: 'view-quality', navId: 'nav-quality' },
  'quality-setup': { viewId: 'view-quality', navId: 'nav-quality' },
  'watchlist': {
    viewId: 'view-watchlist',
    navId: 'nav-watchlist',
    onActivate: () => { if (typeof loadWatchlistAndJournal === 'function') loadWatchlistAndJournal(); }
  },
  'journal': {
    viewId: 'view-watchlist',
    navId: 'nav-watchlist',
    onActivate: () => { if (typeof loadWatchlistAndJournal === 'function') loadWatchlistAndJournal(); }
  },
  'backtest': {
    viewId: 'view-backtest',
    navId: 'nav-backtest',
    onActivate: () => { if (typeof loadBacktestData === 'function') loadBacktestData(); }
  },
  'lab': {
    viewId: 'view-backtest',
    navId: 'nav-backtest',
    onActivate: () => { if (typeof loadBacktestData === 'function') loadBacktestData(); }
  },
  'lpm': {
    viewId: 'view-lpm',
    navId: 'nav-lpm',
    onActivate: () => { if (typeof initLpmPage === 'function') initLpmPage(); }
  }
};

function switchScreener(screenerId) {
  const target = SCREENER_CONFIG[screenerId];
  if (!target) return;

  // Hide all views
  document.querySelectorAll('.screener-view').forEach(el => {
    el.classList.remove('active');
    el.classList.add('hidden');
  });

  // Remove active from all nav items / tabs
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.remove('active');
    el.removeAttribute('aria-current');
  });

  const viewEl = document.getElementById(target.viewId);
  const navEl = document.getElementById(target.navId);

  if (viewEl) {
    viewEl.classList.remove('hidden');
    viewEl.classList.add('active');
  }

  if (navEl) {
    navEl.classList.add('active');
    navEl.setAttribute('aria-current', 'page');
  }

  if (typeof target.onActivate === 'function') {
    target.onActivate();
  }

  // Auto-close mobile drawer after navigating on phone/tablet (Design.md §9: <= 1024px)
  if (window.innerWidth <= 1024) {
    closeMobileSidebar();
  }
}

// ============================================================================
// CENTRALIZED DATA-ACTION EVENT DELEGATION ROUTER (Fase 9)
// ============================================================================

const APP_ACTIONS = {
  'switch-screener': (el) => {
    const s = el.dataset.screener || el.getAttribute('data-screener');
    if (s) switchScreener(s);
  },
  'open-command-palette': () => {
    if (typeof openCommandPalette === 'function') openCommandPalette();
  },
  'toggle-theme': () => {
    if (typeof toggleTheme === 'function') toggleTheme();
  },
  'toggle-mobile-sidebar': () => {
    if (typeof toggleMobileSidebar === 'function') toggleMobileSidebar();
  },
  'close-mobile-sidebar': () => {
    if (typeof closeMobileSidebar === 'function') closeMobileSidebar();
  },
  'trigger-scan': () => {
    if (typeof triggerScan === 'function') triggerScan();
  },
  'refresh-screener': () => {
    if (typeof refreshActiveScreener === 'function') refreshActiveScreener();
  },
  'refresh-market-regime': () => {
    if (typeof loadMarketRegime === 'function') loadMarketRegime();
  },
  'open-position-calculator': () => {
    if (typeof openPositionCalculator === 'function') openPositionCalculator();
  },
  'close-position-calculator': () => {
    if (typeof closePositionCalculator === 'function') closePositionCalculator();
  },
  'toggle-advanced-calc': () => {
    if (typeof toggleAdvancedCalcSettings === 'function') toggleAdvancedCalcSettings();
  },
  'set-risk-preset': (el) => {
    const r = parseFloat(el.dataset.risk || '1.0');
    if (typeof setRiskPreset === 'function') setRiskPreset(r);
  },
  'copy-position-sizing': () => {
    if (typeof copyPositionSizingSummary === 'function') copyPositionSizingSummary();
  },
  'transfer-calc-journal': () => {
    if (typeof transferCalcToTradeJournal === 'function') transferCalcToTradeJournal();
  },
  'copy-modal-rs': () => {
    if (typeof copyModalRSValue === 'function') copyModalRSValue();
  },
  'copy-all-rs-distribution': () => {
    if (typeof handleCopyAllRsDistribution === 'function') handleCopyAllRsDistribution();
  },
  'reset-sepa-filters': () => {
    if (typeof resetSepaFilters === 'function') resetSepaFilters();
  },
  'reset-rsi-filters': () => {
    if (typeof resetRsiFilters === 'function') resetRsiFilters();
  },
  'reset-pb-filters': () => {
    if (typeof resetPreBreakoutFilters === 'function') resetPreBreakoutFilters();
  },
  'reset-quality-filters': () => {
    if (typeof resetQualityFilters === 'function') resetQualityFilters();
  },
  'reset-backtest-filters': () => {
    if (typeof resetBacktestTableFilters === 'function') resetBacktestTableFilters();
  },
  'reset-universe-benchmark': () => {
    if (typeof resetToUniverseBenchmark === 'function') resetToUniverseBenchmark();
  },
  'export-csv': (el) => {
    const type = el.dataset.screener || el.dataset.type || 'sepa';
    if (typeof exportTableToCsv === 'function') exportTableToCsv(type);
  },
  'export-sepa-csv': () => {
    if (typeof exportTableToCsv === 'function') exportTableToCsv('sepa');
  },
  'export-rsi-csv': () => {
    if (typeof exportTableToCsv === 'function') exportTableToCsv('rsi');
  },
  'export-pb-csv': () => {
    if (typeof exportTableToCsv === 'function') exportTableToCsv('prebreakout');
  },
  'export-quality-csv': () => {
    if (typeof exportQualityCSV === 'function') exportQualityCSV();
  },
  'export-journal-csv': () => {
    if (typeof exportJournalCSV === 'function') exportJournalCSV();
  },
  'export-journal-backup': () => {
    if (typeof exportJournalBackupJSON === 'function') exportJournalBackupJSON();
  },
  'restore-journal-backup': () => {
    if (typeof triggerRestoreBackupInput === 'function') triggerRestoreBackupInput();
  },
  'export-backtest-csv': () => {
    if (typeof exportBacktestTradesCSV === 'function') exportBacktestTradesCSV();
  },
  'copy-tradingview': (el) => {
    const type = el.dataset.screener || el.dataset.type || 'sepa';
    if (typeof copyTradingViewWatchlist === 'function') copyTradingViewWatchlist(type);
  },
  'open-new-trade-modal': () => {
    if (typeof openNewTradeEntryModal === 'function') openNewTradeEntryModal();
  },
  'open-portfolio-settings': () => {
    if (typeof openPortfolioSettingsModal === 'function') openPortfolioSettingsModal();
  },
  'refresh-backtest': () => {
    if (typeof refreshBacktestBenchmark === 'function') refreshBacktestBenchmark();
  },
  'refresh-lpm': () => {
    if (typeof refreshLpmPage === 'function') refreshLpmPage();
  }
};

document.addEventListener('click', (e) => {
  const trigger = e.target.closest('[data-action]');
  if (!trigger) return;
  const actionName = trigger.getAttribute('data-action');
  if (APP_ACTIONS[actionName]) {
    APP_ACTIONS[actionName](trigger, e);
  }
});

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

// ============================================================================
// THEME TOGGLE (the initial theme is set by the inline script in <head>)
// ============================================================================

function syncThemeToggle() {
  const btn = document.getElementById('btn-theme-toggle');
  if (btn) btn.setAttribute('aria-pressed', String(document.documentElement.dataset.theme === 'dark'));
}

function toggleTheme() {
  const root = document.documentElement;
  const next = root.dataset.theme === 'dark' ? 'light' : 'dark';

  // Swap colors at once instead of letting every transition animate:
  // the forced reflow commits the new colors while transitions are off
  root.classList.add('theme-switching');
  root.dataset.theme = next;
  void document.body.offsetHeight;
  root.classList.remove('theme-switching');

  try { localStorage.setItem('theme', next); } catch (e) {}
  syncThemeToggle();
  document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
}

document.addEventListener('DOMContentLoaded', syncThemeToggle);

// ============================================================================
// MOBILE NAVIGATION & DRAWER CONTROLLER (Design.md §9)
// ============================================================================

function toggleMobileSidebar() {
  const sidebar = document.getElementById('app-sidebar') || document.querySelector('.sidebar');
  if (!sidebar) return;

  const isOpen = sidebar.classList.contains('mobile-open');
  if (isOpen) {
    closeMobileSidebar();
  } else {
    openMobileSidebar();
  }
}

function openMobileSidebar() {
  const sidebar = document.getElementById('app-sidebar') || document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const menuBtn = document.getElementById('btn-mobile-menu');
  const closeBtn = document.getElementById('btn-sidebar-close');

  if (sidebar) {
    sidebar.classList.add('mobile-open');
    sidebar.setAttribute('aria-hidden', 'false');
  }
  if (overlay) overlay.classList.add('active');
  if (menuBtn) menuBtn.setAttribute('aria-expanded', 'true');
  document.body.classList.add('sidebar-locked');

  // Move focus into drawer
  if (closeBtn) {
    closeBtn.focus();
  } else if (sidebar) {
    sidebar.focus();
  }
}

function closeMobileSidebar() {
  const sidebar = document.getElementById('app-sidebar') || document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const menuBtn = document.getElementById('btn-mobile-menu');

  if (!sidebar || !sidebar.classList.contains('mobile-open')) return;

  sidebar.classList.remove('mobile-open');
  if (window.innerWidth <= 1024) {
    sidebar.setAttribute('aria-hidden', 'true');
  } else {
    sidebar.removeAttribute('aria-hidden');
  }

  if (overlay) overlay.classList.remove('active');
  if (menuBtn) {
    menuBtn.setAttribute('aria-expanded', 'false');
    // Restore focus if focus was inside sidebar
    if (sidebar.contains(document.activeElement)) {
      menuBtn.focus();
    }
  }
  document.body.classList.remove('sidebar-locked');
}

// Close drawer on Escape key or on window resize > 1024px
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const sidebar = document.getElementById('app-sidebar') || document.querySelector('.sidebar');
    if (sidebar && sidebar.classList.contains('mobile-open')) {
      closeMobileSidebar();
      e.stopPropagation();
    }
  }
});

window.addEventListener('resize', () => {
  if (window.innerWidth > 1024) {
    closeMobileSidebar();
    const sidebar = document.getElementById('app-sidebar') || document.querySelector('.sidebar');
    if (sidebar) sidebar.removeAttribute('aria-hidden');
  }
});
