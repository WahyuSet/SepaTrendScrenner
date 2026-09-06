// ============================================================================
// SIGNAL BACKTEST & ACCURACY LAB CONTROLLER (backtest.js)
// Financial Terminal Pro Architecture
// ============================================================================

const backtestState = {
  summary: null,
  trades: [],
  filteredTrades: [],
  selectedStrategy: 'ALL',
  selectedStatus: 'ALL',
  selectedPeriod: 2,
  currentTicker: null,
  searchQuery: '',
  currentPage: 1,
  pageSize: 20
};

document.addEventListener('DOMContentLoaded', () => {
  // Backtest Lab is lazy-loaded on first navigation or initial run
});

// 1. DATA INITIALIZATION & LOADING
async function loadBacktestData(period = null) {
  if (period !== null) {
    backtestState.selectedPeriod = period;
  }
  const years = backtestState.selectedPeriod;

  try {
    // 1. Fetch Summary Benchmark
    const resSummary = await fetch(`/api/backtest/summary?years=${years}`);
    if (resSummary.ok) {
      const jsonSummary = await resSummary.json();
      if (jsonSummary.status === 'success') {
        backtestState.summary = jsonSummary;
        renderBacktestKPIs(jsonSummary);
        renderStrategyComparison(jsonSummary.breakdown);
      }
    }

    // 2. Fetch Initial Trade Log
    const resTrades = await fetch(`/api/backtest/trades?run_id=benchmark_${years}y&limit=300`);
    if (resTrades.ok) {
      const jsonTrades = await resTrades.json();
      if (jsonTrades.status === 'success') {
        backtestState.trades = jsonTrades.trades || [];
        backtestState.currentTicker = null;
        updateBacktestScopeUI(null);
        filterAndRenderBacktestTrades();
      }
    }
  } catch (err) {
    console.error('Error loading backtest data:', err);
    if (typeof showToast === 'function') {
      showToast('Gagal memuat data backtest', 'error');
    }
  }
}

// 2. RENDERING TOP KPI CARDS
function renderBacktestKPIs(data) {
  if (!data) return;

  // Win Rate
  const elWr = document.getElementById('kpi-winrate-val');
  const elWrSub = document.getElementById('kpi-winrate-sub');
  if (elWr) elWr.textContent = `${data.win_rate || 0.0}%`;
  if (elWrSub) {
    elWrSub.textContent = `${data.win_trades || 0} Menang / ${data.loss_trades || 0} Kalah (Total ${data.total_trades || 0} Sinyal)`;
  }

  // Profit Factor
  const elPf = document.getElementById('kpi-pf-val');
  const elPfSub = document.getElementById('kpi-pf-sub');
  if (elPf) {
    elPf.textContent = `${data.profit_factor || 0.00}`;
    elPf.className = `stat-value mono ${(data.profit_factor >= 1.5) ? 'text-gain' : ((data.profit_factor < 1.0) ? 'text-danger' : '')}`;
  }
  if (elPfSub) {
    elPfSub.textContent = (data.profit_factor >= 2.0) ? '🌟 Kategori Sangat Unggul (> 2.0)' :
                          (data.profit_factor >= 1.5) ? '✅ Kategori Sehat & Profitabel' : '⚠️ Perlu Optimasi Ketat';
  }

  // Payoff Ratio
  const elPayoff = document.getElementById('kpi-payoff-val');
  const elPayoffSub = document.getElementById('kpi-payoff-sub');
  if (elPayoff) elPayoff.textContent = `${data.payoff_ratio || 0.00} : 1`;
  if (elPayoffSub) {
    elPayoffSub.textContent = `Avg Win: +${data.avg_gain_pct || 0.0}% | Loss: -${data.avg_loss_pct || 0.0}%`;
  }

  // Avg Holding
  const elHolding = document.getElementById('kpi-holding-val');
  if (elHolding) elHolding.textContent = `${data.avg_holding_days || 0.0}`;

  // Max Drawdown
  const elMdd = document.getElementById('kpi-mdd-val');
  if (elMdd) elMdd.textContent = `-${data.max_drawdown || 0.0}%`;
}

// 3. RENDERING STRATEGY COMPARISON & COUNTERS
function renderStrategyComparison(breakdown) {
  if (!breakdown) return;

  // 1. Momentum Breakout
  const mb = breakdown['MOMENTUM_BREAKOUT'] || { total: 0, wins: 0, win_rate: 0.0, avg_net_return: 0.0 };
  const elMbWr = document.getElementById('strat-mb-wr');
  const elMbRet = document.getElementById('strat-mb-ret');
  const elMbTot = document.getElementById('strat-mb-total-badge');
  const cntMb = document.getElementById('cnt-bt-mb');

  if (elMbWr) elMbWr.textContent = `${mb.win_rate}% WR`;
  if (elMbRet) {
    const sign = mb.avg_net_return >= 0 ? '+' : '';
    elMbRet.textContent = `${sign}${mb.avg_net_return}%`;
    elMbRet.className = `h-ret mono ${mb.avg_net_return >= 0 ? 'text-gain' : 'text-danger'}`;
  }
  if (elMbTot) elMbTot.textContent = `(${mb.total} trade)`;
  if (cntMb) cntMb.textContent = mb.total;

  // 2. Pullback / RBS
  const pb = breakdown['PULLBACK_RBS'] || { total: 0, wins: 0, win_rate: 0.0, avg_net_return: 0.0 };
  const elPbWr = document.getElementById('strat-pb-wr');
  const elPbRet = document.getElementById('strat-pb-ret');
  const elPbTot = document.getElementById('strat-pb-total-badge');
  const cntPb = document.getElementById('cnt-bt-pb');

  if (elPbWr) elPbWr.textContent = `${pb.win_rate}% WR`;
  if (elPbRet) {
    const sign = pb.avg_net_return >= 0 ? '+' : '';
    elPbRet.textContent = `${sign}${pb.avg_net_return}%`;
    elPbRet.className = `h-ret mono ${pb.avg_net_return >= 0 ? 'text-gain' : 'text-danger'}`;
  }
  if (elPbTot) elPbTot.textContent = `(${pb.total} trade)`;
  if (cntPb) cntPb.textContent = pb.total;

  // 3. Base Building / VCP
  const bb = breakdown['BASE_BUILDING'] || { total: 0, wins: 0, win_rate: 0.0, avg_net_return: 0.0 };
  const elBbWr = document.getElementById('strat-bb-wr');
  const elBbRet = document.getElementById('strat-bb-ret');
  const elBbTot = document.getElementById('strat-bb-total-badge');
  const cntBb = document.getElementById('cnt-bt-bb');

  if (elBbWr) elBbWr.textContent = `${bb.win_rate}% WR`;
  if (elBbRet) {
    const sign = bb.avg_net_return >= 0 ? '+' : '';
    elBbRet.textContent = `${sign}${bb.avg_net_return}%`;
    elBbRet.className = `h-ret mono ${bb.avg_net_return >= 0 ? 'text-gain' : 'text-danger'}`;
  }
  if (elBbTot) elBbTot.textContent = `(${bb.total} trade)`;
  if (cntBb) cntBb.textContent = bb.total;

  // Total All counter
  const cntAll = document.getElementById('cnt-bt-all');
  if (cntAll) cntAll.textContent = (mb.total + pb.total + bb.total);
}

// 4. ON-DEMAND TICKER SIMULATOR (< 1s)
async function runOnDemandTickerBacktest(targetSymbol = null) {
  const input = document.getElementById('bt-ticker-input');
  const ticker = (targetSymbol || (input ? input.value : '')).trim().toUpperCase();

  if (!ticker) {
    if (typeof showToast === 'function') showToast('Masukkan kode ticker saham (e.g. BBCA)', 'info');
    return;
  }

  if (input) input.value = ticker;

  // Highlight active chip
  document.querySelectorAll('.chip-btn').forEach(btn => {
    if (btn.textContent.trim() === ticker) {
      btn.style.background = '#0284c7';
      btn.style.color = '#ffffff';
      btn.style.borderColor = '#0284c7';
    } else if (!btn.classList.contains('reset')) {
      btn.style.background = '';
      btn.style.color = '';
      btn.style.borderColor = '';
    }
  });

  const years = backtestState.selectedPeriod;

  // Show loading indicator
  const tbody = document.getElementById('bt-trades-tbody');
  if (tbody) {
    tbody.innerHTML = `
      <tr>
        <td colspan="14" class="empty-state">
          <div class="empty-state-icon">⏳</div>
          <h3>Menjalankan simulasi point-in-time untuk ${ticker}...</h3>
          <p>Mengevaluasi sinyal Quality Setup & VCP selama ${years} tahun terakhir...</p>
        </td>
      </tr>
    `;
  }

  try {
    const res = await fetch(`/api/backtest/ticker?ticker=${ticker}&years=${years}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();

    if (json.status === 'success') {
      backtestState.currentTicker = ticker;
      backtestState.trades = json.trades || [];
      backtestState.currentPage = 1;

      // Update Scope UI
      updateBacktestScopeUI(ticker, json.stats.total_trades);

      // Render KPIs & Breakdown
      renderBacktestKPIs(json.stats);
      renderStrategyComparison(json.stats.breakdown);

      // Filter and render table
      filterAndRenderBacktestTrades();

      if (typeof showToast === 'function') {
        if (json.stats && json.stats.total_trades > 0) {
          showToast(`Simulasi ${ticker} selesai (${json.stats.total_trades} trade ditemukan, Win Rate: ${json.stats.win_rate}%)`, 'success');
        } else {
          showToast(`Simulasi ${ticker} selesai: 0 sinyal terpicu pada rentang ${years} tahun (Filter likuiditas / belum ada setup)`, 'info');
        }
      }
    } else {
      if (typeof showToast === 'function') {
        showToast(json.message || `Gagal simulasi ${ticker}`, 'warning');
      }
      resetToUniverseBenchmark();
    }
  } catch (err) {
    console.error(`Error simulating ${ticker}:`, err);
    if (typeof showToast === 'function') {
      showToast(`Gagal memproses simulasi untuk ${ticker}`, 'error');
    }
    resetToUniverseBenchmark();
  }
}

function quickInspectTicker(ticker) {
  runOnDemandTickerBacktest(ticker);
}

function resetToUniverseBenchmark() {
  const input = document.getElementById('bt-ticker-input');
  if (input) input.value = '';

  document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.style.background = '';
    btn.style.color = '';
    btn.style.borderColor = '';
  });

  backtestState.currentTicker = null;
  backtestState.currentPage = 1;
  loadBacktestData();

  if (typeof showToast === 'function') {
    showToast('Kembali ke Universe Benchmark agregat IHSG', 'info');
  }
}

function updateBacktestScopeUI(ticker, count = 0) {
  const scopeBadge = document.getElementById('backtest-active-scope-badge');
  const scopeText = document.getElementById('backtest-scope-text');
  const resetBtn = document.getElementById('btn-reset-ticker-filter');
  const tableTitle = document.getElementById('bt-table-title');

  if (ticker) {
    if (scopeBadge) scopeBadge.className = 'deck-scope-pill ticker-active';
    if (scopeText) scopeText.textContent = `SIMULASI: ${ticker} (${count} TRADES)`;
    if (resetBtn) resetBtn.classList.remove('hidden');
    if (tableTitle) tableTitle.textContent = `Histori Transaksi Sinyal — ${ticker}`;
  } else {
    if (scopeBadge) scopeBadge.className = 'deck-scope-pill';
    if (scopeText) scopeText.textContent = `BENCHMARK UNIVERSE (${backtestState.trades.length} TRADES)`;
    if (resetBtn) resetBtn.classList.add('hidden');
    if (tableTitle) tableTitle.textContent = 'Histori Transaksi Sinyal';
  }
}

// 5. PERIOD & STRATEGY FILTERS
function onBacktestPeriodChange(years) {
  backtestState.selectedPeriod = parseInt(years, 10);
  if (backtestState.currentTicker) {
    runOnDemandTickerBacktest(backtestState.currentTicker);
  } else {
    loadBacktestData(backtestState.selectedPeriod);
  }
}

function setBacktestStrategyFilter(strategy) {
  backtestState.selectedStrategy = strategy;
  backtestState.currentPage = 1;

  // Update segmented tabs
  const tabGroup = document.getElementById('bt-strategy-pills');
  if (tabGroup) {
    tabGroup.querySelectorAll('.segmented-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-strategy') === strategy);
    });
  }

  // Update horizon cards highlight
  document.querySelectorAll('.horizon-card').forEach(card => {
    const onclickStr = card.getAttribute('onclick') || '';
    card.classList.toggle('active', onclickStr.includes(strategy));
  });

  filterAndRenderBacktestTrades();
}

function onBacktestStatusFilterChange(status) {
  backtestState.selectedStatus = status;
  backtestState.currentPage = 1;

  const resetBtn = document.getElementById('bt-reset-filter-btn');
  if (resetBtn) {
    if (status !== 'ALL' || backtestState.searchQuery) {
      resetBtn.classList.remove('hidden');
    } else {
      resetBtn.classList.add('hidden');
    }
  }

  filterAndRenderBacktestTrades();
}

function filterBacktestTable() {
  const searchInput = document.getElementById('bt-trade-search');
  backtestState.searchQuery = (searchInput ? searchInput.value : '').trim().toUpperCase();
  backtestState.currentPage = 1;

  const resetBtn = document.getElementById('bt-reset-filter-btn');
  if (resetBtn) {
    if (backtestState.searchQuery || backtestState.selectedStatus !== 'ALL') {
      resetBtn.classList.remove('hidden');
    } else {
      resetBtn.classList.add('hidden');
    }
  }

  filterAndRenderBacktestTrades();
}

function resetBacktestTableFilters() {
  const searchInput = document.getElementById('bt-trade-search');
  if (searchInput) searchInput.value = '';
  backtestState.searchQuery = '';

  const statusSelect = document.getElementById('bt-status-filter');
  if (statusSelect) statusSelect.value = 'ALL';
  backtestState.selectedStatus = 'ALL';

  const resetBtn = document.getElementById('bt-reset-filter-btn');
  if (resetBtn) resetBtn.classList.add('hidden');

  backtestState.currentPage = 1;
  filterAndRenderBacktestTrades();
}

function refreshBacktestBenchmark() {
  if (typeof showToast === 'function') showToast('Memuat ulang benchmark agregat...', 'info');
  loadBacktestData();
}

// 6. FILTERING & TABLE RENDERING
function filterAndRenderBacktestTrades() {
  let list = backtestState.trades || [];

  // 1. Filter strategy
  if (backtestState.selectedStrategy !== 'ALL') {
    list = list.filter(t => t.setup_type === backtestState.selectedStrategy);
  }

  // 2. Filter status
  if (backtestState.selectedStatus !== 'ALL') {
    if (backtestState.selectedStatus === 'WIN') {
      list = list.filter(t => t.is_win === 1);
    } else if (backtestState.selectedStatus === 'LOSS') {
      list = list.filter(t => t.is_win === 0);
    } else {
      list = list.filter(t => t.status === backtestState.selectedStatus);
    }
  }

  // 3. Search query
  if (backtestState.searchQuery) {
    list = list.filter(t => t.ticker.includes(backtestState.searchQuery));
  }

  backtestState.filteredTrades = list;
  renderBacktestTableRows();
}

function renderBacktestTableRows() {
  const tbody = document.getElementById('bt-trades-tbody');
  const countLabel = document.getElementById('bt-trades-displayed-count');
  const totalLabel = document.getElementById('bt-trades-total-count');
  const badgeCount = document.getElementById('bt-trades-count-badge');

  if (!tbody) return;

  const total = backtestState.filteredTrades.length;
  if (totalLabel) totalLabel.textContent = backtestState.trades.length;
  if (badgeCount) badgeCount.textContent = `${total} Transaksi`;

  if (total === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="14" class="empty-state">
          <div class="empty-state-icon">📂</div>
          <h3>Tidak ada transaksi yang cocok dengan filter</h3>
          <p>Coba ubah filter setup atau status keluar pada toolbar di atas.</p>
        </td>
      </tr>
    `;
    if (countLabel) countLabel.textContent = '0';
    renderBacktestPagination(0);
    return;
  }

  // Pagination slice
  const startIdx = (backtestState.currentPage - 1) * backtestState.pageSize;
  const endIdx = Math.min(startIdx + backtestState.pageSize, total);
  const pageItems = backtestState.filteredTrades.slice(startIdx, endIdx);

  if (countLabel) countLabel.textContent = `${pageItems.length}`;

  let html = '';
  pageItems.forEach((t, idx) => {
    const rowNum = startIdx + idx + 1;

    // Check if pinned in watchlist
    const isPinned = (typeof watchlistState !== 'undefined' && watchlistState.items && watchlistState.items.has(t.ticker));
    const starClass = isPinned ? 'pinned' : '';

    // Setup Badge
    let setupBadge = '';
    if (t.setup_type === 'MOMENTUM_BREAKOUT') {
      setupBadge = `<span class="badge-setup-type breakout">⚡ Breakout (7D)</span>`;
    } else if (t.setup_type === 'PULLBACK_RBS') {
      setupBadge = `<span class="badge-setup-type pullback">🔄 Pullback (12D)</span>`;
    } else {
      setupBadge = `<span class="badge-setup-type base">💎 Base (20D)</span>`;
    }

    // Status Badge
    let statusBadge = '';
    if (t.status === 'TP2_HIT') {
      statusBadge = `<span class="badge-bt-status tp2">🚀 Runner (TP2)</span>`;
    } else if (t.status === 'TP1_HIT') {
      statusBadge = `<span class="badge-bt-status tp1">🎯 Target 1 Hit</span>`;
    } else if (t.status === 'SL_HIT') {
      statusBadge = `<span class="badge-bt-status sl">🛑 Cut Loss (SL)</span>`;
    } else {
      statusBadge = `<span class="badge-bt-status expired">⏱️ Expired Exit</span>`;
    }

    // Return formatting
    const sign = t.net_return_pct >= 0 ? '+' : '';
    const retClass = t.net_return_pct >= 0 ? 'text-gain' : 'text-danger';

    html += `
      <tr>
        <td class="text-center text-muted" style="font-size: 11px;">${rowNum}</td>
        <td>
          <div class="ticker-cell-wrapper">
            <button class="btn-star-pin ${starClass}" onclick="event.stopPropagation(); toggleWatchlistPin('${t.ticker}', '${t.ticker}', 'IDX', 'BACKTEST')" title="Pin ke Watchlist Pribadi">
              ★
            </button>
            <span class="ticker-text font-bold" onclick="showStockDetail('${t.ticker}')" style="cursor: pointer; color: #0284c7; font-family: var(--font-mono); font-weight: 700; font-size: 13px;">
              ${t.ticker}
            </span>
          </div>
        </td>
        <td>${setupBadge}</td>
        <td class="text-center mono" style="font-size: 11px;">${t.signal_date}</td>
        <td class="text-right mono font-bold">Rp ${t.entry_price.toLocaleString('id-ID')}</td>
        <td class="text-right mono text-muted">Rp ${t.stop_loss.toLocaleString('id-ID')}</td>
        <td class="text-right mono text-gain">Rp ${t.target_1.toLocaleString('id-ID')}</td>
        <td class="text-center mono" style="font-size: 11px;">${t.exit_date}</td>
        <td class="text-right mono font-bold">Rp ${t.exit_price.toLocaleString('id-ID')}</td>
        <td class="text-center mono font-bold">${t.holding_days} d</td>
        <td class="text-center">${statusBadge}</td>
        <td class="text-right mono font-bold ${retClass}">
          ${sign}${t.net_return_pct.toFixed(2)}%
        </td>
        <td class="text-center">
          <span class="mfe-mae-pill">
            <span class="mfe">+${t.mfe_pct.toFixed(1)}%</span> / <span class="mae">${t.mae_pct.toFixed(1)}%</span>
          </span>
        </td>
        <td class="text-center">
          <div class="row-actions-group">
            <button class="btn-table-action" onclick="event.stopPropagation(); openPositionCalculator('${t.ticker}', ${t.entry_price}, ${t.stop_loss}, ${t.target_1}, ${t.target_2 || t.target_1})" title="Hitung Position Sizing Minervini">
              🧮
            </button>
          </div>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
  renderBacktestPagination(total);
}

function renderBacktestPagination(total) {
  const wrap = document.getElementById('bt-pagination-wrap');
  if (!wrap) return;

  const totalPages = Math.ceil(total / backtestState.pageSize);
  if (totalPages <= 1) {
    wrap.innerHTML = '';
    return;
  }

  let html = '';
  html += `
    <button class="btn-page ${backtestState.currentPage === 1 ? 'disabled' : ''}" 
      onclick="changeBacktestPage(${backtestState.currentPage - 1})" ${backtestState.currentPage === 1 ? 'disabled' : ''}>
      ◀ Prev
    </button>
  `;

  html += `<span class="page-indicator">Halaman ${backtestState.currentPage} dari ${totalPages}</span>`;

  html += `
    <button class="btn-page ${backtestState.currentPage === totalPages ? 'disabled' : ''}" 
      onclick="changeBacktestPage(${backtestState.currentPage + 1})" ${backtestState.currentPage === totalPages ? 'disabled' : ''}>
      Next ▶
    </button>
  `;

  wrap.innerHTML = html;
}

function changeBacktestPage(newPage) {
  const totalPages = Math.ceil(backtestState.filteredTrades.length / backtestState.pageSize);
  if (newPage < 1 || newPage > totalPages) return;
  backtestState.currentPage = newPage;
  renderBacktestTableRows();
}

// 7. EXPORT BACKTEST TRADES TO CSV
function exportBacktestTradesCSV() {
  const trades = backtestState.filteredTrades;
  if (!trades || trades.length === 0) {
    if (typeof showToast === 'function') showToast('Tidak ada data transaksi untuk diekspor', 'info');
    return;
  }

  const headers = [
    'Ticker', 'Setup Type', 'Signal Date', 'Entry Date', 'Entry Price',
    'Stop Loss', 'Target 1', 'Target 2', 'Exit Date', 'Exit Price',
    'Holding Days', 'Status', 'Gross Return Pct', 'Net Return Pct',
    'Is Win', 'MFE Pct', 'MAE Pct'
  ];

  let csvContent = 'data:text/csv;charset=utf-8,' + headers.join(',') + '\n';
  trades.forEach(t => {
    const row = [
      t.ticker, t.setup_type, t.signal_date, t.entry_date, t.entry_price,
      t.stop_loss, t.target_1, t.target_2, t.exit_date, t.exit_price,
      t.holding_days, t.status, t.gross_return_pct, t.net_return_pct,
      t.is_win, t.mfe_pct, t.mae_pct
    ];
    csvContent += row.join(',') + '\n';
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  const filename = `tirexxz_backtest_${backtestState.currentTicker || 'benchmark'}_${new Date().toISOString().split('T')[0]}.csv`;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  if (typeof showToast === 'function') {
    showToast(`Ekspor CSV ${filename} berhasil!`, 'success');
  }
}
