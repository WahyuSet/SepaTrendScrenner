// ============================================================================
// EXPORT & WATCHLIST UTILITIES (TRADINGVIEW & CSV)
// ============================================================================

function copyTradingViewWatchlist(type) {
  let list = [];
  let label = 'SEPA';

  if (type === 'sepa') {
    list = typeof state !== 'undefined' ? state.filteredResults : [];
    label = 'SEPA';
  } else if (type === 'rsi') {
    list = typeof rsiState !== 'undefined' ? rsiState.filteredResults : [];
    label = 'RSI';
  } else if (type === 'prebreakout') {
    list = typeof prebreakoutState !== 'undefined' ? prebreakoutState.filteredResults : [];
    label = 'Pre-Breakout';
  }

  if (!list || list.length === 0) {
    showToast('Tidak ada ticker untuk disalin pada filter saat ini.');
    return;
  }

  const tickersStr = list.map(item => `IDX:${item.ticker}`).join(', ');

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(tickersStr).then(() => {
      showToast(`✓ Berhasil menyalin ${list.length} ticker ${label} ke clipboard!`);
    }).catch(() => {
      fallbackCopy(tickersStr, list.length, label);
    });
  } else {
    fallbackCopy(tickersStr, list.length, label);
  }
}

function fallbackCopy(text, count, label) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    showToast(`✓ Berhasil menyalin ${count} ticker ${label} ke clipboard!`);
  } catch (err) {
    showToast('Gagal menyalin ke clipboard.');
  }
  document.body.removeChild(ta);
}

function exportTableToCsv(type) {
  const isSepa = type === 'sepa';
  const isRsi = type === 'rsi';
  const isPb = type === 'prebreakout';

  let list = [];
  if (isSepa) list = typeof state !== 'undefined' ? state.filteredResults : [];
  else if (isRsi) list = typeof rsiState !== 'undefined' ? rsiState.filteredResults : [];
  else if (isPb) list = typeof prebreakoutState !== 'undefined' ? prebreakoutState.filteredResults : [];

  if (!list || list.length === 0) {
    showToast('Tidak ada data untuk diekspor pada filter saat ini.');
    return;
  }

  let csvContent = '';
  let filename = '';
  const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');

  if (isSepa) {
    filename = `IDX_SEPA_Trend_${dateStr}.csv`;
    csvContent = 'Ticker,Nama Emiten,Sektor,Harga,SEPA Score,Status,RS Rating,Dist 52W Low (%),Dist 52W High (%),Volume\n';
    list.forEach(s => {
      const nameEsc = `"${(s.name || '').replace(/"/g, '""')}"`;
      const secEsc = `"${(s.sector || '').replace(/"/g, '""')}"`;
      csvContent += `${s.ticker},${nameEsc},${secEsc},${s.price},${s.total_score},${s.status},${s.rs_score},${s.dist_low_pct},${s.dist_high_pct},${s.volume}\n`;
    });
  } else if (isRsi) {
    filename = `IDX_RSI_Divergence_${dateStr}.csv`;
    csvContent = 'Ticker,Nama Emiten,Sektor,Harga,1D Change (%),Tipe Divergence,RSI,Pivot Low,Prev Pivot Low,Pivot RSI,Prev Pivot RSI,Bars Ago,Volume\n';
    list.forEach(s => {
      const nameEsc = `"${(s.name || '').replace(/"/g, '""')}"`;
      const secEsc = `"${(s.sector || '').replace(/"/g, '""')}"`;
      csvContent += `${s.ticker},${nameEsc},${secEsc},${s.price},${s.pct_change_1d},${s.divergence_label},${s.rsi},${s.pivot_low},${s.prev_pivot_low},${s.pivot_rsi},${s.prev_pivot_rsi},${s.bars_ago},${s.volume}\n`;
    });
  } else if (isPb) {
    filename = `IDX_PreBreakout_Setup_${dateStr}.csv`;
    csvContent = 'Ticker,Nama Emiten,Sektor,Harga,1D Change (%),Skor Setup,Status,Jarak Resistance 50D (%),Resistance 50D,RVOL,RSI 14,MACD,Signal,EMA20,EMA50,Volume\n';
    list.forEach(s => {
      const nameEsc = `"${(s.name || '').replace(/"/g, '""')}"`;
      const secEsc = `"${(s.sector || '').replace(/"/g, '""')}"`;
      csvContent += `${s.ticker},${nameEsc},${secEsc},${s.price},${s.pct_change_1d},${s.total_score},${s.status_label},${s.dist_res_pct},${s.high_50d},${s.rvol},${s.rsi},${s.macd},${s.signal},${s.ema20},${s.ema50},${s.volume}\n`;
    });
  }

  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast(`✓ File CSV ${isSepa ? 'SEPA' : (isRsi ? 'RSI' : 'Pre-Breakout')} berhasil diunduh!`);
}
