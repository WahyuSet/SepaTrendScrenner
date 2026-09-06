// ============================================================================
// SEPA TREND SCREENER MODULE (Mark Minervini 8-Criteria Stage 2)
// ============================================================================

const state = {
  allResults: [],
  filteredResults: [],
  minScore: 6,
  sectorFilter: 'ALL',
  searchQuery: '',
  tabFilter: 'ALL', // 'ALL' | 'CONFIRMED' | 'WATCHLIST' | 'VCP_READY'
  sortCol: 'total_score',
  sortAsc: false
};

async function loadCachedResults() {
  renderSkeleton(8);
  try {
    const res = await fetch('/api/results');
    const json = await res.json();

    if (json.status === 'success' && json.data) {
      const { timestamp, stats, results } = json.data;
      state.allResults = results || [];
      renderStatsCards(stats, timestamp);
      populateSectorDropdown(state.allResults);
      updateTabCounters(state.allResults);
      applyFilters();
    } else {
      renderStatsCards(null, null);
      state.allResults = [];
      applyFilters();
    }
  } catch (err) {
    console.error('Failed to load cached results:', err);
    state.allResults = [];
    applyFilters();
  }
}

function populateSectorDropdown(data) {
  const select = document.getElementById('sepa-sector-filter');
  if (!select) return;

  const currentVal = select.value;
  const sectors = [...new Set(data.map(d => d.sector).filter(Boolean))].sort();

  let opts = '<option value="ALL">Semua Sektor (All)</option>';
  sectors.forEach(sec => {
    opts += `<option value="${sec}">${sec}</option>`;
  });
  select.innerHTML = opts;
  if (sectors.includes(currentVal)) {
    select.value = currentVal;
  }
}

function updateTabCounters(data) {
  const cntAll = document.getElementById('cnt-sepa-all');
  const cntConf = document.getElementById('cnt-sepa-confirmed');
  const cntWatch = document.getElementById('cnt-sepa-watchlist');
  const cntVcp = document.getElementById('cnt-sepa-vcp');

  if (cntAll) cntAll.textContent = data.length;
  if (cntConf) cntConf.textContent = data.filter(d => d.status === 'CONFIRMED').length;
  if (cntWatch) cntWatch.textContent = data.filter(d => d.status === 'WATCHLIST').length;
  if (cntVcp) cntVcp.textContent = data.filter(d => d.is_sepa_vcp_ready).length;
}

function handleScorePill(val) {
  state.minScore = parseInt(val, 10);
  
  const pills = document.querySelectorAll('#sepa-score-pills .score-pill-btn');
  pills.forEach(p => {
    const scoreVal = parseInt(p.getAttribute('data-score'), 10);
    if (scoreVal === state.minScore) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  });

  applyFilters();
}

function handleSectorFilter(val) {
  state.sectorFilter = val;
  applyFilters();
}

function resetSepaFilters() {
  state.minScore = 6;
  state.sectorFilter = 'ALL';
  state.tabFilter = 'ALL';

  // Reset UI elements
  const select = document.getElementById('sepa-sector-filter');
  if (select) select.value = 'ALL';

  const pills = document.querySelectorAll('#sepa-score-pills .score-pill-btn');
  pills.forEach(p => {
    const scoreVal = parseInt(p.getAttribute('data-score'), 10);
    p.classList.toggle('active', scoreVal === 6);
  });

  ['tab-all', 'tab-confirmed', 'tab-watchlist', 'tab-vcp'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', id === 'tab-all');
  });

  applyFilters();
}

function setTabFilter(tab) {
  state.tabFilter = tab;
  ['tab-all', 'tab-confirmed', 'tab-watchlist', 'tab-vcp'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });

  if (tab === 'ALL') document.getElementById('tab-all')?.classList.add('active');
  if (tab === 'CONFIRMED') document.getElementById('tab-confirmed')?.classList.add('active');
  if (tab === 'WATCHLIST') document.getElementById('tab-watchlist')?.classList.add('active');
  if (tab === 'VCP_READY') document.getElementById('tab-vcp')?.classList.add('active');

  applyFilters();
}

function sortTable(column) {
  if (state.sortCol === column) {
    state.sortAsc = !state.sortAsc;
  } else {
    state.sortCol = column;
    state.sortAsc = (column === 'ticker' || column === 'name' || column === 'sector');
  }

  // Update header indicator icons
  const icons = document.querySelectorAll('#screener-table .sort-icon');
  icons.forEach(ic => ic.textContent = '↕');
  const targetIcon = document.getElementById(`sort-${column}`);
  if (targetIcon) {
    targetIcon.textContent = state.sortAsc ? '▲' : '▼';
  }

  applyFilters();
}

function applyFilters() {
  let list = [...state.allResults];

  // 1. Min Score Filter
  list = list.filter(item => item.total_score >= state.minScore);

  // 2. Tab Filter
  if (state.tabFilter === 'CONFIRMED') {
    list = list.filter(item => item.status === 'CONFIRMED');
  } else if (state.tabFilter === 'WATCHLIST') {
    list = list.filter(item => item.status === 'WATCHLIST');
  } else if (state.tabFilter === 'VCP_READY') {
    list = list.filter(item => item.is_sepa_vcp_ready);
  }

  // 3. Sector Filter
  if (state.sectorFilter !== 'ALL') {
    list = list.filter(item => item.sector === state.sectorFilter);
  }

  // Update Reset button visibility
  const resetBtn = document.getElementById('sepa-reset-btn');
  const isCustomFiltered = (state.minScore !== 6 || state.sectorFilter !== 'ALL' || state.tabFilter !== 'ALL');
  if (resetBtn) {
    resetBtn.classList.toggle('hidden', !isCustomFiltered);
  }

  // Update Table Count Badge
  const countBadge = document.getElementById('table-count-badge');
  if (countBadge) {
    countBadge.textContent = `${list.length} Saham Terkualifikasi`;
  }

  // 3. Search Query Filter
  if (state.searchQuery) {
    list = list.filter(item => 
      item.ticker.toLowerCase().includes(state.searchQuery) ||
      item.name.toLowerCase().includes(state.searchQuery) ||
      item.sector.toLowerCase().includes(state.searchQuery)
    );
  }

  // 4. Sorting
  list.sort((a, b) => {
    let valA = a[state.sortCol];
    let valB = b[state.sortCol];

    if (typeof valA === 'string') {
      return state.sortAsc 
        ? valA.localeCompare(valB) 
        : valB.localeCompare(valA);
    }

    valA = valA !== undefined ? valA : 0;
    valB = valB !== undefined ? valB : 0;

    return state.sortAsc ? valA - valB : valB - valA;
  });

  state.filteredResults = list;
  renderTable(list);
}

function renderStatsCards(stats, timestamp) {
  const statScanned = document.getElementById('stat-scanned');
  const statConfirmed = document.getElementById('stat-confirmed');
  const statWatchlist = document.getElementById('stat-watchlist');
  const statLastTime = document.getElementById('stat-last-time');
  const badgeSepa = document.getElementById('badge-sepa');

  if (stats) {
    if (statScanned) statScanned.textContent = stats.total_scanned || 0;
    if (statConfirmed) statConfirmed.textContent = stats.confirmed_count || 0;
    if (statWatchlist) statWatchlist.textContent = stats.watchlist_count || 0;
    if (badgeSepa) {
      const qualified = (stats.confirmed_count || 0) + (stats.watchlist_count || 0);
      badgeSepa.textContent = qualified > 0 ? qualified : '0';
    }
  } else {
    if (badgeSepa) badgeSepa.textContent = '—';
  }

  const timeText = timestamp || 'Belum pernah scan';
  if (statLastTime) statLastTime.textContent = timeText;
  if (typeof updateSidebarLastScan === 'function') {
    updateSidebarLastScan(timeText);
  }
}

function renderSkeleton(rowCount = 8) {
  const tbody = document.getElementById('table-body');
  const emptyState = document.getElementById('empty-state');
  if (emptyState) emptyState.classList.add('hidden');
  if (!tbody) return;

  let html = '';
  for (let i = 0; i < rowCount; i++) {
    html += `
      <tr>
        <td><div class="skeleton-shimmer sk-cell" style="width: 50px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 140px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 90px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 70px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 65px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 95px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 150px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 45px;"></div></td>
        <td class="text-right"><div class="skeleton-shimmer sk-cell" style="width: 60px;"></div></td>
        <td class="text-right"><div class="skeleton-shimmer sk-cell" style="width: 60px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 80px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 60px; height: 26px; border-radius: 6px;"></div></td>
      </tr>
    `;
  }
  tbody.innerHTML = html;
}

function renderTable(data) {
  const tbody = document.getElementById('table-body');
  const countBadge = document.getElementById('table-count-badge');
  const emptyState = document.getElementById('empty-state');

  if (countBadge) {
    countBadge.textContent = `${data.length} Saham Terkualifikasi`;
  }

  if (!tbody) return;

  if (data.length === 0) {
    tbody.innerHTML = '';
    if (emptyState) emptyState.classList.remove('hidden');
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');

  let rowsHtml = '';
  data.forEach((stock, idx) => {
    const scoreClass = stock.total_score === 8 ? 'score-8' : (stock.total_score >= 6 ? 'score-6-7' : 'score-low');
    const scorePct = Math.round((stock.total_score / 8) * 100);

    const statusClass = stock.status === 'CONFIRMED' ? 'confirmed' : 'watchlist';
    const statusIcon = stock.status === 'CONFIRMED' ? '✓' : '⭐';

    const rsClass = stock.rs_score >= 90 ? 'rs-high' : (stock.rs_score >= 70 ? 'rs-high' : (stock.rs_score >= 50 ? 'rs-mid' : 'rs-low'));

    const changeClass = stock.pct_change_1d >= 0 ? 'pos' : 'neg';
    const changeSign = stock.pct_change_1d >= 0 ? '+' : '';
    const changeHtml = stock.pct_change_1d !== 0 
      ? `<span class="price-change-sub ${changeClass}">${changeSign}${stock.pct_change_1d}%</span>`
      : '';

    const priceFormatted = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(stock.price);
    const delay = Math.min(idx * 25, 500);

    let critPillsHtml = '<div class="crit-pills-wrap">';
    if (stock.criteria) {
      const keys = ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8'];
      keys.forEach((k, kIdx) => {
        const num = kIdx + 1;
        const crit = stock.criteria[k];
        const isPass = crit ? crit.pass : false;
        const title = crit ? crit.title : `Kriteria ${num}`;
        const val = crit ? crit.val : '';
        const statusText = isPass ? 'PASS' : 'FAIL';
        const tooltip = `C${num}: ${title} (${val}) — ${statusText}`;
        const pillClass = isPass ? 'pass' : 'fail';
        critPillsHtml += `<span class="crit-pill ${pillClass}" title="${tooltip}">${num}</span>`;
      });
    }
    critPillsHtml += '</div>';

    rowsHtml += `
      <tr style="animation-delay: ${delay}ms" onclick="openCriteriaModal('${stock.ticker}')">
        <td>
          <div class="ticker-cell-wrapper">
            <button class="btn-star-pin ${(typeof watchlistState !== 'undefined' && watchlistState.pinnedTickers && watchlistState.pinnedTickers.has(stock.ticker)) ? 'pinned' : ''}" data-ticker="${stock.ticker}" onclick="togglePinStock('${stock.ticker}', '${(stock.name || '').replace(/'/g, "\\'")}', '${stock.sector}', 'SEPA Trend', event)" title="${(typeof watchlistState !== 'undefined' && watchlistState.pinnedTickers && watchlistState.pinnedTickers.has(stock.ticker)) ? 'Hapus dari Watchlist' : 'Sematkan ke Watchlist'}">★</button>
            <div class="ticker-info-stack">
              <span class="ticker-cell">${stock.ticker}</span>
              ${stock.is_sepa_vcp_ready ? `<span class="badge-sepa-vcp" title="Setup Emas: SEPA Confirmed & VCP Ready to Breakout!">⭐ VCP READY</span>` : ''}
            </div>
          </div>
        </td>
        <td><div class="name-cell" title="${stock.name}">${stock.name}</div></td>
        <td><span class="sector-cell">${stock.sector}</span></td>
        <td>
          <span class="price-cell">${priceFormatted}</span>
          ${changeHtml}
        </td>
        <td class="text-center">
          <div class="score-cell-wrap">
            <div class="score-bar-track">
              <div class="score-bar-fill ${scoreClass}" style="width: ${scorePct}%;"></div>
            </div>
            <span class="score-text ${scoreClass}">${stock.total_score}/8</span>
          </div>
        </td>
        <td class="text-center">
          <span class="badge-status ${statusClass}">${statusIcon} ${stock.status}</span>
        </td>
        <td class="text-center" onclick="event.stopPropagation()">
          ${critPillsHtml}
        </td>
        <td class="text-center">
          <span class="rs-badge ${rsClass}">${stock.rs_score.toFixed(0)}</span>
        </td>
        <td class="text-right" style="color: ${stock.dist_low_pct >= 25 ? 'var(--status-confirmed-text)' : 'var(--text-secondary)'}; font-family: var(--font-mono); font-weight: 700;">
          +${stock.dist_low_pct.toFixed(1)}%
        </td>
        <td class="text-right" style="color: ${stock.dist_high_pct <= 25 ? 'var(--status-confirmed-text)' : 'var(--status-fail-text)'}; font-family: var(--font-mono); font-weight: 700;">
          -${stock.dist_high_pct.toFixed(1)}%
        </td>
        <td class="text-center" onclick="event.stopPropagation()">
          <button class="btn-cek-bandar" onclick="checkBandarInline('${stock.ticker}', this, event)" title="Ambil status akumulasi broker dari IDX Edge PRO API">
            🔍 Cek Bandar
          </button>
        </td>
        <td class="text-center" onclick="event.stopPropagation()">
          <button class="btn-table-detail" onclick="openStockDetailModal('${stock.ticker}', {name: '${(stock.name || '').replace(/'/g, "\\'")}', sector: '${stock.sector}', price: ${stock.price}})" title="Buka Detail Analisis Komprehensif">
            📊 Detail
          </button>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rowsHtml;
}

function openCriteriaModal(ticker) {
  const stock = state.allResults.find(s => s.ticker === ticker);
  if (!stock) return;

  const modal = document.getElementById('criteria-modal');
  const tickerEl = document.getElementById('modal-ticker');
  const nameEl = document.getElementById('modal-name');
  const title = document.getElementById('modal-ticker-title');
  const price = document.getElementById('modal-price');
  const score = document.getElementById('modal-score');
  const status = document.getElementById('modal-status');
  const rs = document.getElementById('modal-rs');
  const container = document.getElementById('modal-criteria-container');
  const tvLink = document.getElementById('modal-tv-link');

  if (tickerEl) tickerEl.textContent = stock.ticker;
  if (nameEl) nameEl.textContent = stock.name;
  if (title) title.textContent = `${stock.ticker} — ${stock.name}`;
  if (price) price.textContent = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(stock.price);
  if (score) score.textContent = `${stock.total_score} / 8 Kriteria`;
  if (status) {
    status.textContent = stock.status;
    status.style.color = stock.status === 'CONFIRMED' ? 'var(--status-confirmed-text)' : 'var(--status-watchlist-text)';
  }
  if (rs) {
    const perfSign = (stock.stock_perf || 0) >= 0 ? '+' : '';
    rs.textContent = `${(stock.rs_score || 0).toFixed(0)} / 100 (${perfSign}${stock.stock_perf || 0}% vs IHSG)`;
  }
  if (tvLink) tvLink.href = stock.tradingview_url;

  if (container && stock.criteria) {
    let listHtml = '';
    const keys = ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8'];
    
    keys.forEach((k, idx) => {
      const crit = stock.criteria[k];
      if (!crit) return;
      const isPass = crit.pass;
      const icon = isPass ? '✓ PASS' : '✗ FAIL';
      const itemClass = isPass ? 'pass' : 'fail';
      const iconClass = isPass ? 'pass' : 'fail';

      listHtml += `
        <div class="criteria-item ${itemClass}">
          <div class="crit-left">
            <span class="crit-icon ${iconClass}">${icon}</span>
            <span class="crit-title">C${idx + 1}: ${crit.title}</span>
          </div>
          <span class="crit-val">${crit.val}</span>
        </div>
      `;
    });

    container.innerHTML = listHtml;
  }

  if (modal) modal.classList.remove('hidden');
}

function closeModal() {
  const modal = document.getElementById('criteria-modal');
  if (modal) modal.classList.add('hidden');
}

function closeModalOnBackdrop(event) {
  if (event.target.id === 'criteria-modal') {
    closeModal();
  }
}

function resetSepaFilters() {
  state.minScore = 6;
  state.searchQuery = '';
  state.tabFilter = 'ALL';

  const slider = document.getElementById('score-slider');
  if (slider) slider.value = 6;
  const sliderVal = document.getElementById('score-slider-val');
  if (sliderVal) sliderVal.textContent = '≥ 6';

  ['tab-all', 'tab-confirmed', 'tab-watchlist'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });
  const allTab = document.getElementById('tab-all');
  if (allTab) allTab.classList.add('active');

  applyFilters();
  showToast('Filter SEPA telah direset ke default.');
}
