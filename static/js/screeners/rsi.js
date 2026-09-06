// ============================================================================
// RSI DIVERGENCE SCREENER MODULE
// ============================================================================

const rsiState = {
  allResults: [],
  filteredResults: [],
  sectorFilter: 'ALL',
  typeFilter: 'ALL', // 'ALL' | 'REGULAR_BULL' | 'HIDDEN_BULL'
  gradeFilter: 'ALL', // 'ALL' | 'GRADE_A'
  hideHighRisk: false,
  searchQuery: '',
  sortCol: 'bars_ago',
  sortAsc: true
};

async function loadRsiResults() {
  renderRsiSkeleton(6);
  try {
    const res = await fetch('/api/rsi-divergence');
    const json = await res.json();

    if (json.status === 'success' && json.data) {
      const { timestamp, stats, results } = json.data;
      rsiState.allResults = results || [];
      renderRsiStatsCards(stats, timestamp);
      populateRsiSectorDropdown(rsiState.allResults);
      updateRsiTabCounters(rsiState.allResults);
      applyRsiFilters();
    } else {
      renderRsiStatsCards(null, null);
      rsiState.allResults = [];
      applyRsiFilters();
    }
  } catch (err) {
    console.error('Failed to load RSI results:', err);
    rsiState.allResults = [];
    applyRsiFilters();
  }
}

function populateRsiSectorDropdown(data) {
  const select = document.getElementById('rsi-sector-filter');
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

function updateRsiTabCounters(data) {
  const cntAll = document.getElementById('cnt-rsi-all');
  const cntGradeA = document.getElementById('cnt-rsi-gradea');
  const cntReg = document.getElementById('cnt-rsi-reg');
  const cntHid = document.getElementById('cnt-rsi-hid');

  if (cntAll) cntAll.textContent = data.length;
  if (cntGradeA) cntGradeA.textContent = data.filter(d => d.grade === 'GRADE_A').length;
  if (cntReg) cntReg.textContent = data.filter(d => d.divergence_type === 'REGULAR_BULL').length;
  if (cntHid) cntHid.textContent = data.filter(d => d.divergence_type === 'HIDDEN_BULL').length;
}

function handleRsiSectorFilter(val) {
  rsiState.sectorFilter = val;
  applyRsiFilters();
}

function resetRsiFilters() {
  rsiState.sectorFilter = 'ALL';
  rsiState.typeFilter = 'ALL';
  rsiState.gradeFilter = 'ALL';
  rsiState.hideHighRisk = false;

  const select = document.getElementById('rsi-sector-filter');
  if (select) select.value = 'ALL';

  const riskBtn = document.getElementById('rsi-toggle-highrisk');
  if (riskBtn) {
    riskBtn.classList.remove('active-filter');
    riskBtn.innerHTML = '⚠️ Sembunyikan Grade C';
  }

  ['rsi-tab-all', 'rsi-tab-reg', 'rsi-tab-hid', 'rsi-tab-gradea'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', id === 'rsi-tab-all');
  });

  applyRsiFilters();
}

function renderRsiStatsCards(stats, timestamp) {
  const statTotal = document.getElementById('rsi-stat-total');
  const statReg = document.getElementById('rsi-stat-reg-bull');
  const statHid = document.getElementById('rsi-stat-hid-bull');
  const statTime = document.getElementById('rsi-stat-last-time');
  const badgeNav = document.getElementById('badge-rsi-div');

  const count = stats ? (stats.total_divergences || 0) : (rsiState.allResults.length || 0);
  if (statTotal) statTotal.textContent = count;
  if (statReg) statReg.textContent = stats ? (stats.regular_bull_count || 0) : 0;
  if (statHid) statHid.textContent = stats ? (stats.hidden_bull_count || 0) : 0;

  const timeText = timestamp || 'Belum pernah scan';
  if (statTime) statTime.textContent = timeText;
  if (badgeNav) badgeNav.textContent = count > 0 ? count : (stats ? '0' : '—');
  if (typeof updateSidebarLastScan === 'function') {
    updateSidebarLastScan(timeText);
  }
}

function setRsiTabFilter(tab) {
  ['rsi-tab-all', 'rsi-tab-reg', 'rsi-tab-hid', 'rsi-tab-gradea'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });

  if (tab === 'GRADE_A') {
    rsiState.gradeFilter = 'GRADE_A';
    rsiState.typeFilter = 'ALL';
    document.getElementById('rsi-tab-gradea')?.classList.add('active');
  } else {
    rsiState.gradeFilter = 'ALL';
    rsiState.typeFilter = tab;
    if (tab === 'ALL') document.getElementById('rsi-tab-all')?.classList.add('active');
    if (tab === 'REGULAR_BULL') document.getElementById('rsi-tab-reg')?.classList.add('active');
    if (tab === 'HIDDEN_BULL') document.getElementById('rsi-tab-hid')?.classList.add('active');
  }

  applyRsiFilters();
}

function toggleRsiHighRisk() {
  rsiState.hideHighRisk = !rsiState.hideHighRisk;
  const btn = document.getElementById('rsi-toggle-highrisk');
  if (btn) {
    if (rsiState.hideHighRisk) {
      btn.classList.add('active-filter');
      btn.innerHTML = '🛡️ Grade C Disembunyikan (Aktif)';
    } else {
      btn.classList.remove('active-filter');
      btn.innerHTML = '⚠️ Sembunyikan Grade C';
    }
  }
  applyRsiFilters();
}

function sortRsiTable(col) {
  if (rsiState.sortCol === col) {
    rsiState.sortAsc = !rsiState.sortAsc;
  } else {
    rsiState.sortCol = col;
    rsiState.sortAsc = (col === 'ticker' || col === 'name' || col === 'sector' || col === 'bars_ago');
  }

  const icons = document.querySelectorAll('#rsi-table .sort-icon');
  icons.forEach(ic => ic.textContent = '↕');
  const targetIcon = document.getElementById(`rsi-sort-${col}`);
  if (targetIcon) {
    targetIcon.textContent = rsiState.sortAsc ? '▲' : '▼';
  }

  applyRsiFilters();
}

function applyRsiFilters() {
  let list = [...rsiState.allResults];

  // 1. Type Filter
  if (rsiState.typeFilter === 'REGULAR_BULL') {
    list = list.filter(item => item.divergence_type === 'REGULAR_BULL');
  } else if (rsiState.typeFilter === 'HIDDEN_BULL') {
    list = list.filter(item => item.divergence_type === 'HIDDEN_BULL');
  }

  // 2. Grade A Filter
  if (rsiState.gradeFilter === 'GRADE_A') {
    list = list.filter(item => item.grade === 'GRADE_A');
  }

  // 3. Hide High-Risk Grade C
  if (rsiState.hideHighRisk) {
    list = list.filter(item => !item.is_high_risk);
  }

  // 4. Sector Filter
  if (rsiState.sectorFilter !== 'ALL') {
    list = list.filter(item => item.sector === rsiState.sectorFilter);
  }

  // Update Reset button visibility
  const resetBtn = document.getElementById('rsi-reset-btn');
  const isCustomFiltered = (rsiState.sectorFilter !== 'ALL' || rsiState.typeFilter !== 'ALL' || rsiState.gradeFilter !== 'ALL' || rsiState.hideHighRisk);
  if (resetBtn) {
    resetBtn.classList.toggle('hidden', !isCustomFiltered);
  }

  // Update Table Count Badge
  const countBadge = document.getElementById('rsi-table-count-badge');
  if (countBadge) {
    countBadge.textContent = `${list.length} Sinyal Terkualifikasi`;
  }

  // 5. Search Query
  if (rsiState.searchQuery) {
    list = list.filter(item =>
      item.ticker.toLowerCase().includes(rsiState.searchQuery) ||
      item.name.toLowerCase().includes(rsiState.searchQuery) ||
      item.sector.toLowerCase().includes(rsiState.searchQuery)
    );
  }

  // 6. Sorting
  list.sort((a, b) => {
    let valA = a[rsiState.sortCol];
    let valB = b[rsiState.sortCol];

    if (typeof valA === 'string') {
      return rsiState.sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    valA = valA !== undefined ? valA : 0;
    valB = valB !== undefined ? valB : 0;
    return rsiState.sortAsc ? valA - valB : valB - valA;
  });

  rsiState.filteredResults = list;
  renderRsiTable(list);
}

function renderRsiSkeleton(rowCount = 6) {
  const tbody = document.getElementById('rsi-table-body');
  const emptyState = document.getElementById('rsi-empty-state');
  if (emptyState) emptyState.classList.add('hidden');
  if (!tbody) return;

  let html = '';
  for (let i = 0; i < rowCount; i++) {
    html += `
      <tr>
        <td><div class="skeleton-shimmer sk-cell" style="width: 55px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 140px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 90px;"></div></td>
        <td><div class="skeleton-shimmer sk-cell" style="width: 75px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 90px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 110px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 50px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 130px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 160px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 80px;"></div></td>
        <td class="text-center"><div class="skeleton-shimmer sk-cell" style="width: 30px; height: 26px; border-radius: 6px;"></div></td>
      </tr>
    `;
  }
  tbody.innerHTML = html;
}

function renderRsiTable(data) {
  const tbody = document.getElementById('rsi-table-body');
  const countBadge = document.getElementById('rsi-table-count-badge');
  const emptyState = document.getElementById('rsi-empty-state');

  if (countBadge) {
    countBadge.textContent = `${data.length} Sinyal Bullish`;
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
    const isReg = stock.divergence_type === 'REGULAR_BULL';
    const typeBadgeClass = isReg ? 'reg-bull' : 'hid-bull';
    const typeIcon = isReg ? '🔄' : '🚀';

    // RSI class
    const rsiClass = stock.rsi <= 30 ? 'oversold' : (stock.rsi >= 70 ? 'overbought' : 'neutral');

    // Price change
    const changeClass = stock.pct_change_1d >= 0 ? 'pos' : 'neg';
    const changeSign = stock.pct_change_1d >= 0 ? '+' : '';
    const changeHtml = stock.pct_change_1d !== 0
      ? `<span class="price-change-sub ${changeClass}">${changeSign}${stock.pct_change_1d}%</span>`
      : '';

    const priceFormatted = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(stock.price);

    // Stagger animation delay
    const delay = Math.min(idx * 25, 500);

    // Pivot comparison display
    const lowCompare = isReg ? `L: ${stock.pivot_low} < ${stock.prev_pivot_low}` : `L: ${stock.pivot_low} > ${stock.prev_pivot_low}`;
    const rsiCompare = isReg ? `RSI: ${stock.pivot_rsi} > ${stock.prev_pivot_rsi}` : `RSI: ${stock.pivot_rsi} < ${stock.prev_pivot_rsi}`;

    // Trend Context
    const isAbove200 = stock.price > (stock.ma200 || 0);
    const trendClass = isAbove200 ? 'trend-above' : 'trend-below';
    const trendText = isAbove200 ? 'Above MA200 ✓' : 'Below MA200 ⚠️';

    rowsHtml += `
      <tr style="animation-delay: ${delay}ms" onclick="openRsiModal('${stock.ticker}')">
        <td>
          <div class="ticker-cell-wrapper">
            <button class="btn-star-pin ${(typeof watchlistState !== 'undefined' && watchlistState.pinnedTickers && watchlistState.pinnedTickers.has(stock.ticker)) ? 'pinned' : ''}" data-ticker="${stock.ticker}" onclick="togglePinStock('${stock.ticker}', '${(stock.name || '').replace(/'/g, "\\'")}', '${stock.sector}', 'RSI Divergence', event)" title="${(typeof watchlistState !== 'undefined' && watchlistState.pinnedTickers && watchlistState.pinnedTickers.has(stock.ticker)) ? 'Hapus dari Watchlist' : 'Sematkan ke Watchlist'}">★</button>
            <div class="ticker-info-stack">
              <span class="ticker-cell">${stock.ticker}</span>
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
          <span class="grade-badge ${stock.grade_class || 'badge-grade-b'}" title="${stock.grade_label || ''}">
            ${stock.grade_badge || 'Grade B'}
          </span>
        </td>
        <td class="text-center">
          <span class="badge-div-type ${typeBadgeClass}">${typeIcon} ${stock.divergence_label}</span>
        </td>
        <td class="text-center">
          <span class="rsi-pill ${rsiClass}">${stock.rsi.toFixed(1)}</span>
        </td>
        <td class="text-center">
          <div class="trend-context-pill ${trendClass}">
            <span>${trendText}</span>
            <small style="display: block; font-size: 10px; color: var(--text-muted);">MA200: ${(stock.ma200 || 0).toLocaleString('id-ID')}</small>
          </div>
        </td>
        <td class="text-center">
          <div class="pivot-struct-box">
            <div class="pivot-struct-row">
              <span class="tag">Price:</span> <span class="accent">${lowCompare}</span>
            </div>
            <div class="pivot-struct-row">
              <span class="tag">RSI:</span> <span class="accent">${rsiCompare}</span>
            </div>
          </div>
        </td>
        <td class="text-center">
          <span class="count-pill">
            ${stock.recency_text}
          </span>
        </td>
        <td class="text-center">
          <a href="${stock.tradingview_url}" target="_blank" class="btn-tv" onclick="event.stopPropagation()" title="Buka Chart TradingView IDX:${stock.ticker}">
            ↗
          </a>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rowsHtml;
}

function openRsiModal(ticker) {
  const stock = rsiState.allResults.find(s => s.ticker === ticker);
  if (!stock) return;

  const title = document.getElementById('rsi-modal-title');
  const subtitle = document.getElementById('rsi-modal-subtitle');
  const price = document.getElementById('rsi-modal-price');
  const type = document.getElementById('rsi-modal-type');
  const rsiVal = document.getElementById('rsi-modal-rsi');
  const recency = document.getElementById('rsi-modal-recency');
  const tvLink = document.getElementById('rsi-modal-tv-link');

  const diagPrevBars = document.getElementById('rsi-diag-prev-bars');
  const diagPrevPrice = document.getElementById('rsi-diag-prev-price');
  const diagPrevRsi = document.getElementById('rsi-diag-prev-rsi');
  const diagCurrPrice = document.getElementById('rsi-diag-curr-price');
  const diagCurrRsi = document.getElementById('rsi-diag-curr-rsi');
  const diagCompPrice = document.getElementById('rsi-diag-compare-price');
  const diagCompRsi = document.getElementById('rsi-diag-compare-rsi');
  const techText = document.getElementById('rsi-tech-text');

  const isReg = stock.divergence_type === 'REGULAR_BULL';

  if (title) title.textContent = `${stock.ticker} — ${stock.name}`;
  if (subtitle) subtitle.textContent = `Inspeksi Sinyal ${stock.divergence_label} (IDX:${stock.ticker})`;
  if (price) price.textContent = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(stock.price);
  if (type) {
    type.textContent = stock.divergence_label;
    type.style.color = isReg ? 'var(--status-div-reg-text)' : 'var(--status-div-hid-text)';
  }
  if (rsiVal) rsiVal.textContent = stock.rsi.toFixed(1);
  if (recency) recency.textContent = stock.recency_text;
  if (tvLink) tvLink.href = stock.tradingview_url;

  if (diagPrevBars) diagPrevBars.textContent = `${stock.bars_between} bar lalu`;
  if (diagPrevPrice) diagPrevPrice.textContent = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(stock.prev_pivot_low);
  if (diagPrevRsi) diagPrevRsi.textContent = stock.prev_pivot_rsi.toFixed(1);

  if (diagCurrPrice) diagCurrPrice.textContent = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(stock.pivot_low);
  if (diagCurrRsi) diagCurrRsi.textContent = stock.pivot_rsi.toFixed(1);

  if (diagCompPrice) {
    diagCompPrice.textContent = isReg ? `Price: Lower Low (${stock.pivot_low} < ${stock.prev_pivot_low})` : `Price: Higher Low (${stock.pivot_low} > ${stock.prev_pivot_low})`;
  }
  if (diagCompRsi) {
    diagCompRsi.textContent = isReg ? `RSI: Higher Low (${stock.pivot_rsi} > ${stock.prev_pivot_rsi})` : `RSI: Lower Low (${stock.pivot_rsi} < ${stock.prev_pivot_rsi})`;
  }

  if (techText) {
    techText.textContent = isReg
      ? `Sinyal Regular Bullish Reversal: Harga saham berhasil membentuk swing low baru yang lebih rendah (Rp ${stock.pivot_low}), namun indikator RSI mencetak titik low yang lebih tinggi (${stock.pivot_rsi} vs ${stock.prev_pivot_rsi}). Ini mencerminkan pelemahan momentum jual (seller exhaustion) dan membuka probabilitas tinggi untuk pembalikan arah harga ke atas.`
      : `Sinyal Hidden Bullish Trend Continuation: Harga saham membentuk swing low yang lebih tinggi (Rp ${stock.pivot_low} > Rp ${stock.prev_pivot_low}), namun indikator RSI justru jatuh ke titik yang lebih rendah (${stock.pivot_rsi} < ${stock.prev_pivot_rsi}). Ini mengindikasikan bahwa tren naik utama (uptrend) masih sangat kuat dan penurunan sebelumnya hanyalah koreksi teknikal sementara yang sehat.`;
  }

  const modal = document.getElementById('rsi-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeRsiModal() {
  const modal = document.getElementById('rsi-modal');
  if (modal) modal.classList.add('hidden');
}

function closeRsiModalOnBackdrop(event) {
  if (event.target.id === 'rsi-modal') {
    closeRsiModal();
  }
}

function resetRsiFilters() {
  rsiState.typeFilter = 'ALL';
  rsiState.searchQuery = '';

  ['rsi-tab-all', 'rsi-tab-reg', 'rsi-tab-hid'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });
  const allTab = document.getElementById('rsi-tab-all');
  if (allTab) allTab.classList.add('active');

  applyRsiFilters();
  showToast('Filter RSI Divergence telah direset ke default.');
}
