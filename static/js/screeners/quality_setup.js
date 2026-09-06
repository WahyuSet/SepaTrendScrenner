// ============================================================================
// QUALITY SETUP SCREENER MODULE (static/js/screeners/quality_setup.js)
// ============================================================================

const qualityState = {
  allResults: [],
  filteredResults: [],
  tabFilter: 'ALL', // 'ALL' | 'ELITE' | 'BREAKOUT' | 'PULLBACK'
  sectorFilter: 'ALL',
  searchQuery: '',
  sortCol: 'score',
  sortAsc: false,
  selectedStock: null
};

// 1. DATA LOADER
async function loadQualityResults() {
  renderQualitySkeleton(8);
  try {
    const res = await fetch('/api/quality-setup');
    const json = await res.json();

    if (json.status === 'success' && json.data) {
      const { scan_time, total_scanned, passed_count, elite_count, strong_count, breakout_count, pullback_count, avg_rr, data } = json.data;
      qualityState.allResults = data || [];
      renderQualityStatsCards(json.data);
      populateQualitySectorDropdown(qualityState.allResults);
      updateQualityTabCounters();
      applyQualityFilters();
    } else {
      renderQualityStatsCards(null);
      qualityState.allResults = [];
      applyQualityFilters();
    }
  } catch (err) {
    console.error('Failed to load Quality Setup results:', err);
    qualityState.allResults = [];
    applyQualityFilters();
  }
}

// 2. STATS CARDS & COUNTERS
function renderQualityStatsCards(stats) {
  const statTotal = document.getElementById('qs-stat-total');
  const statElite = document.getElementById('qs-stat-elite');
  const statStrong = document.getElementById('qs-stat-strong');
  const statRR = document.getElementById('qs-stat-rr');
  const statTime = document.getElementById('qs-stat-last-time');
  const badgeNav = document.getElementById('badge-quality');

  const count = stats ? (stats.passed_count || qualityState.allResults.length) : qualityState.allResults.length;

  if (statTotal) statTotal.textContent = count;
  if (statElite) statElite.textContent = stats ? (stats.elite_count || 0) : 0;
  if (statStrong) statStrong.textContent = stats ? (stats.strong_count || 0) : 0;
  if (statRR) statRR.textContent = stats && stats.avg_rr ? `1 : ${stats.avg_rr}` : '1 : 2.5';

  const timeText = (stats && stats.scan_time) ? stats.scan_time : 'Belum pernah scan';
  if (statTime) statTime.textContent = timeText;
  if (badgeNav) badgeNav.textContent = count > 0 ? count : (stats ? '0' : '—');
}

function updateQualityTabCounters() {
  const all = qualityState.allResults.length;
  const elite = qualityState.allResults.filter(r => r.grade === 'Elite').length;
  const breakout = qualityState.allResults.filter(r => (r.setup_type || '').includes('Breakout')).length;
  const pullback = qualityState.allResults.filter(r => (r.setup_type || '').includes('Pullback')).length;

  const elAll = document.getElementById('cnt-qs-all');
  const elElite = document.getElementById('cnt-qs-elite');
  const elBreakout = document.getElementById('cnt-qs-breakout');
  const elPullback = document.getElementById('cnt-qs-pullback');

  if (elAll) elAll.textContent = all;
  if (elElite) elElite.textContent = elite;
  if (elBreakout) elBreakout.textContent = breakout;
  if (elPullback) elPullback.textContent = pullback;
}

function populateQualitySectorDropdown(results) {
  const select = document.getElementById('qs-sector-filter');
  if (!select) return;

  const currentVal = select.value;
  const sectors = Array.from(new Set(results.map(r => r.sector || 'General'))).filter(Boolean).sort();

  let html = '<option value="ALL">Semua Sektor (All)</option>';
  sectors.forEach(sec => {
    html += `<option value="${sec}">${sec}</option>`;
  });
  select.innerHTML = html;
  if (sectors.includes(currentVal)) {
    select.value = currentVal;
  }
}

// 3. SKELETON LOADER
function renderQualitySkeleton(count = 8) {
  const tbody = document.getElementById('quality-table-body');
  if (!tbody) return;

  let html = '';
  for (let i = 0; i < count; i++) {
    html += `
      <tr>
        <td><div class="skeleton-shimmer sk-cell" style="width: 140px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 80px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 75px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 80px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 65px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 110px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 170px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 50px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 80px;"></div></td>
      </tr>
    `;
  }
  tbody.innerHTML = html;
}

// 4. FILTERING & SORTING
function setQualityTabFilter(tab) {
  qualityState.tabFilter = tab;
  ['all', 'elite', 'breakout', 'pullback'].forEach(t => {
    const btn = document.getElementById(`qs-tab-${t}`);
    if (btn) {
      if (t === tab.toLowerCase()) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    }
  });
  applyQualityFilters();
}

function handleQualitySectorFilter(val) {
  qualityState.sectorFilter = val;
  applyQualityFilters();
}

function resetQualityFilters() {
  qualityState.tabFilter = 'ALL';
  qualityState.sectorFilter = 'ALL';
  qualityState.searchQuery = '';

  const searchInput = document.getElementById('qs-search-input');
  if (searchInput) searchInput.value = '';

  const sectorSelect = document.getElementById('qs-sector-filter');
  if (sectorSelect) sectorSelect.value = 'ALL';

  ['all', 'elite', 'breakout', 'pullback'].forEach(t => {
    const btn = document.getElementById(`qs-tab-${t}`);
    if (btn) {
      if (t === 'all') btn.classList.add('active');
      else btn.classList.remove('active');
    }
  });

  applyQualityFilters();
}

function applyQualityFilters() {
  const searchInput = document.getElementById('qs-search-input');
  const sectorSelect = document.getElementById('qs-sector-filter');
  const resetBtn = document.getElementById('qs-reset-btn');

  qualityState.searchQuery = searchInput ? searchInput.value.trim().toUpperCase() : '';
  qualityState.sectorFilter = sectorSelect ? sectorSelect.value : 'ALL';

  // Toggle reset button visibility
  const isFiltered = qualityState.tabFilter !== 'ALL' || qualityState.sectorFilter !== 'ALL' || qualityState.searchQuery !== '';
  if (resetBtn) {
    if (isFiltered) resetBtn.classList.remove('hidden');
    else resetBtn.classList.add('hidden');
  }

  qualityState.filteredResults = qualityState.allResults.filter(item => {
    // Tab Filter
    if (qualityState.tabFilter === 'ELITE' && item.grade !== 'Elite') return false;
    if (qualityState.tabFilter === 'BREAKOUT' && !(item.setup_type || '').includes('Breakout')) return false;
    if (qualityState.tabFilter === 'PULLBACK' && !(item.setup_type || '').includes('Pullback')) return false;

    // Sector Filter
    if (qualityState.sectorFilter !== 'ALL' && item.sector !== qualityState.sectorFilter) return false;

    // Search Query
    if (qualityState.searchQuery) {
      const matchTicker = (item.ticker || '').toUpperCase().includes(qualityState.searchQuery);
      const matchName = (item.name || '').toUpperCase().includes(qualityState.searchQuery);
      if (!matchTicker && !matchName) return false;
    }

    return true;
  });

  // Sort
  qualityState.filteredResults.sort((a, b) => {
    let valA = a[qualityState.sortCol];
    let valB = b[qualityState.sortCol];

    if (valA === undefined || valA === null) valA = 0;
    if (valB === undefined || valB === null) valB = 0;

    if (typeof valA === 'string') {
      return qualityState.sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return qualityState.sortAsc ? valA - valB : valB - valA;
  });

  renderQualityTable();
}

function sortQualityTable(col) {
  if (qualityState.sortCol === col) {
    qualityState.sortAsc = !qualityState.sortAsc;
  } else {
    qualityState.sortCol = col;
    qualityState.sortAsc = false;
  }

  // Update sort icons in header
  ['ticker', 'sector', 'price', 'score', 'grade', 'risk_reward'].forEach(c => {
    const icon = document.getElementById(`qs-sort-${c}`);
    if (icon) {
      if (c === col) {
        icon.textContent = qualityState.sortAsc ? '▲' : '▼';
        icon.style.opacity = '1';
      } else {
        icon.textContent = '↕';
        icon.style.opacity = '0.4';
      }
    }
  });

  applyQualityFilters();
}

// 5. TABLE RENDERER (ELEGANT 8-COLUMN PRO TERMINAL)
function renderQualityTable() {
  const tbody = document.getElementById('quality-table-body');
  const countBadge = document.getElementById('qs-table-count-badge');
  const emptyState = document.getElementById('qs-empty-state');

  if (countBadge) countBadge.textContent = `${qualityState.filteredResults.length} Setup Terkualifikasi`;

  if (!tbody) return;

  if (qualityState.filteredResults.length === 0) {
    tbody.innerHTML = '';
    if (emptyState) emptyState.classList.remove('hidden');
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');

  let rowsHtml = '';
  qualityState.filteredResults.forEach((item, idx) => {
    const isElite = item.grade === 'Elite';
    const gradeBadge = isElite
      ? `<span class="qs-grade-badge elite">👑 Elite</span>`
      : `<span class="qs-grade-badge strong">🟢 Strong</span>`;

    const isBreakout = (item.setup_type || '').includes('Breakout');
    const setupBadge = isBreakout
      ? `<span class="qs-setup-badge breakout">🚀 ${item.setup_type}</span>`
      : `<span class="qs-setup-badge pullback">⚡ ${item.setup_type}</span>`;

    const isBullish = item.supertrend === 'BULLISH';
    const stBadge = isBullish
      ? `<span class="st-badge bullish">BULLISH</span>`
      : `<span class="st-badge bearish">BEARISH</span>`;

    const changeVal = item.change_pct || 0;
    const changeClass = changeVal >= 0 ? 'pos' : 'neg';
    const changeSign = changeVal >= 0 ? '+' : '';

    const priceFormatted = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(item.price);
    const entryFormatted = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(item.entry);
    const slFormatted = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(item.stop_loss);
    const t1Formatted = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(item.target_1);

    const delay = Math.min(idx * 20, 400);

    rowsHtml += `
      <tr style="animation-delay: ${delay}ms" onclick="openQualityModal('${item.ticker}')">
        <!-- 1. Ticker & Nama -->
        <td>
          <div class="ticker-cell-wrapper">
            <button class="btn-star-pin ${(typeof watchlistState !== 'undefined' && watchlistState.pinnedTickers && watchlistState.pinnedTickers.has(item.ticker)) ? 'pinned' : ''}" data-ticker="${item.ticker}" onclick="togglePinStock('${item.ticker}', '${escapeQuotes(item.name)}', '${item.sector}', 'Quality Setup', event)" title="${(typeof watchlistState !== 'undefined' && watchlistState.pinnedTickers && watchlistState.pinnedTickers.has(item.ticker)) ? 'Hapus dari Watchlist' : 'Sematkan ke Watchlist'}">★</button>
            <div class="ticker-info-stack">
              <span class="ticker-cell">${item.ticker}</span>
            </div>
          </div>
          <div class="name-cell" title="${item.name}">${item.name}</div>
        </td>

        <!-- 2. Sektor -->
        <td><span class="sector-cell">${item.sector || 'General'}</span></td>

        <!-- 3. Harga & Change -->
        <td>
          <span class="price-cell">${priceFormatted}</span>
          <span class="price-change-sub ${changeClass}">${changeSign}${changeVal.toFixed(2)}%</span>
        </td>

        <!-- 4. Quality Score -->
        <td class="text-center">
          <div class="score-cell-wrap">
            <span class="font-bold mono ${isElite ? 'success' : ''}">${item.score}</span>
            <div class="score-bar-track">
              <div class="score-bar-fill ${isElite ? 'elite' : 'strong'}" style="width: ${Math.min(100, item.score)}%;"></div>
            </div>
          </div>
        </td>

        <!-- 5. Grade -->
        <td class="text-center">${gradeBadge}</td>

        <!-- 6. Setup & Supertrend -->
        <td class="text-center">
          <div class="table-setup-group">
            ${setupBadge}
            ${stBadge}
          </div>
        </td>

        <!-- 7. Trading Plan Taktis Capsule -->
        <td class="text-center">
          <div class="table-plan-capsule">
            <div class="table-plan-line">
              <span class="table-plan-lbl">Entry:</span>
              <span class="table-plan-val">${entryFormatted}</span>
            </div>
            <div class="table-plan-line">
              <span class="table-plan-lbl">SL:</span>
              <span class="table-plan-val danger">${slFormatted} (-${(item.stop_loss_pct || 0).toFixed(1)}%)</span>
            </div>
            <div class="table-plan-line">
              <span class="table-plan-lbl">TP1:</span>
              <span class="table-plan-val success">${t1Formatted}</span>
            </div>
          </div>
        </td>

        <!-- 8. Risk:Reward -->
        <td class="text-center mono font-bold">1 : ${(item.risk_reward || 0).toFixed(1)}</td>

        <!-- 9. Aksi Detail Bento -->
        <td class="text-center" onclick="event.stopPropagation()">
          <button class="btn-detail-bento" onclick="openQualityModal('${item.ticker}')" title="Buka Detail Bento Quality Setup">
            <span>💎</span> Detail
          </button>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rowsHtml;
}

// 6. BENTO MODAL CONTROLLER
function openQualityModal(ticker) {
  const stock = qualityState.allResults.find(r => r.ticker === ticker);
  if (!stock) return;

  qualityState.selectedStock = stock;
  const modal = document.getElementById('modal-quality-setup');
  if (!modal) return;

  // Header Info
  document.getElementById('qs-modal-ticker').textContent = stock.ticker;
  document.getElementById('qs-modal-name').textContent = stock.name || stock.ticker;
  document.getElementById('qs-modal-sector').textContent = stock.sector || 'General';
  document.getElementById('qs-modal-price').textContent = `Rp ${(stock.price || 0).toLocaleString('id-ID')}`;

  const changeEl = document.getElementById('qs-modal-change');
  const chg = stock.change_pct || 0;
  changeEl.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
  changeEl.className = `price-change-sub ${chg >= 0 ? 'pos' : 'neg'}`;

  // Badges
  const isElite = stock.grade === 'Elite';
  const gradeBadgeEl = document.getElementById('qs-modal-grade-badge');
  gradeBadgeEl.textContent = isElite ? '👑 ELITE' : '🟢 STRONG';
  gradeBadgeEl.className = `badge-status ${isElite ? 'ready' : 'forming'}`;

  const isBreakout = (stock.setup_type || '').includes('Breakout');
  const setupBadgeEl = document.getElementById('qs-modal-setup-badge');
  setupBadgeEl.textContent = (stock.setup_type || 'SWING SETUP').toUpperCase();
  setupBadgeEl.className = `qs-setup-badge ${isBreakout ? 'breakout' : 'pullback'}`;

  // Trade Execution Plan (Bento 1)
  document.getElementById('qs-modal-entry').textContent = `Rp ${(stock.entry || 0).toLocaleString('id-ID')}`;
  document.getElementById('qs-modal-entry-note').textContent = isBreakout ? 'Nearest Resistance (Breakout Trigger)' : 'Dynamic Support / EMA20 (Pullback Retest)';
  document.getElementById('qs-modal-sl').textContent = `Rp ${(stock.stop_loss || 0).toLocaleString('id-ID')}`;
  document.getElementById('qs-modal-sl-pct').textContent = `-${(stock.stop_loss_pct || 0).toFixed(1)}% (1.5x ATR Protection)`;
  document.getElementById('qs-modal-t1').textContent = `Rp ${(stock.target_1 || 0).toLocaleString('id-ID')}`;
  document.getElementById('qs-modal-t2').textContent = `Rp ${(stock.target_2 || 0).toLocaleString('id-ID')}`;
  document.getElementById('qs-modal-rr-badge').textContent = `Risk:Reward 1 : ${(stock.risk_reward || 0).toFixed(1)}`;

  // Score Breakdown (Bento 2)
  document.getElementById('qs-modal-score').textContent = stock.score;
  const b = stock.score_breakdown || {};
  document.getElementById('qs-modal-p-trend').textContent = `${(b.ema_trend || 0) + (b.rsi || 0) + (b.macd || 0) + (b.relative_performance || 0)} pt`;
  document.getElementById('qs-modal-p-volume').textContent = `${(b.volume_confirmation || 0) + (b.adx || 0)} pt`;
  document.getElementById('qs-modal-p-volatility').textContent = `${b.volatility_control || 0} pt`;
  document.getElementById('qs-modal-p-overlay').textContent = `${(b.drawdown_stability || 0) + (b.supertrend_overlay || 0)} pt`;

  const sigList = document.getElementById('qs-modal-signals');
  if (stock.signals && stock.signals.length > 0) {
    sigList.innerHTML = stock.signals.map(s => `<li>✓ ${s}</li>`).join('');
  } else {
    sigList.innerHTML = '<li>✓ Struktur tren momentum valid</li>';
  }

  // Fibonacci Levels (Bento 3)
  const fib = stock.fibonacci || {};
  document.getElementById('qs-modal-fib-trend').textContent = (fib.trend || 'UPTREND').toUpperCase();
  document.getElementById('qs-fib-236').textContent = fib.fib_236 ? `Rp ${fib.fib_236.toLocaleString('id-ID')}` : '—';
  document.getElementById('qs-fib-382').textContent = fib.fib_382 ? `Rp ${fib.fib_382.toLocaleString('id-ID')}` : '—';
  document.getElementById('qs-fib-500').textContent = fib.fib_500 ? `Rp ${fib.fib_500.toLocaleString('id-ID')}` : '—';
  document.getElementById('qs-fib-618').textContent = fib.golden_pocket ? `Rp ${fib.golden_pocket.toLocaleString('id-ID')}` : '—';
  document.getElementById('qs-fib-786').textContent = fib.fib_786 ? `Rp ${fib.fib_786.toLocaleString('id-ID')}` : '—';
  document.getElementById('qs-ext-1272').textContent = fib.ext_1272 ? `Rp ${fib.ext_1272.toLocaleString('id-ID')}` : '—';
  document.getElementById('qs-ext-1618').textContent = fib.ext_1618 ? `Rp ${fib.ext_1618.toLocaleString('id-ID')}` : '—';
  document.getElementById('qs-ext-2618').textContent = fib.ext_2618 ? `Rp ${fib.ext_2618.toLocaleString('id-ID')}` : '—';

  // Candle & Supertrend (Bento 4)
  const isStBull = stock.supertrend === 'BULLISH';
  const stBadge = document.getElementById('qs-modal-st-badge');
  stBadge.textContent = stock.supertrend;
  stBadge.className = `st-badge ${isStBull ? 'bullish' : 'bearish'}`;

  const str = stock.structure || {};
  document.getElementById('qs-struct-candle').textContent = `${str.candle_type || 'Normal'} (${str.strength || 'Moderate'})`;
  document.getElementById('qs-struct-body').textContent = `${str.body_pct || 0}% total range`;
  document.getElementById('qs-struct-upper-wick').textContent = `${str.upper_wick_pct || 0}% wick`;
  document.getElementById('qs-struct-lower-wick').textContent = `${str.lower_wick_pct || 0}% rejection`;

  // Display standard modal with backdrop blur
  modal.classList.remove('hidden');
}

function closeQualityModal() {
  const modal = document.getElementById('modal-quality-setup');
  if (modal) modal.classList.add('hidden');
}

function closeQualityModalOnBackdrop(event) {
  if (event.target.id === 'modal-quality-setup' || event.target.classList.contains('modal')) {
    closeQualityModal();
  }
}

// Seamless transition to IDX Edge PRO Modal
function openBandarFromQuality() {
  if (!qualityState.selectedStock) return;
  const ticker = qualityState.selectedStock.ticker;
  closeQualityModal();
  if (typeof openStockDetailModal === 'function') {
    openStockDetailModal(ticker);
  }
}

function openTradingViewFromQuality() {
  if (!qualityState.selectedStock) return;
  const ticker = qualityState.selectedStock.ticker;
  window.open(`https://www.tradingview.com/chart/?symbol=IDX:${ticker}`, '_blank');
}

function openSizingFromQuality() {
  if (!qualityState.selectedStock) return;
  const s = qualityState.selectedStock;
  closeQualityModal();
  if (typeof openPositionCalculator === 'function') {
    openPositionCalculator({
      ticker: s.ticker,
      name: s.name,
      sector: s.sector,
      entry: s.entry,
      sl: s.stop_loss,
      t1: s.target_1,
      t2: s.target_2
    });
  }
}

function togglePinFromQuality() {
  if (!qualityState.selectedStock) return;
  const s = qualityState.selectedStock;
  if (typeof togglePinStock === 'function') {
    togglePinStock(s.ticker, s.name, s.sector, 'Quality Setup');
  }
}

// 7. SCAN TRIGGER VIA UI
async function triggerQualityScanUI() {
  if (typeof showToast === 'function') {
    showToast('Memulai scan Quality Setup 941 saham IDX...', 'info');
  }

  try {
    const res = await fetch('/api/scan/quality-setup', { method: 'POST' });
    const json = await res.json();

    if (res.status === 409) {
      if (typeof showToast === 'function') showToast('Quality scan sedang berjalan...', 'warning');
      pollQualityScanStatus();
      return;
    }

    if (json.status === 'started') {
      if (typeof showToast === 'function') showToast('Scan 941 emiten dimulai di background!', 'success');
      pollQualityScanStatus();
    }
  } catch (err) {
    console.error('Trigger scan error:', err);
    if (typeof showToast === 'function') showToast('Gagal memulai scan Quality Setup', 'error');
  }
}

function pollQualityScanStatus() {
  const interval = setInterval(async () => {
    try {
      const res = await fetch('/api/status/quality-setup');
      const data = await res.json();
      if (!data.is_scanning) {
        clearInterval(interval);
        if (typeof showToast === 'function') showToast('✅ Quality Setup scan selesai!', 'success');
        loadQualityResults();
      }
    } catch (e) {
      clearInterval(interval);
    }
  }, 2000);
}

// 8. CSV EXPORT
function exportQualityCSV() {
  if (!qualityState.filteredResults || qualityState.filteredResults.length === 0) {
    if (typeof showToast === 'function') showToast('Tidak ada data untuk diekspor', 'warning');
    return;
  }

  const headers = ['Ticker', 'Nama Perusahaan', 'Sektor', 'Harga', 'Score', 'Grade', 'Setup Type', 'Supertrend', 'Entry', 'Stop Loss', 'SL %', 'Target 1', 'Target 2', 'Risk Reward'];
  const rows = qualityState.filteredResults.map(r => [
    r.ticker,
    `"${(r.name || '').replace(/"/g, '""')}"`,
    `"${(r.sector || '').replace(/"/g, '""')}"`,
    r.price,
    r.score,
    r.grade,
    `"${r.setup_type || ''}"`,
    r.supertrend,
    r.entry,
    r.stop_loss,
    r.stop_loss_pct,
    r.target_1,
    r.target_2,
    r.risk_reward
  ]);

  const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `Tirexxz_Quality_Setup_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// ESC Key listener to close modal
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeQualityModal();
  }
});
