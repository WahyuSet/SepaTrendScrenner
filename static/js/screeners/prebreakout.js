// ============================================================================
// PRE-BREAKOUT SETUP SCREENER MODULE
// ============================================================================

const prebreakoutState = {
  allResults: [],
  filteredResults: [],
  minScore: 5,
  tabFilter: 'ALL', // 'ALL' | 'READY' | 'FORMING'
  searchQuery: '',
  sortCol: 'total_score',
  sortAsc: false
};

async function loadPreBreakoutResults() {
  renderPreBreakoutSkeleton(6);
  try {
    const res = await fetch('/api/pre-breakout');
    const json = await res.json();

    if (json.status === 'success' && json.data) {
      const { timestamp, stats, results } = json.data;
      prebreakoutState.allResults = results || [];
      renderPreBreakoutStatsCards(stats, timestamp);
      applyPreBreakoutFilters();
    } else {
      renderPreBreakoutStatsCards(null, null);
      prebreakoutState.allResults = [];
      applyPreBreakoutFilters();
    }
  } catch (err) {
    console.error('Failed to load Pre-Breakout results:', err);
    prebreakoutState.allResults = [];
    applyPreBreakoutFilters();
  }
}

function renderPreBreakoutStatsCards(stats, timestamp) {
  const statTotal = document.getElementById('pb-stat-total');
  const statReady = document.getElementById('pb-stat-ready');
  const statForming = document.getElementById('pb-stat-forming');
  const statTime = document.getElementById('pb-stat-last-time');
  const badgeNav = document.getElementById('badge-prebreakout');

  const count = stats ? (stats.total_setups || 0) : (prebreakoutState.allResults.length || 0);

  if (statTotal) statTotal.textContent = count;
  if (statReady) statReady.textContent = stats ? (stats.ready_count || 0) : 0;
  if (statForming) statForming.textContent = stats ? (stats.forming_count || 0) : 0;

  const timeText = timestamp || 'Belum pernah scan';
  if (statTime) statTime.textContent = timeText;
  if (badgeNav) badgeNav.textContent = count > 0 ? count : (stats ? '0' : '—');
}

function renderPreBreakoutSkeleton(count = 6) {
  const tbody = document.getElementById('pb-table-body');
  if (!tbody) return;

  let skeletonHtml = '';
  for (let i = 0; i < count; i++) {
    skeletonHtml += `
      <tr>
        <td><div class="skeleton-shimmer sk-cell" style="width: 50px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 130px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 90px;"></div></td>
        <td class="text-right"><div class="skeleton-shimmer sk-cell" style="width: 70px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 50px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 80px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 120px;"></div></td>
        <td class="text-right"><div class="skeleton-shimmer sk-cell" style="width: 60px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 50px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 45px;"></div></td>
        <td class="text-right"><div class="skeleton-shimmer sk-cell" style="width: 70px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 80px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 60px; height: 26px; border-radius: 6px;"></div></td>
      </tr>
    `;
  }
  tbody.innerHTML = skeletonHtml;
}

function handlePbScoreSlider(val) {
  prebreakoutState.minScore = parseInt(val, 10);
  const badge = document.getElementById('pb-score-slider-val');
  if (badge) badge.textContent = `≥ ${prebreakoutState.minScore}`;
  applyPreBreakoutFilters();
}

function setPbTabFilter(tab) {
  prebreakoutState.tabFilter = tab;

  ['pb-tab-all', 'pb-tab-ready', 'pb-tab-forming'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });

  if (tab === 'ALL') document.getElementById('pb-tab-all')?.classList.add('active');
  if (tab === 'READY') document.getElementById('pb-tab-ready')?.classList.add('active');
  if (tab === 'FORMING') document.getElementById('pb-tab-forming')?.classList.add('active');

  applyPreBreakoutFilters();
}

function sortPbTable(col) {
  if (prebreakoutState.sortCol === col) {
    prebreakoutState.sortAsc = !prebreakoutState.sortAsc;
  } else {
    prebreakoutState.sortCol = col;
    prebreakoutState.sortAsc = (col === 'ticker' || col === 'name' || col === 'sector' || col === 'dist_res_pct');
  }

  const icons = document.querySelectorAll('#pb-table .sort-icon');
  icons.forEach(ic => ic.textContent = '↕');
  const targetIcon = document.getElementById(`pb-sort-${col}`);
  if (targetIcon) {
    targetIcon.textContent = prebreakoutState.sortAsc ? '▲' : '▼';
  }

  applyPreBreakoutFilters();
}

function applyPreBreakoutFilters() {
  let list = [...prebreakoutState.allResults];

  // 1. Min Score Filter
  list = list.filter(item => item.total_score >= prebreakoutState.minScore);

  // 2. Tab Filter
  if (prebreakoutState.tabFilter === 'READY') {
    list = list.filter(item => item.status === 'READY');
  } else if (prebreakoutState.tabFilter === 'FORMING') {
    list = list.filter(item => item.status === 'FORMING');
  }

  // 3. Search Query Filter
  if (prebreakoutState.searchQuery) {
    list = list.filter(item =>
      item.ticker.toLowerCase().includes(prebreakoutState.searchQuery) ||
      item.name.toLowerCase().includes(prebreakoutState.searchQuery) ||
      item.sector.toLowerCase().includes(prebreakoutState.searchQuery)
    );
  }

  // 4. Sorting
  list.sort((a, b) => {
    let valA = a[prebreakoutState.sortCol];
    let valB = b[prebreakoutState.sortCol];

    if (typeof valA === 'string') {
      return prebreakoutState.sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return prebreakoutState.sortAsc ? valA - valB : valB - valA;
  });

  prebreakoutState.filteredResults = list;
  renderPreBreakoutTable(list);
}

function renderPreBreakoutTable(data) {
  const tbody = document.getElementById('pb-table-body');
  const countBadge = document.getElementById('pb-table-count-badge');
  const emptyState = document.getElementById('pb-empty-state');

  if (countBadge) {
    countBadge.textContent = `${data.length} Setup Terkualifikasi`;
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
    const isReady = stock.status === 'READY';
    const statusClass = isReady ? 'ready' : 'forming';
    const statusIcon = isReady ? '⚡' : '⭐';

    const scoreClass = stock.total_score === 7 ? 'score-8' : 'score-6-7';
    const scorePct = Math.round((stock.total_score / 7) * 100);

    const changeClass = stock.pct_change_1d >= 0 ? 'pos' : 'neg';
    const changeSign = stock.pct_change_1d >= 0 ? '+' : '';
    const changeHtml = stock.pct_change_1d !== 0
      ? `<span class="price-change-sub ${changeClass}">${changeSign}${stock.pct_change_1d}%</span>`
      : '';

    const priceFormatted = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(stock.price);
    const volumeFormatted = new Intl.NumberFormat('id-ID').format(stock.volume);

    const delay = Math.min(idx * 25, 500);

    // Mini pills for K1-K7
    let critPillsHtml = '<div class="crit-pills-wrap">';
    if (stock.criteria) {
      const keys = ['k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7'];
      keys.forEach((k, kIdx) => {
        const num = kIdx + 1;
        const crit = stock.criteria[k];
        const isPass = crit ? crit.pass : false;
        const title = crit ? crit.title : `Kriteria ${num}`;
        const val = crit ? crit.val : '';
        const statusText = isPass ? 'PASS' : 'FAIL';
        const tooltip = `K${num}: ${title} (${val}) — ${statusText}`;
        const pillClass = isPass ? 'pass' : 'fail';
        critPillsHtml += `<span class="crit-pill ${pillClass}" title="${tooltip}">${num}</span>`;
      });
    }
    critPillsHtml += '</div>';

    const isSurge = stock.vol_type === 'SURGE' || stock.rvol >= 1.2;
    const isDryUp = stock.vol_type === 'DRY_UP' || stock.rvol <= 0.75;
    const rvolClass = isSurge ? 'surge' : (isDryUp ? 'dryup' : 'normal');
    const rvolBadgeText = isSurge 
      ? `${stock.rvol.toFixed(2)}x ⚡` 
      : (isDryUp ? `${stock.rvol.toFixed(2)}x 💧` : `${stock.rvol.toFixed(2)}x`);
    const rvolTooltip = isSurge 
      ? 'Demand Surge (RVOL >= 1.2x)' 
      : (isDryUp ? 'Supply Dry-Up / VCP (RVOL <= 0.75x)' : 'Normal Volume');

    const distClass = stock.dist_res_pct < 3.0 ? 'close' : 'normal';

    rowsHtml += `
      <tr style="animation-delay: ${delay}ms" onclick="openPreBreakoutModal('${stock.ticker}')">
        <td><span class="ticker-cell">${stock.ticker}</span></td>
        <td><div class="name-cell" title="${stock.name}">${stock.name}</div></td>
        <td><span class="sector-cell">${stock.sector}</span></td>
        <td class="text-right">
          <span class="price-cell">${priceFormatted}</span>
          ${changeHtml}
        </td>
        <td class="text-center">
          <div class="score-cell-wrap">
            <div class="score-bar-track">
              <div class="score-bar-fill ${scoreClass}" style="width: ${scorePct}%;"></div>
            </div>
            <span class="score-text ${scoreClass}">${stock.total_score}/7</span>
          </div>
        </td>
        <td class="text-center">
          <span class="badge-status ${statusClass}">${statusIcon} ${stock.status_label}</span>
        </td>
        <td class="text-center" onclick="event.stopPropagation()">
          ${critPillsHtml}
        </td>
        <td class="text-right">
          <span class="dist-res-badge ${distClass}">-${stock.dist_res_pct}%</span>
          <div style="font-size: 10px; color: var(--text-muted); font-family: var(--font-mono);">H50: ${stock.high_50d.toLocaleString('id-ID')}</div>
        </td>
        <td class="text-center">
          <span class="rvol-badge ${rvolClass}" title="${rvolTooltip}">${rvolBadgeText}</span>
        </td>
        <td class="text-center">
          <span class="rsi-pill neutral">${stock.rsi.toFixed(1)}</span>
        </td>
        <td class="text-right" style="font-family: var(--font-mono); font-size: 12px;">
          ${volumeFormatted}
        </td>
        <td class="text-center" onclick="event.stopPropagation()">
          <button class="btn-cek-bandar" onclick="checkBandarInline('${stock.ticker}', this, event)" title="Ambil status akumulasi broker dari IDX Edge PRO API">
            🔍 Cek Bandar
          </button>
        </td>
        <td class="text-center" onclick="event.stopPropagation()">
          <button class="btn-table-detail" onclick="openStockDetailModal('${stock.ticker}', {name: '${stock.name}', sector: '${stock.sector}', price: ${stock.price}})" title="Buka Detail Analisis Komprehensif">
            📊 Detail
          </button>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rowsHtml;
}

function openPreBreakoutModal(ticker) {
  const stock = prebreakoutState.allResults.find(s => s.ticker === ticker);
  if (!stock) return;

  const title = document.getElementById('pb-modal-title');
  const subtitle = document.getElementById('pb-modal-subtitle');
  const price = document.getElementById('pb-modal-price');
  const score = document.getElementById('pb-modal-score');
  const status = document.getElementById('pb-modal-status');
  const dist = document.getElementById('pb-modal-dist');
  const tvLink = document.getElementById('pb-modal-tv-link');
  const container = document.getElementById('pb-modal-criteria-container');

  if (title) title.textContent = `${stock.ticker} — ${stock.name}`;
  if (subtitle) subtitle.textContent = `Setup Pre-Breakout (${stock.sector})`;
  if (price) price.textContent = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(stock.price);
  if (score) score.textContent = `${stock.total_score} / 7 Kriteria`;
  if (status) {
    status.textContent = stock.status_label;
    status.style.color = stock.status === 'READY' ? 'var(--status-confirmed-text)' : 'var(--status-watchlist-text)';
  }
  const h50Str = (stock.high_50d || 0).toLocaleString('id-ID');
  if (dist) dist.textContent = `-${stock.dist_res_pct}% (50D High: Rp ${h50Str})`;
  if (tvLink) tvLink.href = stock.tradingview_url;

  if (container && stock.criteria) {
    let listHtml = '';
    const keys = ['k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7'];
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
            <span class="crit-title">K${idx + 1}: ${crit.title}</span>
          </div>
          <span class="crit-val">${crit.val}</span>
        </div>
      `;
    });
    container.innerHTML = listHtml;
  }

  const modal = document.getElementById('prebreakout-modal');
  if (modal) modal.classList.remove('hidden');
}

function closePreBreakoutModal() {
  const modal = document.getElementById('prebreakout-modal');
  if (modal) modal.classList.add('hidden');
}

function closePreBreakoutModalOnBackdrop(event) {
  if (event.target.id === 'prebreakout-modal') {
    closePreBreakoutModal();
  }
}

function resetPreBreakoutFilters() {
  prebreakoutState.minScore = 5;
  prebreakoutState.tabFilter = 'ALL';
  prebreakoutState.searchQuery = '';

  const slider = document.getElementById('pb-score-slider');
  if (slider) slider.value = 5;
  const sliderVal = document.getElementById('pb-score-slider-val');
  if (sliderVal) sliderVal.textContent = '≥ 5';

  ['pb-tab-all', 'pb-tab-ready', 'pb-tab-forming'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });
  const allTab = document.getElementById('pb-tab-all');
  if (allTab) allTab.classList.add('active');

  applyPreBreakoutFilters();
  showToast('Filter Pre-Breakout telah direset ke default.');
}
