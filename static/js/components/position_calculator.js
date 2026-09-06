// ============================================================================
// POSITION SIZING & MONEY MANAGEMENT CALCULATOR (static/js/components/position_calculator.js)
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

const calcState = {
  ticker: '',
  name: '',
  sector: 'General',
  portfolioCapital: 100000000,
  riskPct: 1.0,
  entryPrice: 0,
  stopLoss: 0,
  target1: null,
  target2: null,
  maxCapPct: 20.0,
  buyFeePct: 0.15,
  sellFeePct: 0.25,
  feeEnabled: true
};

// 1. OPEN & CLOSE MODAL
function openPositionCalculator(params = {}) {
  const modal = document.getElementById('modal-position-sizing');
  if (!modal) return;

  // Load saved settings if available
  fetch('/api/settings/money-management')
    .then(res => res.json())
    .then(json => {
      if (json.status === 'success' && json.data) {
        calcState.portfolioCapital = json.data.portfolio_capital || 100000000;
        calcState.riskPct = json.data.risk_per_trade_pct || 1.0;
        calcState.maxCapPct = json.data.max_position_cap_pct || 20.0;
        calcState.buyFeePct = json.data.broker_fee_buy_pct || 0.15;
        calcState.sellFeePct = json.data.broker_fee_sell_pct || 0.25;
        calcState.feeEnabled = json.data.broker_fee_enabled !== false;
      }
      populateCalcForm(params);
      recomputePositionSizing();
      modal.classList.remove('hidden');
    })
    .catch(() => {
      populateCalcForm(params);
      recomputePositionSizing();
      modal.classList.remove('hidden');
    });
}

function closePositionCalculator() {
  const modal = document.getElementById('modal-position-sizing');
  if (modal) modal.classList.add('hidden');
}

function closePositionCalcOnBackdrop(e) {
  if (e.target.id === 'modal-position-sizing') {
    closePositionCalculator();
  }
}

// 2. POPULATE FORM
function populateCalcForm(params) {
  const elTicker = document.getElementById('calc-ticker');
  const elCapital = document.getElementById('calc-capital');
  const elRisk = document.getElementById('calc-risk-pct');
  const elEntry = document.getElementById('calc-entry');
  const elSL = document.getElementById('calc-sl');
  const elT1 = document.getElementById('calc-t1');
  const elT2 = document.getElementById('calc-t2');
  const elMaxCap = document.getElementById('calc-max-cap');
  const elFeeEnabled = document.getElementById('calc-fee-enabled');
  const elFeeBuy = document.getElementById('calc-fee-buy');
  const elFeeSell = document.getElementById('calc-fee-sell');

  calcState.ticker = params.ticker || '';
  calcState.name = params.name || params.ticker || '';
  calcState.sector = params.sector || 'General';

  if (elTicker) elTicker.value = calcState.ticker;
  if (elCapital) elCapital.value = calcState.portfolioCapital;
  if (elRisk) elRisk.value = calcState.riskPct;
  if (elMaxCap) elMaxCap.value = calcState.maxCapPct;
  if (elFeeEnabled) elFeeEnabled.checked = calcState.feeEnabled;
  if (elFeeBuy) elFeeBuy.value = calcState.buyFeePct;
  if (elFeeSell) elFeeSell.value = calcState.sellFeePct;

  // Preset prices if provided
  if (params.price || params.entry) {
    calcState.entryPrice = parseFloat(params.price || params.entry) || 0;
    if (elEntry) elEntry.value = calcState.entryPrice;
  }
  if (params.stop_loss || params.sl) {
    calcState.stopLoss = parseFloat(params.stop_loss || params.sl) || 0;
    if (elSL) elSL.value = calcState.stopLoss;
  }
  if (params.target_1 || params.t1) {
    calcState.target1 = parseFloat(params.target_1 || params.t1) || null;
    if (elT1) elT1.value = calcState.target1 || '';
  }
  if (params.target_2 || params.t2) {
    calcState.target2 = parseFloat(params.target_2 || params.t2) || null;
    if (elT2) elT2.value = calcState.target2 || '';
  }

  // Set active risk preset pill
  updateRiskPresetPills(calcState.riskPct);
}

// 3. RECOMPUTE LOGIC (INSTANT CLIENT MATH)
function recomputePositionSizing() {
  const elCapital = document.getElementById('calc-capital');
  const elRisk = document.getElementById('calc-risk-pct');
  const elEntry = document.getElementById('calc-entry');
  const elSL = document.getElementById('calc-sl');
  const elT1 = document.getElementById('calc-t1');
  const elT2 = document.getElementById('calc-t2');
  const elMaxCap = document.getElementById('calc-max-cap');
  const elFeeEnabled = document.getElementById('calc-fee-enabled');
  const elFeeBuy = document.getElementById('calc-fee-buy');
  const elFeeSell = document.getElementById('calc-fee-sell');

  const capital = Math.max(1, parseFloat(elCapital ? elCapital.value : 100000000) || 100000000);
  const riskPct = Math.max(0.1, parseFloat(elRisk ? elRisk.value : 1.0) || 1.0);
  const entry = Math.max(0, parseFloat(elEntry ? elEntry.value : 0) || 0);
  const sl = Math.max(0, parseFloat(elSL ? elSL.value : 0) || 0);
  const t1 = parseFloat(elT1 && elT1.value ? elT1.value : 0) || null;
  const t2 = parseFloat(elT2 && elT2.value ? elT2.value : 0) || null;
  const maxCap = Math.max(1, parseFloat(elMaxCap ? elMaxCap.value : 20) || 20);
  const feeEnabled = elFeeEnabled ? elFeeEnabled.checked : true;
  const feeBuy = parseFloat(elFeeBuy ? elFeeBuy.value : 0.15) || 0.15;
  const feeSell = parseFloat(elFeeSell ? elFeeSell.value : 0.25) || 0.25;

  calcState.portfolioCapital = capital;
  calcState.riskPct = riskPct;
  calcState.entryPrice = entry;
  calcState.stopLoss = sl;
  calcState.target1 = t1;
  calcState.target2 = t2;
  calcState.maxCapPct = maxCap;
  calcState.feeEnabled = feeEnabled;

  // Header Previews
  const elCapDisp = document.getElementById('calc-capital-display');
  if (elCapDisp) elCapDisp.textContent = formatIDR(capital);

  const maxRiskIDR = capital * (riskPct / 100.0);
  const elRiskDisp = document.getElementById('calc-max-risk-display');
  if (elRiskDisp) elRiskDisp.textContent = `Maks Loss: ${formatIDR(maxRiskIDR)} (${riskPct.toFixed(1)}%)`;

  // Validation
  if (entry <= 0 || sl <= 0 || sl >= entry) {
    renderInvalidCalcState(entry, sl);
    return;
  }

  // Minervini Calculation
  const riskPerShare = entry - sl;
  const riskPctShare = (riskPerShare / entry) * 100.0;

  const idealShares = maxRiskIDR / riskPerShare;
  const idealLots = Math.floor(idealShares / 100.0);

  const maxCapCapital = capital * (maxCap / 100.0);
  const capLots = Math.floor(maxCapCapital / (entry * 100.0));

  const isCapped = idealLots > capLots;
  const finalLots = Math.max(1, Math.min(idealLots, capLots));
  const finalShares = finalLots * 100;
  const totalCapitalAllocated = finalShares * entry;
  const allocPct = (totalCapitalAllocated / capital) * 100.0;

  // Broker Fees
  const buyFee = feeEnabled ? (totalCapitalAllocated * (feeBuy / 100.0)) : 0;
  const slExitVal = finalShares * sl;
  const slSellFee = feeEnabled ? (slExitVal * (feeSell / 100.0)) : 0;
  const totalLoss = (finalShares * riskPerShare) + (buyFee + slSellFee);

  // Targets
  let t1GainNet = 0;
  let t1RR = 0;
  let t1GainPct = 0;
  if (t1 && t1 > entry) {
    const t1GainGross = finalShares * (t1 - entry);
    const t1SellFee = feeEnabled ? ((finalShares * t1) * (feeSell / 100.0)) : 0;
    t1GainNet = t1GainGross - (buyFee + t1SellFee);
    t1RR = (t1 - entry) / riskPerShare;
    t1GainPct = ((t1 - entry) / entry) * 100.0;
  }

  let t2GainNet = 0;
  let t2RR = 0;
  let t2GainPct = 0;
  if (t2 && t2 > entry) {
    const t2GainGross = finalShares * (t2 - entry);
    const t2SellFee = feeEnabled ? ((finalShares * t2) * (feeSell / 100.0)) : 0;
    t2GainNet = t2GainGross - (buyFee + t2SellFee);
    t2RR = (t2 - entry) / riskPerShare;
    t2GainPct = ((t2 - entry) / entry) * 100.0;
  }

  // Render DOM
  const elLots = document.getElementById('calc-result-lots');
  const elShares = document.getElementById('calc-result-shares');
  const elAllocCap = document.getElementById('calc-result-capital');
  const elAllocPct = document.getElementById('calc-result-alloc-pct');
  const elAllocBar = document.getElementById('calc-result-alloc-bar');
  const elBadge = document.getElementById('calc-status-badge');
  const elCapWarn = document.getElementById('calc-cap-warning');

  if (elLots) elLots.textContent = finalLots.toLocaleString('id-ID');
  if (elShares) elShares.textContent = `(${finalShares.toLocaleString('id-ID')} lembar)`;
  if (elAllocCap) elAllocCap.textContent = formatIDR(totalCapitalAllocated);
  if (elAllocPct) elAllocPct.textContent = `${allocPct.toFixed(1)}%`;
  if (elAllocBar) elAllocBar.style.width = `${Math.min(100, allocPct)}%`;

  if (isCapped) {
    if (elBadge) {
      elBadge.className = 'hero-badge warn';
      elBadge.textContent = `⚠️ DIBATASI CAP ${maxCap}%`;
    }
    if (elCapWarn) elCapWarn.classList.remove('hidden');
  } else {
    if (elBadge) {
      elBadge.className = 'hero-badge safe';
      elBadge.textContent = '✅ AMAN TERKONTROL';
    }
    if (elCapWarn) elCapWarn.classList.add('hidden');
  }

  // Risk Downside
  const elRiskLoss = document.getElementById('calc-result-risk-loss');
  const elRiskPct = document.getElementById('calc-result-risk-pct');
  const elFeeSub = document.getElementById('calc-result-fee-sub');

  if (elRiskLoss) elRiskLoss.textContent = `-${formatIDR(totalLoss)}`;
  if (elRiskPct) elRiskPct.textContent = `Jarak SL: -${riskPctShare.toFixed(1)}%`;
  if (elFeeSub) elFeeSub.textContent = feeEnabled ? `Fee: ${formatIDR(buyFee + slSellFee)}` : 'Fee: Nonaktif';

  // Targets
  const elT1Gain = document.getElementById('calc-result-t1-gain');
  const elT1RR = document.getElementById('calc-result-t1-rr');
  const elT1Pct = document.getElementById('calc-result-t1-pct');

  if (elT1Gain) elT1Gain.textContent = t1 ? `+${formatIDR(t1GainNet)}` : '—';
  if (elT1RR) elT1RR.textContent = t1 ? `R:R 1 : ${t1RR.toFixed(1)}` : 'R:R —';
  if (elT1Pct) elT1Pct.textContent = t1 ? `+${t1GainPct.toFixed(1)}%` : '';

  const elT2Gain = document.getElementById('calc-result-t2-gain');
  const elT2RR = document.getElementById('calc-result-t2-rr');
  const elT2Pct = document.getElementById('calc-result-t2-pct');

  if (elT2Gain) elT2Gain.textContent = t2 ? `+${formatIDR(t2GainNet)}` : '—';
  if (elT2RR) elT2RR.textContent = t2 ? `R:R 1 : ${t2RR.toFixed(1)}` : 'R:R —';
  if (elT2Pct) elT2Pct.textContent = t2 ? `+${t2GainPct.toFixed(1)}%` : '';
}

function renderInvalidCalcState(entry, sl) {
  const elLots = document.getElementById('calc-result-lots');
  const elShares = document.getElementById('calc-result-shares');
  const elAllocCap = document.getElementById('calc-result-capital');
  const elAllocPct = document.getElementById('calc-result-alloc-pct');
  const elAllocBar = document.getElementById('calc-result-alloc-bar');
  const elBadge = document.getElementById('calc-status-badge');
  const elCapWarn = document.getElementById('calc-cap-warning');

  if (elLots) elLots.textContent = '0';
  if (elShares) elShares.textContent = '(0 lembar)';
  if (elAllocCap) elAllocCap.textContent = 'Rp 0';
  if (elAllocPct) elAllocPct.textContent = '0.0%';
  if (elAllocBar) elAllocBar.style.width = '0%';

  if (sl >= entry && entry > 0) {
    if (elBadge) {
      elBadge.className = 'hero-badge warn';
      elBadge.textContent = '❌ SL HARUS < ENTRY';
    }
  } else {
    if (elBadge) {
      elBadge.className = 'hero-badge safe';
      elBadge.textContent = 'MASUKKAN HARGA';
    }
  }
  if (elCapWarn) elCapWarn.classList.add('hidden');
}

// 4. PRESETS & TOGGLES
function setRiskPreset(pct) {
  const elRisk = document.getElementById('calc-risk-pct');
  if (elRisk) elRisk.value = pct;
  updateRiskPresetPills(pct);
  recomputePositionSizing();
}

function updateRiskPresetPills(val) {
  const pills = document.querySelectorAll('.btn-risk-pill');
  pills.forEach(p => {
    const pVal = parseFloat(p.textContent.replace('%', ''));
    if (Math.abs(pVal - val) < 0.05) {
      p.classList.add('active');
    } else {
      p.classList.remove('active');
    }
  });
}

function toggleAdvancedCalcSettings() {
  const content = document.getElementById('adv-calc-body');
  const chevron = document.getElementById('adv-calc-chevron');
  if (!content) return;
  const isHidden = content.classList.contains('hidden');
  if (isHidden) {
    content.classList.remove('hidden');
    if (chevron) chevron.textContent = '▲';
  } else {
    content.classList.add('hidden');
    if (chevron) chevron.textContent = '▼';
  }
}

function onCalcTickerChange(val) {
  const clean = (val || '').trim().toUpperCase();
  calcState.ticker = clean;
  const elMeta = document.getElementById('calc-ticker-meta');
  if (elMeta) {
    elMeta.textContent = clean ? `${clean}.JK` : 'IDX Stock';
  }
}

// 5. TRANSFER DATA TO TRADE JOURNAL
function transferCalcToTradeJournal() {
  const elLots = document.getElementById('calc-result-lots');
  const lots = elLots ? parseInt(elLots.textContent.replace(/\D/g, ''), 10) : 0;

  if (lots <= 0 || calcState.entryPrice <= 0) {
    if (typeof showToast === 'function') {
      showToast('Masukkan harga Entry dan Stop Loss yang valid terlebih dahulu', 'warning');
    }
    return;
  }

  // Close calculator
  closePositionCalculator();

  // Open Trade Journal Modal with pre-filled data
  openNewTradeEntryModal({
    ticker: calcState.ticker || 'EMITEN',
    name: calcState.name || calcState.ticker || 'Saham Pilihan',
    sector: calcState.sector || 'General',
    buy_price: calcState.entryPrice,
    lots: lots,
    stop_loss: calcState.stopLoss,
    target_1: calcState.target1,
    target_2: calcState.target2,
    setup_type: 'Position Sizing Plan',
    notes: `Dihitung via Position Sizing. Modal Portofolio: ${formatIDR(calcState.portfolioCapital)}, Risiko: ${calcState.riskPct}%`
  });
}

function copyPositionSizingSummary() {
  const elLots = document.getElementById('calc-result-lots');
  const lots = elLots ? elLots.textContent : '0';
  const text = `🎯 PLAN POSITION SIZING IDX:
Saham: ${calcState.ticker || '—'}
Entry: Rp ${calcState.entryPrice.toLocaleString('id-ID')}
Stop Loss: Rp ${calcState.stopLoss.toLocaleString('id-ID')} (Jarak: -${(((calcState.entryPrice - calcState.stopLoss) / calcState.entryPrice) * 100).toFixed(1)}%)
Target 1: Rp ${(calcState.target1 || 0).toLocaleString('id-ID')}
Rekomendasi: ${lots} LOT (${(parseInt(lots.replace(/\D/g, ''), 10) * 100).toLocaleString('id-ID')} lembar)
Modal Terpakai: ${formatIDR(parseInt(lots.replace(/\D/g, ''), 10) * 100 * calcState.entryPrice)}
Toleransi Risiko: ${calcState.riskPct}% (${formatIDR(calcState.portfolioCapital * (calcState.riskPct / 100))})`;

  navigator.clipboard.writeText(text).then(() => {
    if (typeof showToast === 'function') {
      showToast('Ringkasan sizing berhasil disalin ke clipboard!', 'success');
    }
  });
}
