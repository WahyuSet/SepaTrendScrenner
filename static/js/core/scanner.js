// ============================================================================
// SCAN ENGINE & PROGRESS POLLING CONTROLLER
// ============================================================================

let isGlobalScanning = false;
let scanPollTimer = null;

async function triggerScan() {
  const btnScan = document.getElementById('btn-scan');
  const btnText = document.getElementById('btn-scan-text');

  try {
    if (btnScan) btnScan.disabled = true;
    if (btnText) btnText.textContent = 'Memulai Scan...';

    const res = await fetch('/api/scan', { method: 'POST' });
    const json = await res.json();

    if (res.ok || res.status === 409) {
      startStatusPolling();
      if (typeof renderSkeleton === 'function') renderSkeleton(8);
      if (typeof renderRsiSkeleton === 'function') renderRsiSkeleton(6);
      if (typeof renderPbSkeleton === 'function') renderPbSkeleton(6);
    } else {
      showToast('Gagal memulai scan: ' + (json.message || 'Error server'));
      if (btnScan) btnScan.disabled = false;
      if (btnText) btnText.textContent = 'Scan IDX Sekarang';
    }
  } catch (err) {
    console.error('Error triggering scan:', err);
    showToast('Terjadi kesalahan koneksi saat memulai scan.');
    if (btnScan) btnScan.disabled = false;
    if (btnText) btnText.textContent = 'Scan IDX Sekarang';
  }
}

function startStatusPolling() {
  isGlobalScanning = true;
  const progressBox = document.getElementById('scan-progress-box');
  if (progressBox) progressBox.classList.remove('hidden');

  const btnScan = document.getElementById('btn-scan');
  const btnText = document.getElementById('btn-scan-text');
  if (btnScan) btnScan.disabled = true;
  if (btnText) btnText.textContent = 'Sedang Scanning...';

  if (scanPollTimer) clearInterval(scanPollTimer);

  scanPollTimer = setInterval(async () => {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();

      updateProgressUI(data);

      if (!data.is_scanning) {
        clearInterval(scanPollTimer);
        scanPollTimer = null;
        isGlobalScanning = false;

        if (progressBox) progressBox.classList.add('hidden');
        if (btnScan) btnScan.disabled = false;
        if (btnText) btnText.textContent = 'Scan IDX Sekarang';

        // Load new results for all three screeners
        const loaders = [];
        if (typeof loadCachedResults === 'function') loaders.push(loadCachedResults());
        if (typeof loadRsiResults === 'function') loaders.push(loadRsiResults());
        if (typeof loadPreBreakoutResults === 'function') loaders.push(loadPreBreakoutResults());

        await Promise.all(loaders);
        showToast('✓ Scanning IDX selesai! Data terbaru berhasil dimuat.');
      }
    } catch (e) {
      console.error('Polling error:', e);
    }
  }, 1500);
}

async function checkScanStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.is_scanning) {
      startStatusPolling();
    }
  } catch (e) {
    console.error('Status check error:', e);
  }
}

function updateProgressUI(data) {
  const current = data.progress_current || 0;
  const total = data.progress_total || 1;
  const pct = Math.min(100, Math.round((current / total) * 100));

  const fill = document.getElementById('scan-progress-fill');
  const count = document.getElementById('scan-progress-count');
  const activeTicker = document.getElementById('scan-current-ticker');

  if (fill) fill.style.width = `${pct}%`;
  if (count) count.textContent = `${current}/${total} (${pct}%)`;
  if (activeTicker) activeTicker.textContent = data.current_ticker ? `Memeriksa ${data.current_ticker}` : 'Mengalkulasi RS Rating & Setup...';
}
