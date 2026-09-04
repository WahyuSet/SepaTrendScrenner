// ============================================================================
// MAIN APPLICATION ENTRY POINT & SCREENER ROUTING
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  initSliderVisuals();
  checkScanStatus();

  // Initial load of cached results across all three screeners
  loadCachedResults();
  loadRsiResults();
  loadPreBreakoutResults();
});

function initSliderVisuals() {
  const slider = document.getElementById('score-slider');
  if (slider) {
    updateSliderBackground(slider.value);
  }
}

function updateSliderBackground(val) {
  const pct = ((val - 1) / 7) * 100;
  const slider = document.getElementById('score-slider');
  if (slider) {
    slider.style.background = `linear-gradient(to right, var(--brand-lime) 0%, var(--brand-lime) ${pct}%, var(--bg-tertiary) ${pct}%, var(--bg-tertiary) 100%)`;
  }
}

function switchScreener(screenerId) {
  // Hide all views
  ['view-sepa', 'view-rsi-div', 'view-prebreakout'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.classList.remove('active');
      el.classList.add('hidden');
    }
  });

  // Remove active from all nav items / tabs
  ['nav-sepa', 'nav-rsi-div', 'nav-prebreakout'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  });

  if (screenerId === 'sepa') {
    document.getElementById('view-sepa')?.classList.remove('hidden');
    document.getElementById('view-sepa')?.classList.add('active');
    document.getElementById('nav-sepa')?.classList.add('active');
  } else if (screenerId === 'rsi-div') {
    document.getElementById('view-rsi-div')?.classList.remove('hidden');
    document.getElementById('view-rsi-div')?.classList.add('active');
    document.getElementById('nav-rsi-div')?.classList.add('active');
  } else if (screenerId === 'prebreakout') {
    document.getElementById('view-prebreakout')?.classList.remove('hidden');
    document.getElementById('view-prebreakout')?.classList.add('active');
    document.getElementById('nav-prebreakout')?.classList.add('active');
  }
}

function refreshActiveScreener() {
  Promise.all([loadCachedResults(), loadRsiResults(), loadPreBreakoutResults()]).then(() => {
    showToast('✓ Data berhasil dimuat ulang dari server!');
  });
}
