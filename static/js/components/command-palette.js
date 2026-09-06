// ============================================================================
// COMMAND PALETTE CONTROLLER (CTRL + K)
// ============================================================================

let cmdSelectedIndex = 0;
let cmdFilteredItems = [];
let idxMasterTickers = [];
let idxMasterTickersMap = {};

// Preload 941 IDX Master Tickers on script load
async function loadIdxMasterTickers() {
  try {
    const res = await fetch('/api/idx/tickers');
    if (res.ok) {
      const data = await res.json();
      if (data.status === 'success' && Array.isArray(data.data)) {
        idxMasterTickers = data.data;
        idxMasterTickersMap = {};
        data.data.forEach(item => {
          idxMasterTickersMap[item.ticker] = item;
        });
        window.idxMasterTickers = idxMasterTickers;
        window.idxMasterTickersMap = idxMasterTickersMap;
      }
    }
  } catch (err) {
    console.error('Failed to load IDX master tickers:', err);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadIdxMasterTickers);
} else {
  loadIdxMasterTickers();
}

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    openCommandPalette();
  }
});

function openCommandPalette() {
  const dialog = document.getElementById('cmd-palette');
  if (!dialog) return;

  if (typeof dialog.showModal === 'function') {
    dialog.showModal();
  } else {
    dialog.setAttribute('open', '');
  }

  const input = document.getElementById('cmd-input');
  if (input) {
    input.value = '';
    setTimeout(() => input.focus(), 50);
  }
  handleCmdSearch('');
}

function closeCommandPalette() {
  const dialog = document.getElementById('cmd-palette');
  if (!dialog) return;

  if (typeof dialog.close === 'function') {
    dialog.close();
  } else {
    dialog.removeAttribute('open');
  }
}

function handleCmdBackdropClick(event) {
  const dialog = document.getElementById('cmd-palette');
  if (event.target === dialog) {
    closeCommandPalette();
  }
}

function getBaseCommands() {
  return [
    {
      id: 'nav-sepa',
      group: 'Navigasi Screener',
      icon: '📈',
      title: 'Beralih ke SEPA Trend Screener',
      desc: 'Minervini Stage 2 Filter (8 Kriteria Evaluasi)',
      badge: 'Menu',
      action: () => switchScreener('sepa')
    },
    {
      id: 'nav-rsi',
      group: 'Navigasi Screener',
      icon: '📉',
      title: 'Beralih ke RSI Divergence Screener',
      desc: 'Sinyal Bullish Reversal & Trend Continuation',
      badge: 'Menu',
      action: () => switchScreener('rsi-div')
    },
    {
      id: 'nav-prebreakout',
      group: 'Navigasi Screener',
      icon: '🎯',
      title: 'Beralih ke Pre-Breakout Screener',
      desc: 'Ready to Breakout Setup (7 Kriteria Konsolidasi)',
      badge: 'Menu',
      action: () => switchScreener('prebreakout')
    },
    {
      id: 'nav-quality',
      group: 'Navigasi Screener',
      icon: '💎',
      title: 'Beralih ke Quality Setup Screener',
      desc: '100-Pt Momentum & Setup Pullback / Breakout (941 IDX)',
      badge: 'Menu',
      action: () => switchScreener('quality')
    },
    {
      id: 'act-scan',
      group: 'Aksi Cepat',
      icon: '⚡',
      title: 'Jalankan Scan IDX Sekarang',
      desc: 'Mulai background screening untuk seluruh universe saham IDX',
      badge: 'Action',
      action: () => triggerScan()
    },
    {
      id: 'act-refresh',
      group: 'Aksi Cepat',
      icon: '🔄',
      title: 'Muat Ulang Cache Hasil Scan',
      desc: 'Perbarui data tampilan dari server untuk semua screener',
      badge: 'Action',
      action: () => Promise.all([loadCachedResults(), loadRsiResults(), loadPreBreakoutResults()])
    },
    {
      id: 'act-copy-sepa',
      group: 'Aksi Cepat',
      icon: '📋',
      title: 'Salin Watchlist SEPA Trend ke TradingView',
      desc: 'Copy semua ticker SEPA Stage 2 & Watchlist format IDX:TICKER',
      badge: 'Tool',
      action: () => copyTradingViewWatchlist('sepa')
    },
    {
      id: 'act-copy-rsi',
      group: 'Aksi Cepat',
      icon: '📋',
      title: 'Salin Watchlist RSI Divergence ke TradingView',
      desc: 'Copy semua ticker RSI Divergence format IDX:TICKER',
      badge: 'Tool',
      action: () => copyTradingViewWatchlist('rsi')
    },
    {
      id: 'act-copy-prebreakout',
      group: 'Aksi Cepat',
      icon: '📋',
      title: 'Salin Watchlist Pre-Breakout ke TradingView',
      desc: 'Copy semua ticker Pre-Breakout format IDX:TICKER',
      badge: 'Tool',
      action: () => copyTradingViewWatchlist('prebreakout')
    },
    {
      id: 'act-csv-sepa',
      group: 'Aksi Cepat',
      icon: '📥',
      title: 'Unduh Laporan CSV SEPA Trend',
      desc: 'Export file spreadsheet tabel SEPA',
      badge: 'CSV',
      action: () => exportTableToCsv('sepa')
    },
    {
      id: 'act-csv-rsi',
      group: 'Aksi Cepat',
      icon: '📥',
      title: 'Unduh Laporan CSV RSI Divergence',
      desc: 'Export file spreadsheet tabel RSI',
      badge: 'CSV',
      action: () => exportTableToCsv('rsi')
    },
    {
      id: 'act-csv-prebreakout',
      group: 'Aksi Cepat',
      icon: '📥',
      title: 'Unduh Laporan CSV Pre-Breakout',
      desc: 'Export file spreadsheet tabel Pre-Breakout',
      badge: 'CSV',
      action: () => exportTableToCsv('prebreakout')
    }
  ];
}

function handleCmdSearch(query) {
  const q = (query || '').trim().toLowerCase();
  const cleanQ = q.toUpperCase();
  const baseCommands = getBaseCommands();

  let items = [];

  // Filter base commands
  if (q) {
    items = baseCommands.filter(c =>
      c.title.toLowerCase().includes(q) ||
      c.desc.toLowerCase().includes(q) ||
      c.group.toLowerCase().includes(q)
    );
  } else {
    items = [...baseCommands];
  }

  // Exact 4-letter ticker lookup (strict validation against 941 IDX master emiten)
  const isFourLetter = cleanQ.length === 4 && /^[A-Z]{4}$/.test(cleanQ);

  if (isFourLetter) {
    const meta = idxMasterTickersMap[cleanQ];
    if (meta) {
      // Valid IDX ticker
      items.unshift({
        id: `api-lookup-${cleanQ}`,
        group: 'Riset Saham Komprehensif (IDX Edge PRO)',
        icon: '🔍',
        title: `Buka Analisa Komprehensif: ${cleanQ} — ${meta.name}`,
        desc: `${meta.sector} · Bandarmologi, Top Brokers & Trading Plan`,
        badge: 'IDX PRO',
        action: () => {
          closeCommandPalette();
          openStockDetailModal(cleanQ, meta);
        }
      });
    } else {
      // 4 letters but NOT registered in IDX (e.g. WWWW, XYZW) -> Block & warn!
      items.unshift({
        id: `api-lookup-invalid-${cleanQ}`,
        group: 'Validasi Emiten IDX',
        icon: '⚠️',
        title: `Emiten '${cleanQ}' Tidak Terdaftar di BEI`,
        desc: `Kode emiten ini tidak ditemukan dalam daftar 941 perusahaan resmi IDX.`,
        badge: 'Tidak Valid',
        isInvalid: true,
        action: () => {
          if (typeof showToast === 'function') {
            showToast(`Kode emiten '${cleanQ}' tidak terdaftar di Bursa Efek Indonesia (IDX)`, 'warning');
          }
        }
      });
    }
  }

  // Add matching stocks from loaded screener data
  const stockMatches = [];
  const seenTickers = new Set();

  // 1. Match from SEPA
  if (typeof state !== 'undefined' && state.allResults && state.allResults.length > 0) {
    state.allResults.forEach(s => {
      if (seenTickers.has(s.ticker)) return;
      if (
        !q ||
        s.ticker.toLowerCase().includes(q) ||
        (s.name && s.name.toLowerCase().includes(q)) ||
        (s.sector && s.sector.toLowerCase().includes(q))
      ) {
        seenTickers.add(s.ticker);
        stockMatches.push({
          id: `stock-${s.ticker}`,
          group: 'Emiten Terkualifikasi (SEPA)',
          icon: s.status === 'CONFIRMED' ? '⚡' : '⭐',
          title: `${s.ticker} — ${s.name}`,
          desc: `${s.sector} · Rp ${s.price.toLocaleString('id-ID')} · Score ${s.total_score}/8 · RS ${s.rs_score}`,
          badge: s.status,
          action: () => {
            switchScreener('sepa');
            openCriteriaModal(s.ticker);
          }
        });
      }
    });
  }

  // 2. Match from RSI Divergence
  if (typeof rsiState !== 'undefined' && rsiState.allResults && rsiState.allResults.length > 0) {
    rsiState.allResults.forEach(s => {
      if (seenTickers.has(s.ticker)) return;
      if (
        !q ||
        s.ticker.toLowerCase().includes(q) ||
        (s.name && s.name.toLowerCase().includes(q)) ||
        (s.sector && s.sector.toLowerCase().includes(q))
      ) {
        seenTickers.add(s.ticker);
        stockMatches.push({
          id: `rsi-stock-${s.ticker}`,
          group: 'Emiten RSI Divergence',
          icon: s.divergence_type === 'REGULAR_BULL' ? '🔄' : '🚀',
          title: `${s.ticker} — ${s.name}`,
          desc: `${s.divergence_label} · RSI ${s.rsi} · ${s.recency_text}`,
          badge: s.divergence_label,
          action: () => {
            switchScreener('rsi-div');
            openRsiModal(s.ticker);
          }
        });
      }
    });
  }

  // 3. Match from Pre-Breakout
  if (typeof prebreakoutState !== 'undefined' && prebreakoutState.allResults && prebreakoutState.allResults.length > 0) {
    prebreakoutState.allResults.forEach(s => {
      if (seenTickers.has(s.ticker)) return;
      if (
        !q ||
        s.ticker.toLowerCase().includes(q) ||
        (s.name && s.name.toLowerCase().includes(q)) ||
        (s.sector && s.sector.toLowerCase().includes(q))
      ) {
        seenTickers.add(s.ticker);
        stockMatches.push({
          id: `pb-stock-${s.ticker}`,
          group: 'Emiten Pre-Breakout Setup',
          icon: s.status === 'READY' ? '🎯' : '⭐',
          title: `${s.ticker} — ${s.name}`,
          desc: `${s.status_label} · Skor ${s.total_score}/7 · Jarak Res -${s.dist_res_pct}%`,
          badge: s.status_label,
          action: () => {
            switchScreener('prebreakout');
            openPreBreakoutModal(s.ticker);
          }
        });
      }
    });
  }

  // 4. Autocomplete from Master Tickers (941 IDX stocks)
  if (q && q.length >= 2 && idxMasterTickers.length > 0) {
    const masterMatches = idxMasterTickers
      .filter(m => {
        if (seenTickers.has(m.ticker)) return false;
        if (isFourLetter && m.ticker === cleanQ) return false; // Already handled above
        return m.ticker.startsWith(cleanQ) || (q.length >= 3 && m.name.toLowerCase().includes(q));
      })
      .slice(0, 8);

    masterMatches.forEach(m => {
      seenTickers.add(m.ticker);
      stockMatches.push({
        id: `master-${m.ticker}`,
        group: 'Daftar Seluruh Saham BEI (IDX Master)',
        icon: '🏢',
        title: `${m.ticker} — ${m.name}`,
        desc: `${m.sector} · Klik untuk Riset Bandarmologi & Financials`,
        badge: 'IDX Edge',
        action: () => {
          closeCommandPalette();
          openStockDetailModal(m.ticker, m);
        }
      });
    });
  }

  // Limit stock matches to top 15 for fast rendering
  cmdFilteredItems = [...items, ...stockMatches.slice(0, 15)];
  cmdSelectedIndex = 0;
  renderCmdList();
}

function renderCmdList() {
  const listContainer = document.getElementById('cmd-list');
  if (!listContainer) return;

  if (cmdFilteredItems.length === 0) {
    listContainer.innerHTML = `
      <div class="cmd-empty">
        <p>Tidak ada perintah atau emiten yang cocok dengan pencarian Anda.</p>
      </div>
    `;
    return;
  }

  let html = '';
  let currentGroup = '';

  cmdFilteredItems.forEach((item, index) => {
    if (item.group !== currentGroup) {
      currentGroup = item.group;
      html += `<div class="cmd-group-title">${currentGroup}</div>`;
    }

    const isSelected = index === cmdSelectedIndex;
    const isInvalid = item.isInvalid || item.badge === 'Tidak Valid';
    html += `
      <div class="cmd-item ${isSelected ? 'selected' : ''} ${isInvalid ? 'disabled-item' : ''}" 
           id="cmd-item-${index}"
           onclick="executeCmdItem(${index})">
        <div class="cmd-item-left">
          <span class="cmd-item-icon">${item.icon}</span>
          <div class="cmd-item-info">
            <span class="cmd-item-title ${isInvalid ? 'text-amber' : ''}">${item.title}</span>
            <span class="cmd-item-desc">${item.desc}</span>
          </div>
        </div>
        <span class="cmd-item-badge ${isInvalid ? 'badge-invalid' : ''}">${item.badge}</span>
      </div>
    `;
  });

  listContainer.innerHTML = html;
  scrollSelectedCmdIntoView();
}

function handleCmdKeydown(e) {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (cmdFilteredItems.length > 0) {
      cmdSelectedIndex = (cmdSelectedIndex + 1) % cmdFilteredItems.length;
      renderCmdList();
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (cmdFilteredItems.length > 0) {
      cmdSelectedIndex = (cmdSelectedIndex - 1 + cmdFilteredItems.length) % cmdFilteredItems.length;
      renderCmdList();
    }
  } else if (e.key === 'Enter') {
    e.preventDefault();
    executeCmdItem(cmdSelectedIndex);
  }
}

function executeCmdItem(index) {
  const item = cmdFilteredItems[index];
  if (item) {
    if (item.isInvalid || item.badge === 'Tidak Valid') {
      if (typeof item.action === 'function') {
        item.action();
      }
      return;
    }
    if (typeof item.action === 'function') {
      closeCommandPalette();
      item.action();
    }
  }
}

function scrollSelectedCmdIntoView() {
  const selectedEl = document.getElementById(`cmd-item-${cmdSelectedIndex}`);
  if (selectedEl) {
    selectedEl.scrollIntoView({ block: 'nearest' });
  }
}
