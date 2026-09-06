// ============================================================================
// PERSONAL WATCHLIST & TRADE JOURNALING MODULE (static/js/screeners/watchlist.js)
// ============================================================================

// Defensive formatIDR helper
if (typeof formatIDR !== 'function') {
  window.formatIDR = function(val) {
    if (val === null || val === undefined || isNaN(val)) return "Rp 0";
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      maximumFractionDigits: 0
    }).format(Math.round(val));
  };
}

const watchlistState = {
  activeTab: 'WATCHLIST', // 'WATCHLIST' | 'JOURNAL'
  watchlistItems: [],
  pinnedTickers: new Set(),
  trades: [],
  journalFilter: 'ALL',
  searchQuery: '',
  stats: null,
  sortCol: 'date',
  sortAsc: false
};

// 1. INITIAL LOADER
async function loadWatchlistAndJournal() {
  try {
    // Fetch both watchlist and journal in parallel
    const [wRes, jRes] = await Promise.all([
      fetch('/api/watchlist'),
      fetch('/api/journal')
    ]);

    const wJson = await wRes.json();
    const jJson = await jRes.json();

    if (wJson.status === 'success') {
      watchlistState.watchlistItems = wJson.data || [];
      watchlistState.pinnedTickers = new Set(wJson.tickers || []);
    }

    if (jJson.status === 'success') {
      watchlistState.trades = jJson.data || [];
      watchlistState.stats = jJson.stats || null;
    }

    updateWatchlistStatsCards();
    updateSidebarWatchlistBadge();
    updateAllPinButtonsOnPage();

    if (watchlistState.activeTab === 'WATCHLIST') {
      renderWatchlistTable();
    } else {
      renderJournalTable();
    }
  } catch (err) {
    console.error('Error loading watchlist and journal:', err);
  }
}

// 2. TAB SWITCHER
function switchWatchlistTab(tab) {
  watchlistState.activeTab = tab;

  const btnW = document.getElementById('tab-wl-watchlist');
  const btnJ = document.getElementById('tab-wl-journal');
  const secW = document.getElementById('section-active-watchlist');
  const secJ = document.getElementById('section-trade-journal');
  const filterGroup = document.getElementById('wl-journal-filter-group');
  const sectionTitle = document.getElementById('wl-section-title');
  const counterPill = document.getElementById('wl-active-tab-counter');

  if (tab === 'WATCHLIST') {
    if (btnW) btnW.classList.add('active');
    if (btnJ) btnJ.classList.remove('active');
    if (secW) secW.classList.remove('hidden');
    if (secJ) secJ.classList.add('hidden');
    if (filterGroup) filterGroup.style.display = 'none';
    if (sectionTitle) sectionTitle.textContent = 'Active Watchlist Radar';
    if (counterPill) counterPill.textContent = `${watchlistState.watchlistItems.length} Saham`;
    renderWatchlistTable();
  } else {
    if (btnW) btnW.classList.remove('active');
    if (btnJ) btnJ.classList.add('active');
    if (secW) secW.classList.add('hidden');
    if (secJ) secJ.classList.remove('hidden');
    if (filterGroup) filterGroup.style.display = 'flex';
    if (sectionTitle) sectionTitle.textContent = 'Buku Jurnal Transaksi';
    if (counterPill) counterPill.textContent = `${watchlistState.trades.length} Transaksi`;
    renderJournalTable();
  }
}

// 3. STATS & BADGES
function updateWatchlistStatsCards() {
  const stats = watchlistState.stats;
  const elWlCount = document.getElementById('wl-stat-watchlist-count');
  const elOpenTrades = document.getElementById('wl-stat-open-trades');
  const elOpenCapital = document.getElementById('wl-stat-open-capital');
  const elWinRate = document.getElementById('wl-stat-win-rate');
  const elWinLoss = document.getElementById('wl-stat-win-loss-meta');
  const elNetPnl = document.getElementById('wl-stat-net-pnl');
  const elProfitFactor = document.getElementById('wl-stat-profit-factor');

  const elCntW = document.getElementById('cnt-wl-watchlist');
  const elCntJ = document.getElementById('cnt-wl-journal');
  const elTabBadge = document.getElementById('wl-active-tab-counter');

  const wCount = watchlistState.watchlistItems.length;
  const jCount = watchlistState.trades.length;

  if (elWlCount) elWlCount.textContent = wCount;
  if (elCntW) elCntW.textContent = wCount;
  if (elCntJ) elCntJ.textContent = jCount;
  if (elTabBadge) {
    elTabBadge.textContent = watchlistState.activeTab === 'WATCHLIST' ? `${wCount} Saham` : `${jCount} Transaksi`;
  }

  if (stats) {
    if (elOpenTrades) elOpenTrades.textContent = stats.open_trades_count || 0;
    if (elOpenCapital) elOpenCapital.textContent = `Modal: ${formatIDR(stats.open_capital_allocated || 0)}`;

    const wr = stats.win_rate_pct || 0;
    if (elWinRate) elWinRate.textContent = `${wr.toFixed(1)}%`;
    if (elWinLoss) elWinLoss.textContent = `${stats.wins_count || 0} Menang / ${stats.losses_count || 0} Kalah`;

    const netPnl = stats.total_realized_net || 0;
    if (elNetPnl) {
      const sign = netPnl > 0 ? '+' : (netPnl < 0 ? '-' : '');
      elNetPnl.textContent = `${sign}${formatIDR(Math.abs(netPnl))}`;
      elNetPnl.style.color = netPnl > 0 ? '#4ade80' : (netPnl < 0 ? '#f87171' : 'var(--text-primary)');
    }
    if (elProfitFactor) elProfitFactor.textContent = `Profit Factor: ${stats.profit_factor || 0.0}`;
  }
}

function updateSidebarWatchlistBadge() {
  const badge = document.getElementById('badge-watchlist');
  if (badge) {
    const count = watchlistState.watchlistItems.length;
    badge.textContent = count > 0 ? count : '0';
  }
}

// 4. GLOBAL PIN / UNPIN HANDLER (Callable anywhere in application)
async function togglePinStock(ticker, name = '', sector = 'General', source = 'Manual', event = null) {
  if (event) {
    event.stopPropagation();
  }

  const clean = (ticker || '').replace('.JK', '').trim().toUpperCase();
  if (!clean) return;

  const isPinned = watchlistState.pinnedTickers.has(clean);

  if (isPinned) {
    // Unpin
    try {
      const res = await fetch(`/api/watchlist/unpin/${clean}`, { method: 'DELETE' });
      const json = await res.json();
      if (json.status === 'success') {
        watchlistState.pinnedTickers.delete(clean);
        watchlistState.watchlistItems = watchlistState.watchlistItems.filter(i => i.ticker !== clean);
        updateAllPinButtonsOnPage();
        updateSidebarWatchlistBadge();
        updateWatchlistStatsCards();
        if (watchlistState.activeTab === 'WATCHLIST') renderWatchlistTable();
        if (typeof showToast === 'function') showToast(`⭐ ${clean} dihapus dari Watchlist`, 'info');
      }
    } catch (err) {
      console.error('Failed to unpin:', err);
    }
  } else {
    // Pin
    try {
      const res = await fetch('/api/watchlist/pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: clean, name, sector, source })
      });
      const json = await res.json();
      if (json.status === 'success') {
        watchlistState.pinnedTickers.add(clean);
        if (json.data) {
          watchlistState.watchlistItems.unshift(json.data);
        }
        updateAllPinButtonsOnPage();
        updateSidebarWatchlistBadge();
        updateWatchlistStatsCards();
        if (watchlistState.activeTab === 'WATCHLIST') renderWatchlistTable();
        if (typeof showToast === 'function') showToast(`⭐ ${clean} disematkan ke Watchlist!`, 'success');
      }
    } catch (err) {
      console.error('Failed to pin:', err);
    }
  }
}

function updateAllPinButtonsOnPage() {
  const buttons = document.querySelectorAll('.btn-star-pin');
  buttons.forEach(btn => {
    const t = btn.getAttribute('data-ticker');
    if (t) {
      const clean = t.replace('.JK', '').trim().toUpperCase();
      if (watchlistState.pinnedTickers.has(clean)) {
        btn.classList.add('pinned');
        btn.setAttribute('title', 'Hapus dari Watchlist');
      } else {
        btn.classList.remove('pinned');
        btn.setAttribute('title', 'Sematkan ke Watchlist (⭐)');
      }
    }
  });
}

// 5. RENDER ACTIVE WATCHLIST TABLE
function renderWatchlistTable() {
  const tbody = document.getElementById('watchlist-table-body');
  const emptyState = document.getElementById('watchlist-empty-state');
  if (!tbody) return;

  const items = watchlistState.watchlistItems;

  if (!items || items.length === 0) {
    tbody.innerHTML = '';
    if (emptyState) emptyState.classList.remove('hidden');
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');

  let rowsHtml = '';
  items.forEach(item => {
    const t = item.ticker;
    const sourceClass = (item.source_screener || '').toLowerCase().includes('quality') ? 'quality' :
                        ((item.source_screener || '').toLowerCase().includes('breakout') ? 'prebreakout' : 'sepa');

    const pinnedDate = item.pinned_at ? item.pinned_at.split(' ')[0] : '—';

    rowsHtml += `
      <tr class="table-row-clickable" onclick="openStockDetailModal('${t}', {name: '${escapeQuotes(item.name)}', sector: '${item.sector}'})">
        <td class="text-center" onclick="event.stopPropagation()">
          <button class="btn-star-pin pinned" data-ticker="${t}" onclick="togglePinStock('${t}', '${escapeQuotes(item.name)}', '${item.sector}', '${item.source_screener}', event)" title="Hapus dari Watchlist">
            ★
          </button>
        </td>
        <td>
          <span class="ticker-badge">${t}</span>
        </td>
        <td>
          <span class="company-name-text">${item.name || t}</span>
        </td>
        <td>
          <span class="sector-tag">${item.sector || 'General'}</span>
        </td>
        <td>
          <span class="badge-source ${sourceClass}">${item.source_screener || 'Manual'}</span>
        </td>
        <td>
          <span class="watchlist-notes-snippet">${item.notes || '<span class="text-muted">Tidak ada catatan</span>'}</span>
        </td>
        <td class="mono text-muted text-sm">${pinnedDate}</td>
        <td class="text-center" onclick="event.stopPropagation()">
          <div class="row-actions-group">
            <button class="btn-table-action" onclick="openPositionCalculator({ticker: '${t}', name: '${escapeQuotes(item.name)}', sector: '${item.sector}'})" title="Hitung Sizing & Risiko">
              🧮 Sizing
            </button>
            <button class="btn-table-action primary" onclick="openNewTradeEntryModal({ticker: '${t}', name: '${escapeQuotes(item.name)}', sector: '${item.sector}', setup_type: '${item.source_screener}'})" title="Catat Pembelian Riil">
              📝 Beli
            </button>
            <button class="btn-table-action danger" onclick="togglePinStock('${t}', '', '', '', event)" title="Hapus">
              ✕
            </button>
          </div>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rowsHtml;
}

// 6. RENDER TRADE JOURNAL TABLE
function renderJournalTable() {
  const tbody = document.getElementById('journal-table-body');
  const emptyState = document.getElementById('journal-empty-state');
  if (!tbody) return;

  let trades = watchlistState.trades;

  // Status Filter
  if (watchlistState.journalFilter !== 'ALL') {
    trades = trades.filter(t => t.status === watchlistState.journalFilter);
  }

  // Search Filter
  if (watchlistState.searchQuery) {
    const q = watchlistState.searchQuery.toLowerCase();
    trades = trades.filter(t =>
      (t.ticker && t.ticker.toLowerCase().includes(q)) ||
      (t.name && t.name.toLowerCase().includes(q)) ||
      (t.setup_type && t.setup_type.toLowerCase().includes(q))
    );
  }

  if (!trades || trades.length === 0) {
    tbody.innerHTML = '';
    if (emptyState) emptyState.classList.remove('hidden');
    return;
  }

  if (emptyState) emptyState.classList.add('hidden');

  let rowsHtml = '';
  trades.forEach(tr => {
    const statusClass = tr.status === 'CLOSED_WIN' ? 'win' :
                        (tr.status === 'CLOSED_LOSS' ? 'loss' :
                        (tr.status === 'CLOSED_BEP' ? 'bep' : 'open'));
    const statusLabel = tr.status === 'CLOSED_WIN' ? '🏆 WIN' :
                        (tr.status === 'CLOSED_LOSS' ? '🛑 LOSS' :
                        (tr.status === 'CLOSED_BEP' ? '⚖️ BEP' : '💼 OPEN'));

    const buyPrice = tr.buy_price ? `Rp ${tr.buy_price.toLocaleString('id-ID')}` : '—';
    const slPrice = tr.stop_loss ? `SL: ${tr.stop_loss.toLocaleString('id-ID')}` : '';
    const exitPrice = tr.exit_price ? `Rp ${tr.exit_price.toLocaleString('id-ID')}` : '<span class="text-muted">Aktif</span>';
    const exitDate = tr.exit_date ? tr.exit_date : '<span class="text-muted">Berjalan</span>';

    // PnL display
    let pnlHtml = '—';
    if (tr.status !== 'OPEN') {
      const net = tr.net_pnl || 0;
      const pct = tr.realized_pnl_pct || 0;
      const sign = net > 0 ? '+' : (net < 0 ? '-' : '');
      const cls = net > 0 ? 'pos' : (net < 0 ? 'neg' : 'neu');

      pnlHtml = `
        <div class="pnl-cell-wrap">
          <span class="pnl-val-primary ${cls}">${sign}${formatIDR(Math.abs(net))}</span>
          <span class="pnl-val-sub">(${sign}${Math.abs(pct).toFixed(1)}%)</span>
        </div>
      `;
    }

    const sharesCount = (tr.lots * 100).toLocaleString('id-ID');

    rowsHtml += `
      <tr>
        <td class="text-center">
          <span class="badge-journal-status ${statusClass}">${statusLabel}</span>
        </td>
        <td>
          <div class="trade-ticker-col">
            <span class="ticker-badge">${tr.ticker}</span>
            <span class="trade-company-sub text-muted text-sm">${tr.name}</span>
          </div>
        </td>
        <td>
          <span class="trade-setup-tag">${tr.setup_type || 'Breakout'}</span>
        </td>
        <td class="mono text-sm">
          <div>${tr.buy_date}</div>
          <div class="text-muted text-xs">${exitDate}</div>
        </td>
        <td class="text-right mono">
          <div class="bold">${buyPrice}</div>
          <div class="text-muted text-xs">${slPrice}</div>
        </td>
        <td class="text-right mono">
          <div class="bold">${tr.lots} Lot</div>
          <div class="text-muted text-xs">(${sharesCount} lbr)</div>
        </td>
        <td class="text-right mono text-sm">
          ${formatIDR(tr.capital_allocated)}
        </td>
        <td class="text-right mono">
          ${exitPrice}
        </td>
        <td class="text-right">
          ${pnlHtml}
        </td>
        <td class="text-center">
          <div class="row-actions-group">
            ${tr.status === 'OPEN' ? `
              <button class="btn-table-action success" onclick="openCloseTradeModal(${tr.id})" title="Tutup / Selesaikan Posisi Ini">
                ✅ Tutup
              </button>
            ` : `
              <button class="btn-table-action secondary" onclick="viewTradeEvaluationModal(${tr.id})" title="Lihat Catatan Evaluasi">
                👁️ Note
              </button>
            `}
            <button class="btn-table-action danger" onclick="deleteJournalTrade(${tr.id})" title="Hapus Transaksi">
              🗑️
            </button>
          </div>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rowsHtml;
}

// 7. FILTER & SEARCH HANDLERS
function filterJournalStatus(status) {
  watchlistState.journalFilter = status;

  const pills = document.querySelectorAll('#journal-status-pills .score-pill-btn');
  pills.forEach(p => {
    if (p.getAttribute('data-status') === status) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  });

  renderJournalTable();
}

function handleJournalSearch(val) {
  watchlistState.searchQuery = (val || '').trim();
  const clearBtn = document.getElementById('journal-search-clear');
  if (clearBtn) {
    if (watchlistState.searchQuery) clearBtn.classList.remove('hidden');
    else clearBtn.classList.add('hidden');
  }
  renderJournalTable();
}

function clearJournalSearch() {
  const inp = document.getElementById('journal-search-input');
  if (inp) inp.value = '';
  handleJournalSearch('');
}

// 8. TRADE MODAL HANDLERS
function openNewTradeEntryModal(preset = {}) {
  const modal = document.getElementById('modal-trade-journal');
  const formEntry = document.getElementById('form-journal-entry');
  const formClose = document.getElementById('form-journal-close');
  const formSettings = document.getElementById('form-journal-settings');

  if (!modal || !formEntry) return;

  // Show entry form, hide others
  formEntry.classList.remove('hidden');
  if (formClose) formClose.classList.add('hidden');
  if (formSettings) formSettings.classList.add('hidden');

  document.getElementById('journal-modal-icon').textContent = '📝';
  document.getElementById('journal-modal-title').textContent = 'Catat Transaksi Beli Baru';
  const badge = document.getElementById('journal-modal-mode-badge');
  if (badge) {
    badge.className = 'journal-mode-pill open';
    badge.textContent = 'POSISI BARU';
  }

  // Pre-fill inputs
  const elDate = document.getElementById('entry-date');
  if (elDate) elDate.value = new Date().toISOString().split('T')[0];

  const elTicker = document.getElementById('entry-ticker');
  const elName = document.getElementById('entry-name');
  const elSector = document.getElementById('entry-sector');
  const elPrice = document.getElementById('entry-price');
  const elLots = document.getElementById('entry-lots');
  const elSL = document.getElementById('entry-sl');
  const elT1 = document.getElementById('entry-t1');
  const elT2 = document.getElementById('entry-t2');
  const elSetup = document.getElementById('entry-setup');
  const elNotes = document.getElementById('entry-notes');

  if (elTicker) elTicker.value = preset.ticker || '';
  if (elName) elName.value = preset.name || preset.ticker || '';
  if (elSector) elSector.value = preset.sector || 'General';
  if (elPrice) elPrice.value = preset.buy_price || preset.price || '';
  if (elLots) elLots.value = preset.lots || 10;
  if (elSL) elSL.value = preset.stop_loss || preset.sl || '';
  if (elT1) elT1.value = preset.target_1 || preset.t1 || '';
  if (elT2) elT2.value = preset.target_2 || preset.t2 || '';
  if (elSetup && preset.setup_type) elSetup.value = preset.setup_type;
  if (elNotes) elNotes.value = preset.notes || '';

  calcJournalEntrySummary();
  modal.classList.remove('hidden');
}

function openCloseTradeModal(tradeId) {
  const trade = watchlistState.trades.find(t => t.id === tradeId);
  if (!trade) return;

  const modal = document.getElementById('modal-trade-journal');
  const formEntry = document.getElementById('form-journal-entry');
  const formClose = document.getElementById('form-journal-close');
  const formSettings = document.getElementById('form-journal-settings');

  if (!modal || !formClose) return;

  formEntry.classList.add('hidden');
  formClose.classList.remove('hidden');
  if (formSettings) formSettings.classList.add('hidden');

  document.getElementById('journal-modal-icon').textContent = '✅';
  document.getElementById('journal-modal-title').textContent = `Tutup Posisi: ${trade.ticker}`;
  const badge = document.getElementById('journal-modal-mode-badge');
  if (badge) {
    badge.className = 'journal-mode-pill close';
    badge.textContent = 'SELESAIKAN TRADE';
  }

  // Set trade info
  document.getElementById('close-trade-id').value = trade.id;
  document.getElementById('close-ticker-display').textContent = trade.ticker;
  document.getElementById('close-name-display').textContent = trade.name;
  document.getElementById('close-buy-price-lots').textContent = `Rp ${trade.buy_price.toLocaleString('id-ID')} (${trade.lots} Lot)`;

  // Defaults
  document.getElementById('close-exit-date').value = new Date().toISOString().split('T')[0];
  document.getElementById('close-exit-price').value = trade.target_1 || trade.buy_price;
  document.getElementById('close-exit-reason').value = 'TARGET_1';
  document.getElementById('close-notes').value = '';

  recomputeClosePnlPreview();
  modal.classList.remove('hidden');
}

function closeTradeJournalModal() {
  const modal = document.getElementById('modal-trade-journal');
  if (modal) modal.classList.add('hidden');
}

function closeTradeJournalOnBackdrop(e) {
  if (e.target.id === 'modal-trade-journal') {
    closeTradeJournalModal();
  }
}

// 9. FORM SUBMISSION
async function submitJournalEntry(e) {
  e.preventDefault();

  const payload = {
    ticker: document.getElementById('entry-ticker').value.trim().toUpperCase(),
    name: document.getElementById('entry-name').value.trim(),
    sector: document.getElementById('entry-sector').value.trim() || 'General',
    buy_date: document.getElementById('entry-date').value,
    buy_price: parseFloat(document.getElementById('entry-price').value),
    lots: parseInt(document.getElementById('entry-lots').value, 10),
    stop_loss: parseFloat(document.getElementById('entry-sl').value) || null,
    target_1: parseFloat(document.getElementById('entry-t1').value) || null,
    target_2: parseFloat(document.getElementById('entry-t2').value) || null,
    setup_type: document.getElementById('entry-setup').value,
    notes: document.getElementById('entry-notes').value.trim(),
    chart_url: document.getElementById('entry-chart').value.trim()
  };

  try {
    const res = await fetch('/api/journal/entry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const json = await res.json();

    if (json.status === 'success') {
      closeTradeJournalModal();
      if (typeof showToast === 'function') showToast(json.message || 'Transaksi dicatat di Jurnal!', 'success');
      loadWatchlistAndJournal();
      switchWatchlistTab('JOURNAL');
    } else {
      if (typeof showToast === 'function') showToast(json.message || 'Gagal mencatat transaksi', 'error');
    }
  } catch (err) {
    console.error('Submit trade error:', err);
    if (typeof showToast === 'function') showToast('Terjadi kesalahan jaringan', 'error');
  }
}

async function submitCloseTrade(e) {
  e.preventDefault();

  const tradeId = document.getElementById('close-trade-id').value;
  const payload = {
    exit_date: document.getElementById('close-exit-date').value,
    exit_price: parseFloat(document.getElementById('close-exit-price').value),
    exit_reason: document.getElementById('close-exit-reason').value,
    notes: document.getElementById('close-notes').value.trim()
  };

  try {
    const res = await fetch(`/api/journal/close/${tradeId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const json = await res.json();

    if (json.status === 'success') {
      closeTradeJournalModal();
      if (typeof showToast === 'function') showToast(json.message || 'Posisi berhasil ditutup!', 'success');
      loadWatchlistAndJournal();
    } else {
      if (typeof showToast === 'function') showToast(json.message || 'Gagal menutup posisi', 'error');
    }
  } catch (err) {
    console.error('Close trade error:', err);
    if (typeof showToast === 'function') showToast('Terjadi kesalahan sistem', 'error');
  }
}

async function deleteJournalTrade(tradeId) {
  if (!confirm('Apakah Anda yakin ingin menghapus catatan transaksi ini dari Jurnal?')) return;

  try {
    const res = await fetch(`/api/journal/${tradeId}`, { method: 'DELETE' });
    const json = await res.json();
    if (json.status === 'success') {
      if (typeof showToast === 'function') showToast('Transaksi berhasil dihapus', 'info');
      loadWatchlistAndJournal();
    }
  } catch (err) {
    console.error('Delete trade error:', err);
  }
}

// 10. REAL-TIME FORM PREVIEWS
function calcJournalEntrySummary() {
  const elPrice = document.getElementById('entry-price');
  const elLots = document.getElementById('entry-lots');
  const elShares = document.getElementById('entry-shares-display');
  const elCapital = document.getElementById('entry-capital-display');
  const elFee = document.getElementById('entry-fee-display');

  const price = parseFloat(elPrice ? elPrice.value : 0) || 0;
  const lots = parseInt(elLots ? elLots.value : 0, 10) || 0;

  const shares = lots * 100;
  const capital = shares * price;
  const fee = capital * 0.0015; // 0.15%

  if (elShares) elShares.textContent = `${shares.toLocaleString('id-ID')} Lembar`;
  if (elCapital) elCapital.textContent = formatIDR(capital);
  if (elFee) elFee.textContent = formatIDR(fee);
}

function recomputeClosePnlPreview() {
  const tradeId = parseInt(document.getElementById('close-trade-id').value, 10);
  const trade = watchlistState.trades.find(t => t.id === tradeId);
  if (!trade) return;

  const elExitPrice = document.getElementById('close-exit-price');
  const exitPrice = parseFloat(elExitPrice ? elExitPrice.value : 0) || 0;

  const buyPrice = trade.buy_price;
  const shares = trade.lots * 100;
  const capital = trade.capital_allocated;

  const grossPnl = (shares * exitPrice) - capital;
  const grossPnlPct = buyPrice > 0 ? ((exitPrice - buyPrice) / buyPrice) * 100.0 : 0;

  const feeBuy = capital * 0.0015;
  const feeSell = (shares * exitPrice) * 0.0025;
  const totalFee = feeBuy + feeSell;
  const netPnl = grossPnl - totalFee;

  const elPct = document.getElementById('close-preview-pct');
  const elGross = document.getElementById('close-preview-gross');
  const elFee = document.getElementById('close-preview-fee');
  const elNet = document.getElementById('close-preview-net');

  const sign = netPnl > 0 ? '+' : (netPnl < 0 ? '-' : '');
  const cls = netPnl > 0 ? 'pos' : (netPnl < 0 ? 'neg' : 'neu');

  if (elPct) {
    elPct.textContent = `${sign}${Math.abs(grossPnlPct).toFixed(1)}%`;
    elPct.className = `pnl-card-val mono ${cls}`;
  }
  if (elGross) {
    elGross.textContent = `${sign}${formatIDR(Math.abs(grossPnl))}`;
    elGross.className = `pnl-card-val mono ${cls}`;
  }
  if (elFee) elFee.textContent = formatIDR(totalFee);
  if (elNet) {
    elNet.textContent = `${sign}${formatIDR(Math.abs(netPnl))}`;
    elNet.className = `pnl-card-val mono bold ${cls}`;
  }
}

function onJournalTickerChange(val) {
  const clean = (val || '').trim().toUpperCase();
  // If in watchlist, auto-fill name & sector
  const item = watchlistState.watchlistItems.find(i => i.ticker === clean);
  if (item) {
    const elName = document.getElementById('entry-name');
    const elSector = document.getElementById('entry-sector');
    if (elName && !elName.value) elName.value = item.name;
    if (elSector && !elSector.value) elSector.value = item.sector;
  }
}

// 11. EXPORT & BACKUP/RESTORE
function exportJournalCSV() {
  window.location.href = '/api/journal/export/csv';
  if (typeof showToast === 'function') showToast('Mengunduh Jurnal Trading CSV...', 'info');
}

function exportJournalBackupJSON() {
  window.location.href = '/api/journal/backup';
  if (typeof showToast === 'function') showToast('Mengunduh Backup JSON...', 'info');
}

function triggerRestoreBackupInput() {
  const input = document.getElementById('wl-restore-file-input');
  if (input) input.click();
}

async function handleRestoreBackupFile(e) {
  const file = e.target.files[0];
  if (!file) return;

  if (!confirm(`Apakah Anda yakin ingin memulihkan data dari file "${file.name}"? Data yang ada akan disinkronkan.`)) {
    e.target.value = '';
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/journal/restore', {
      method: 'POST',
      body: formData
    });
    const json = await res.json();

    if (json.status === 'success') {
      if (typeof showToast === 'function') {
        showToast(`Restore berhasil: ${json.result.restored_watchlist} watchlist, ${json.result.restored_trades} trade!`, 'success');
      }
      loadWatchlistAndJournal();
    } else {
      if (typeof showToast === 'function') showToast(json.message || 'Gagal memulihkan backup', 'error');
    }
  } catch (err) {
    console.error('Restore backup error:', err);
    if (typeof showToast === 'function') showToast('Format file backup tidak valid', 'error');
  } finally {
    e.target.value = '';
  }
}

// 12. SETTINGS MODAL
function openPortfolioSettingsModal() {
  const modal = document.getElementById('modal-trade-journal');
  const formEntry = document.getElementById('form-journal-entry');
  const formClose = document.getElementById('form-journal-close');
  const formSettings = document.getElementById('form-journal-settings');

  if (!modal || !formSettings) return;

  formEntry.classList.add('hidden');
  if (formClose) formClose.classList.add('hidden');
  formSettings.classList.remove('hidden');

  document.getElementById('journal-modal-icon').textContent = '⚙️';
  document.getElementById('journal-modal-title').textContent = 'Pengaturan Portofolio & Komisi';
  const badge = document.getElementById('journal-modal-mode-badge');
  if (badge) {
    badge.className = 'journal-mode-pill open';
    badge.textContent = 'KONFIGURASI';
  }

  // Fetch current settings
  fetch('/api/settings/money-management')
    .then(res => res.json())
    .then(json => {
      if (json.status === 'success' && json.data) {
        document.getElementById('set-capital').value = json.data.portfolio_capital || 100000000;
        document.getElementById('set-risk-pct').value = json.data.risk_per_trade_pct || 1.0;
        document.getElementById('set-max-cap').value = json.data.max_position_cap_pct || 20.0;
        document.getElementById('set-fee-buy').value = json.data.broker_fee_buy_pct || 0.15;
        document.getElementById('set-fee-sell').value = json.data.broker_fee_sell_pct || 0.25;
      }
    });

  modal.classList.remove('hidden');
}

async function submitJournalSettings(e) {
  e.preventDefault();

  const payload = {
    portfolio_capital: parseFloat(document.getElementById('set-capital').value) || 100000000,
    risk_per_trade_pct: parseFloat(document.getElementById('set-risk-pct').value) || 1.0,
    max_position_cap_pct: parseFloat(document.getElementById('set-max-cap').value) || 20.0,
    broker_fee_buy_pct: parseFloat(document.getElementById('set-fee-buy').value) || 0.15,
    broker_fee_sell_pct: parseFloat(document.getElementById('set-fee-sell').value) || 0.25
  };

  try {
    const res = await fetch('/api/settings/money-management', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const json = await res.json();
    if (json.status === 'success') {
      closeTradeJournalModal();
      if (typeof showToast === 'function') showToast('Pengaturan berhasil disimpan!', 'success');
      // If position calculator is open, update it
      recomputePositionSizing();
    }
  } catch (err) {
    console.error('Settings save error:', err);
  }
}

function viewTradeEvaluationModal(tradeId) {
  const trade = watchlistState.trades.find(t => t.id === tradeId);
  if (!trade) return;
  alert(`📝 EVALUASI TRADING (${trade.ticker}):\n\nStrategi: ${trade.setup_type}\nBeli: Rp ${trade.buy_price.toLocaleString('id-ID')} (${trade.buy_date})\nJual: Rp ${trade.exit_price.toLocaleString('id-ID')} (${trade.exit_date})\nAlasan Exit: ${trade.exit_reason}\nNet P&L: Rp ${trade.net_pnl.toLocaleString('id-ID')} (${trade.realized_pnl_pct}%)\n\nCatatan Evaluasi:\n${trade.notes || 'Tidak ada catatan'}`);
}

function escapeQuotes(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}
