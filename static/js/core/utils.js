// ============================================================================
// CORE UTILITIES (TOAST, NUMBER FORMATTING & MODAL SYSTEM)
// ============================================================================

// ----------------------------------------------------------------------------
// 1. Toast Notification System (Design.md §6.10)
// ----------------------------------------------------------------------------

function showToast(message, type = 'status') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const isError = type === 'error' || type === 'danger';
  toast.className = `toast ${isError ? 'toast-error' : 'toast-normal'}`;
  toast.setAttribute('role', isError ? 'alert' : 'status');
  toast.setAttribute('aria-live', isError ? 'assertive' : 'polite');

  const textSpan = document.createElement('span');
  textSpan.className = 'toast-message';
  textSpan.textContent = message;

  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'toast-close-btn';
  closeBtn.setAttribute('aria-label', 'Tutup pemberitahuan');
  closeBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';

  let dismissed = false;
  function dismiss() {
    if (dismissed) return;
    dismissed = true;
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.2s ease';
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 200);
  }

  closeBtn.onclick = dismiss;
  toast.append(textSpan, closeBtn);
  container.appendChild(toast);

  setTimeout(dismiss, 4000);
}

// ----------------------------------------------------------------------------
// 2. Shared Modal System & Focus Trap (Design.md §6.8, UI_REFACTOR_PLAN Fase 5)
// ----------------------------------------------------------------------------

let activeModalState = null;

function openModal(modalId, triggerEl) {
  const modal = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
  if (!modal) return;

  const prevActive = triggerEl || document.activeElement;

  // Show modal
  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');

  if (modal.tagName === 'DIALOG' && typeof modal.showModal === 'function') {
    if (!modal.open) modal.showModal();
  }

  // Focusable elements inside modal
  const focusableSelectors = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function getFocusables() {
    return Array.from(modal.querySelectorAll(focusableSelectors))
      .filter(el => el.offsetParent !== null && window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden');
  }

  const focusables = getFocusables();
  // Prefer autofocus input or first focusable element
  const autoFocusEl = modal.querySelector('[autofocus]');
  if (autoFocusEl) {
    autoFocusEl.focus();
  } else if (focusables.length > 0) {
    focusables[0].focus();
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeModal(modal.id);
      return;
    }

    if (e.key === 'Tab') {
      const current = getFocusables();
      if (current.length === 0) {
        e.preventDefault();
        return;
      }

      const firstEl = current[0];
      const lastEl = current[current.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstEl || !modal.contains(document.activeElement)) {
          e.preventDefault();
          lastEl.focus();
        }
      } else {
        if (document.activeElement === lastEl || !modal.contains(document.activeElement)) {
          e.preventDefault();
          firstEl.focus();
        }
      }
    }
  }

  document.addEventListener('keydown', handleKeydown);

  activeModalState = {
    id: modal.id,
    modal,
    triggerEl: prevActive,
    handleKeydown
  };
}

function closeModal(modalId) {
  const id = modalId || (activeModalState ? activeModalState.id : null);
  const modal = id ? document.getElementById(id) : (activeModalState ? activeModalState.modal : null);

  if (activeModalState && activeModalState.handleKeydown) {
    document.removeEventListener('keydown', activeModalState.handleKeydown);
  }

  if (modal) {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    if (modal.tagName === 'DIALOG' && typeof modal.close === 'function') {
      if (modal.open) modal.close();
    }
  }

  if (activeModalState && activeModalState.triggerEl) {
    try {
      activeModalState.triggerEl.focus();
    } catch (_) {}
  }

  activeModalState = null;
}

function handleModalBackdropClick(event, modalId) {
  if (event.target === event.currentTarget || event.target.id === modalId) {
    closeModal(modalId);
  }
}

// ----------------------------------------------------------------------------
// 3. Number Formatting Helpers
// ----------------------------------------------------------------------------

function formatCurrency(amount) {
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    maximumFractionDigits: 0
  }).format(amount || 0);
}

function formatNumber(num) {
  return new Intl.NumberFormat('id-ID').format(num || 0);
}

function formatIDR(val) {
  if (val === null || val === undefined || isNaN(val)) return "Rp 0";
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    maximumFractionDigits: 0
  }).format(Math.round(val));
}

function copyToClipboard(text, successMsg) {
  if (!text || text === '--') return;
  const msg = successMsg || `Tersalin: ${text}`;
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(msg);
    }).catch(() => {
      fallbackCopy(text, msg);
    });
  } else {
    fallbackCopy(text, msg);
  }
}

function fallbackCopy(text, msg) {
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    if (successful) {
      showToast(msg);
    }
  } catch (err) {
    console.error('Fallback copy failed:', err);
  }
}
