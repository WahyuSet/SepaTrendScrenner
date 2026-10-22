/**
 * ============================================================================
 * ENTERPRISE STOCK DETAIL MODAL & IDX EDGE API INTEGRATION
 * Follows /enterprise-frontend-design guidelines
 * ============================================================================
 */

let currentStockTicker = "";
let currentStockMeta = {};
let stockDataCache = {}; // Cache per session: { 'BBCA': { bandar: {...}, accum: {...}, financials: {...}, analysis: {...} } }
let activeStockTab = "bandar";

// Helper: Format Rupiah Singkat (T, B, M)
function formatRupiahShort(val) {
  if (val === null || val === undefined || isNaN(val)) return "Rp 0";
  const abs = Math.abs(val);
  const sign = val < 0 ? "-" : "";
  if (abs >= 1e12) {
    return `${sign}Rp ${(abs / 1e12).toFixed(2)} T`;
  } else if (abs >= 1e9) {
    return `${sign}Rp ${(abs / 1e9).toFixed(2)} B`;
  } else if (abs >= 1e6) {
    return `${sign}Rp ${(abs / 1e6).toFixed(2)} M`;
  } else {
    return `${sign}Rp ${new Intl.NumberFormat("id-ID").format(Math.round(abs))}`;
  }
}

// Helper: Format Angka Lot
function formatLotNumber(vol) {
  if (!vol || isNaN(vol)) return "0";
  return new Intl.NumberFormat("id-ID").format(Math.round(vol));
}

// ============================================================================
// 1. MODAL OPEN / CLOSE CONTROLLERS
// ============================================================================

function openStockDetailModal(ticker, meta = {}) {
  if (!ticker) return;
  ticker = ticker.replace(".JK", "").trim().toUpperCase();

  // Validate against 941 IDX master emiten if available
  if (window.idxMasterTickersMap && Object.keys(window.idxMasterTickersMap).length > 0) {
    if (!window.idxMasterTickersMap[ticker]) {
      if (typeof showToast === 'function') {
        showToast(`Ticker '${ticker}' tidak terdaftar di Bursa Efek Indonesia (IDX)`, 'warning');
      } else {
        alert(`Ticker '${ticker}' tidak terdaftar di Bursa Efek Indonesia (IDX)`);
      }
      return;
    }
    if (!meta.name && window.idxMasterTickersMap[ticker]) {
      meta = window.idxMasterTickersMap[ticker];
    }
  }

  currentStockTicker = ticker;
  currentStockMeta = meta;

  // Header Elements
  document.getElementById("stock-modal-ticker").textContent = ticker;
  document.getElementById("stock-modal-name").textContent = meta.name || `${ticker} Tbk.`;
  document.getElementById("stock-modal-sector").textContent = meta.sector || "IDX Listed";

  const priceEl = document.getElementById("stock-modal-price");
  if (meta.price) {
    priceEl.textContent = `Rp ${new Intl.NumberFormat("id-ID").format(meta.price)}`;
  } else {
    priceEl.textContent = "—";
  }

  // Initial Badge States
  const flowBadge = document.getElementById("stock-modal-flow-badge");
  flowBadge.className = "stock-status-pill neutral";
  flowBadge.textContent = "Checking Flow...";

  const sepaBadge = document.getElementById("stock-modal-sepa-badge");
  sepaBadge.classList.add("hidden");

  // Update Pin button state
  const pinBtn = document.getElementById("detail-modal-pin-btn");
  if (pinBtn) {
    if (typeof watchlistState !== 'undefined' && watchlistState.pinnedTickers && watchlistState.pinnedTickers.has(ticker)) {
      pinBtn.classList.add('pinned');
      pinBtn.innerHTML = '<span>★</span> Pinned';
    } else {
      pinBtn.classList.remove('pinned');
      pinBtn.innerHTML = '<span>☆</span> Pin';
    }
  }

  // Show Modal Backdrop
  const modal = document.getElementById("stock-detail-modal");
  modal.classList.remove("hidden");

  // Activate Default Tab
  switchStockModalTab(activeStockTab || "bandar");
}

function openSizingFromDetailModal() {
  if (!currentStockTicker) return;
  const price = currentStockMeta.price || 0;
  if (typeof openPositionCalculator === 'function') {
    openPositionCalculator({
      ticker: currentStockTicker,
      name: currentStockMeta.name || `${currentStockTicker} Tbk.`,
      sector: currentStockMeta.sector || 'IDX Listed',
      entry: price
    });
  }
}

function togglePinFromDetailModal() {
  if (!currentStockTicker) return;
  if (typeof togglePinStock === 'function') {
    togglePinStock(currentStockTicker, currentStockMeta.name || `${currentStockTicker} Tbk.`, currentStockMeta.sector || 'IDX Listed', 'Detail Modal');
    const pinBtn = document.getElementById("detail-modal-pin-btn");
    if (pinBtn && typeof watchlistState !== 'undefined' && watchlistState.pinnedTickers) {
      if (watchlistState.pinnedTickers.has(currentStockTicker)) {
        pinBtn.classList.add('pinned');
        pinBtn.innerHTML = '<span>★</span> Pinned';
      } else {
        pinBtn.classList.remove('pinned');
        pinBtn.innerHTML = '<span>☆</span> Pin';
      }
    }
  }
}

function closeStockDetailModal() {
  const modal = document.getElementById("stock-detail-modal");
  if (modal) modal.classList.add("hidden");
}

function handleStockModalBackdrop(event) {
  if (event.target && event.target.id === "stock-detail-modal") {
    closeStockDetailModal();
  }
}

// ESC Key closes modal
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const modal = document.getElementById("stock-detail-modal");
    if (modal && !modal.classList.contains("hidden")) {
      closeStockDetailModal();
    }
  }
});

// ============================================================================
// 2. TAB SWITCHING & REFRESH
// ============================================================================

function switchStockModalTab(tabName) {
  activeStockTab = tabName;

  // Update Buttons
  document.querySelectorAll(".stock-tab-btn").forEach((btn) => btn.classList.remove("active"));
  const activeBtn = document.getElementById(`tab-btn-${tabName}`);
  if (activeBtn) activeBtn.classList.add("active");

  // Update Panes
  document.querySelectorAll(".stock-tab-pane").forEach((pane) => pane.classList.remove("active"));
  const activePane = document.getElementById(`pane-${tabName}`);
  if (activePane) activePane.classList.add("active");

  // Fetch or Render data
  loadCurrentTabData(false);
}

function refreshCurrentStockTab() {
  loadCurrentTabData(true);
}

function loadCurrentTabData(force = false) {
  if (!currentStockTicker) return;

  if (activeStockTab === "bandar") {
    fetchBandarData(currentStockTicker, force);
  } else if (activeStockTab === "financials") {
    fetchFinancialsData(currentStockTicker, force);
  } else if (activeStockTab === "analysis") {
    fetchAnalysisData(currentStockTicker, force);
  }
}

// ============================================================================
// 3. TAB 1: BANDARMOLOGI & FLOW FETCHER
// ============================================================================

async function fetchBandarData(ticker, force = false) {
  const cacheKey = `${ticker}_bandar`;
  const loadingEl = document.getElementById("stock-tab-loading");
  const paneEl = document.getElementById("pane-bandar");

  if (!force && stockDataCache[cacheKey]) {
    renderBandarData(stockDataCache[cacheKey]);
    return;
  }

  loadingEl.classList.remove("hidden");

  try {
    const [bsResp, accumResp] = await Promise.all([
      fetch(`/api/idx/broker-summary/${ticker}?force=${force}`).then((r) => r.json()),
      fetch(`/api/idx/broker-accumulation/${ticker}?force=${force}`).then((r) => r.json())
    ]);

    loadingEl.classList.add("hidden");

    if (bsResp.status === "success" && bsResp.data) {
      const combined = {
        summary: bsResp.data,
        accumulation: accumResp.status === "success" ? accumResp.data : null
      };
      stockDataCache[cacheKey] = combined;
      renderBandarData(combined);
      if (bsResp.quota) updateSidebarQuota(bsResp.quota);
    } else {
      document.getElementById("bandar-status-title").textContent = "Gagal memuat data";
      document.getElementById("bandar-status-desc").textContent = bsResp.message || "Endpoint error";
    }
  } catch (err) {
    loadingEl.classList.add("hidden");
    console.error("Bandar fetch error:", err);
  }
}

function renderBandarData(data) {
  const s = data.summary;
  const a = data.accumulation;

  // 1. Status Akumulasi Card
  const titleEl = document.getElementById("bandar-status-title");
  const descEl = document.getElementById("bandar-status-desc");
  const flowBadge = document.getElementById("stock-modal-flow-badge");

  titleEl.className = `bento-value ${s.status_class || "neutral"}`;
  titleEl.textContent = s.status_label || s.status;
  descEl.textContent = `Top 3 Buyers vs Sellers: ${s.top3_buy_ratio}% vs ${s.top3_sell_ratio}%`;

  flowBadge.className = `stock-status-pill ${s.status_class || "neutral"}`;
  flowBadge.textContent = s.status_label || s.status;

  // 2. Bento Metrics
  document.getElementById("bandar-top3-ratio").textContent = `${s.top3_buy_ratio}%`;
  document.getElementById("bandar-turnover").textContent = formatRupiahShort(s.total_turnover);
  document.getElementById("bandar-date-label").textContent = `EOD: ${s.latest_date || "Hari ini"}`;

  document.getElementById("bandar-total-buy-val").textContent = formatRupiahShort(s.top3_buy_val);
  document.getElementById("bandar-total-sell-val").textContent = formatRupiahShort(s.top3_sell_val);

  // 3. Top Buyers List
  const buyersTbody = document.getElementById("bandar-buyers-list");
  if (s.top_buyers && s.top_buyers.length > 0) {
    buyersTbody.innerHTML = s.top_buyers.map((b) => `
      <tr>
        <td>
          <span class="broker-badge">${b.code}</span>
          <span class="broker-name-sub">${(b.name || "").substring(0, 24)}</span>
        </td>
        <td class="text-right mono font-bold text-success">${formatRupiahShort(b.nval)}</td>
        <td class="text-right mono text-muted">${formatLotNumber(b.nvol)}</td>
      </tr>
    `).join("");
  } else {
    buyersTbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Tidak ada data buyer</td></tr>`;
  }

  // 4. Top Sellers List
  const sellersTbody = document.getElementById("bandar-sellers-list");
  if (s.top_sellers && s.top_sellers.length > 0) {
    sellersTbody.innerHTML = s.top_sellers.map((b) => `
      <tr>
        <td>
          <span class="broker-badge">${b.code}</span>
          <span class="broker-name-sub">${(b.name || "").substring(0, 24)}</span>
        </td>
        <td class="text-right mono font-bold text-danger">${formatRupiahShort(b.nval)}</td>
        <td class="text-right mono text-muted">${formatLotNumber(b.nvol)}</td>
      </tr>
    `).join("");
  } else {
    sellersTbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Tidak ada data seller</td></tr>`;
  }

  // 5. Accumulation Series Trend
  const trendBadge = document.getElementById("bandar-trend-badge");
  const seriesContainer = document.getElementById("accum-series-container");

  if (a) {
    if (a.trend === "UPTREND_ACCUM") {
      trendBadge.className = "trend-badge uptrend";
      trendBadge.textContent = a.trend_label || "📈 Accumulation Uptrend";
    } else if (a.trend === "DOWNTREND_DIST") {
      trendBadge.className = "trend-badge downtrend";
      trendBadge.textContent = a.trend_label || "📉 Distribution Downtrend";
    } else {
      trendBadge.className = "trend-badge neutral";
      trendBadge.textContent = a.trend_label || "→ Neutral Trend";
    }

    let pillsHtml = "";
    // Top Buyers summary pill
    if (a.top_buyers && a.top_buyers.length > 0) {
      const buyersStr = a.top_buyers.map(b => `${b.broker_code}: ${formatRupiahShort(b.total_nval)}`).join(", ");
      pillsHtml += `<div class="series-point-pill" style="margin-bottom: 6px;"><span class="text-muted">Top Acc (${a.start_date || 'Start'} s/d ${a.end_date || 'Now'}):</span> <span class="font-bold text-success">${buyersStr}</span></div>`;
    }
    // Daily points
    if (a.series && a.series.length > 0) {
      pillsHtml += `<div style="display: flex; gap: 8px; flex-wrap: wrap;">`;
      pillsHtml += a.series.map((pt) => `
        <div class="series-point-pill">
          <span class="text-muted">${pt.date}:</span>
          <span class="font-bold mono ${pt.accum_val >= 0 ? "text-success" : "text-danger"}">${formatRupiahShort(pt.accum_val)}</span>
        </div>
      `).join("");
      pillsHtml += `</div>`;
    }
    seriesContainer.innerHTML = pillsHtml || `<span class="text-muted text-sm">Data time-series tidak tersedia</span>`;
  } else {
    trendBadge.className = "trend-badge neutral";
    trendBadge.textContent = "—";
    seriesContainer.innerHTML = `<span class="text-muted text-sm">Data time-series tidak tersedia</span>`;
  }
}

// ============================================================================
// 4. TAB 2: FINANCIAL STATEMENTS & EPS GROWTH
// ============================================================================

async function fetchFinancialsData(ticker, force = false) {
  const cacheKey = `${ticker}_financials`;
  const loadingEl = document.getElementById("stock-tab-loading");

  if (!force && stockDataCache[cacheKey]) {
    renderFinancialsData(stockDataCache[cacheKey]);
    return;
  }

  loadingEl.classList.remove("hidden");

  try {
    const resp = await fetch(`/api/idx/financials/${ticker}?force=${force}`).then((r) => r.json());
    loadingEl.classList.add("hidden");

    if (resp.status === "success" && resp.data) {
      stockDataCache[cacheKey] = resp.data;
      renderFinancialsData(resp.data);
      if (resp.quota) updateSidebarQuota(resp.quota);
    } else {
      document.getElementById("fin-sepa-verdict").textContent = "Data tidak ditemukan";
    }
  } catch (err) {
    loadingEl.classList.add("hidden");
    console.error("Financials fetch error:", err);
  }
}

function renderFinancialsData(data) {
  const sepaVerdictEl = document.getElementById("fin-sepa-verdict");
  const sepaDescEl = document.getElementById("fin-sepa-desc");
  const epsGrowthEl = document.getElementById("fin-eps-growth");
  const latestProfitEl = document.getElementById("fin-latest-profit");
  const latestLabelEl = document.getElementById("fin-latest-label");
  const sepaBadge = document.getElementById("stock-modal-sepa-badge");

  if (data.sepa_certified) {
    sepaVerdictEl.className = "bento-value success";
    sepaVerdictEl.textContent = "👑 SEPA Certified";
    sepaDescEl.textContent = `Pertumbuhan laba akseleratif (EPS YoY ≥ 20%)`;
    sepaBadge.classList.remove("hidden");
  } else if (data.yoy_eps_growth !== null) {
    sepaVerdictEl.className = "bento-value neutral";
    sepaVerdictEl.textContent = "Standard Growth";
    sepaDescEl.textContent = `EPS YoY: ${data.yoy_eps_growth}%`;
  } else {
    sepaVerdictEl.className = "bento-value neutral";
    sepaVerdictEl.textContent = "Data EPS Terbatas";
  }

  if (data.yoy_eps_growth !== null) {
    const isPos = data.yoy_eps_growth > 0;
    epsGrowthEl.className = `bento-value mono ${isPos ? "success" : "danger"}`;
    epsGrowthEl.textContent = `${isPos ? "+" : ""}${data.yoy_eps_growth}%`;
  } else {
    epsGrowthEl.textContent = "—";
  }

  latestProfitEl.textContent = formatRupiahShort(data.latest_net_profit);
  if (data.items && data.items.length > 0) {
    latestLabelEl.textContent = `Periode: ${data.items[0].label}`;
  }

  // Render Table
  const tbody = document.getElementById("financials-table-body");
  if (data.items && data.items.length > 0) {
    tbody.innerHTML = data.items.map((it) => {
      const isProfitable = it.net_profit && it.net_profit > 0;
      return `
        <tr>
          <td class="font-bold">${it.label}</td>
          <td class="text-right mono ${isProfitable ? "text-success" : "text-danger"}">${formatRupiahShort(it.net_profit)}</td>
          <td class="text-right mono font-bold">${it.eps !== null ? `Rp ${it.eps}` : "—"}</td>
          <td class="text-center">
            <span class="stock-status-pill ${isProfitable ? "success" : "danger"}">
              ${isProfitable ? "Laba ✅" : "Rugi ⚠️"}
            </span>
          </td>
        </tr>
      `;
    }).join("");
  } else {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Data laporan keuangan tidak tersedia</td></tr>`;
  }
}

// ============================================================================
// 5. TAB 3: COMPREHENSIVE ANALYSIS (AI VERDICT)
// ============================================================================

async function fetchAnalysisData(ticker, force = false) {
  const cacheKey = `${ticker}_analysis`;
  const loadingEl = document.getElementById("stock-tab-loading");

  if (!force && stockDataCache[cacheKey]) {
    renderAnalysisData(stockDataCache[cacheKey]);
    return;
  }

  loadingEl.classList.remove("hidden");

  try {
    const resp = await fetch(`/api/idx/analysis/${ticker}?force=${force}`).then((r) => r.json());
    loadingEl.classList.add("hidden");

    if (resp.status === "success" && resp.data) {
      stockDataCache[cacheKey] = resp.data;
      renderAnalysisData(resp.data);
      if (resp.quota) updateSidebarQuota(resp.quota);
    } else {
      document.getElementById("analysis-raw-text").textContent = "Gagal memuat analisa: " + (resp.message || "");
    }
  } catch (err) {
    loadingEl.classList.add("hidden");
    console.error("Analysis fetch error:", err);
  }
}

function renderAnalysisData(data) {
  const p = data.pivots || {};
  document.getElementById("pivot-s2").textContent = p.s2 || "—";
  document.getElementById("pivot-s1").textContent = p.s1 || "—";
  document.getElementById("pivot-p").textContent = p.p || "—";
  document.getElementById("pivot-r1").textContent = p.r1 || "—";
  document.getElementById("pivot-r2").textContent = p.r2 || "—";

  const plan = data.trading_plan || {};
  
  const scoreBadge = document.getElementById("plan-score-badge");
  if (scoreBadge) {
    scoreBadge.textContent = plan.score ? `Score: ${plan.score}` : "AI Analysis";
  }

  const actionBadge = document.getElementById("plan-action-badge");
  if (actionBadge) {
    const act = plan.action || "MONITOR";
    actionBadge.textContent = act;
    const actUpper = act.toUpperCase();
    if (actUpper.includes("BUY") || actUpper.includes("STRONG")) {
      actionBadge.className = "plan-action-badge success";
    } else if (actUpper.includes("WASPADA") || actUpper.includes("WATCH")) {
      actionBadge.className = "plan-action-badge warning";
    } else if (actUpper.includes("HINDARI") || actUpper.includes("AVOID")) {
      actionBadge.className = "plan-action-badge danger";
    } else {
      actionBadge.className = "plan-action-badge neutral";
    }
  }

  const entryEl = document.getElementById("plan-entry");
  if (entryEl) entryEl.textContent = plan.jika_belum_punya || "—";

  const holdEl = document.getElementById("plan-hold");
  if (holdEl) holdEl.textContent = plan.jika_punya || "—";

  const targetEl = document.getElementById("plan-target");
  if (targetEl) {
    targetEl.textContent = `${plan.target1 || p.r1 || "—"} / ${plan.target2 || p.r2 || "—"}`;
  }

  const stopLossEl = document.getElementById("plan-stoploss");
  if (stopLossEl) stopLossEl.textContent = plan.stop_loss || p.s2 || p.s1 || "—";

  document.getElementById("analysis-raw-text").textContent = data.raw_output || "Tidak ada narasi analisa";
}

// ============================================================================
// 6. INLINE TABLE "CEK BANDAR" BUTTON & CELL ACTION
// ============================================================================

async function checkBandarInline(ticker, btnElement, event) {
  if (event) event.stopPropagation();
  if (!ticker || !btnElement) return;

  btnElement.disabled = true;
  btnElement.innerHTML = `<span>⏳</span> Cek...`;

  try {
    const resp = await fetch(`/api/idx/broker-summary/${ticker}`).then((r) => r.json());
    if (resp.status === "success" && resp.data) {
      const d = resp.data;
      const badgeClass = d.status_class === "success" ? "big-accum" : (d.status_class === "danger" ? "big-dist" : (d.status_class === "warning" ? "normal-dist" : (d.status_class === "accent" ? "normal-accum" : "neutral")));
      const badgeIcon = d.status === "BIG_ACCUM" ? "🟢" : (d.status === "BIG_DIST" ? "🔴" : (d.status === "NORMAL_ACCUM" ? "🔵" : "⚪"));

      const newHtml = `
        <span class="bandar-cell-badge ${badgeClass}" onclick="openStockDetailModal('${ticker}');" title="Klik untuk lihat detail Top Broker">
          ${badgeIcon} ${d.status_label || d.status} (${d.top3_buy_ratio}%)
        </span>
      `;
      btnElement.outerHTML = newHtml;

      if (resp.quota) updateSidebarQuota(resp.quota);
    } else {
      btnElement.disabled = false;
      btnElement.innerHTML = `<span>⚠️</span> Retry`;
    }
  } catch (err) {
    btnElement.disabled = false;
    btnElement.innerHTML = `<span>⚠️</span> Error`;
    console.error("Inline bandar check failed:", err);
  }
}

// ============================================================================
// 7. SIDEBAR QUOTA SYNC & INITIALIZATION
// ============================================================================

function updateSidebarQuota(quota) {
  if (!quota) return;
  const quotaText = document.getElementById("sidebar-quota-text");
  const quotaBar = document.getElementById("sidebar-quota-bar");

  if (quotaText) {
    quotaText.textContent = `${quota.used} / ${quota.limit}`;
  }
  if (quotaBar) {
    quotaBar.style.width = `${Math.min(100, quota.percent_used)}%`;
  }
}

// Fetch quota on start
document.addEventListener("DOMContentLoaded", () => {
  fetch("/api/idx/quota")
    .then((r) => r.json())
    .then((res) => {
      if (res.status === "success" && res.data) {
        updateSidebarQuota(res.data);
      }
    })
    .catch((e) => console.log("Init quota fetch notice:", e));
});

// Helper for TradingView external link
function openTradingViewChart(ticker) {
  if (!ticker) return;
  const url = `https://www.tradingview.com/chart/?symbol=IDX:${ticker}`;
  window.open(url, "_blank");
}
