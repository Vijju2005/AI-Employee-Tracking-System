// EBT System — Enterprise Platform main.js

// ── Initialize Lucide Icons ────────────────────────────────
function initLucideIcons() {
  if (typeof lucide !== 'undefined' && lucide.createIcons) {
    lucide.createIcons();
  }
}
document.addEventListener('DOMContentLoaded', initLucideIcons);

// ── Sidebar toggle (mobile) ────────────────────────────────
const sidebar   = document.getElementById('sidebar');
const overlay   = document.getElementById('sidebarOverlay');
const hamburger = document.getElementById('hamburger');

function openSidebar()  { sidebar?.classList.add('open');    overlay?.classList.add('active'); }
function closeSidebar() { sidebar?.classList.remove('open'); overlay?.classList.remove('active'); }

hamburger?.addEventListener('click', openSidebar);
overlay?.addEventListener('click', closeSidebar);

// ── Flash message auto-dismiss ─────────────────────────────
document.querySelectorAll('.flash-msg').forEach(msg => {
  const close = msg.querySelector('.close-flash');
  close?.addEventListener('click', () => msg.remove());
  setTimeout(() => msg?.remove(), 6000);
});

// ── Global Confirm Dialogs (data-confirm) ──────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

// ── EBT System Confirm Modal (data-confirm-modal) ─────────────
function hrmsConfirm({ title = 'Confirm Action', message = 'Are you sure?', type = 'danger', onConfirm }) {
  const overlay = document.createElement('div');
  overlay.className = 'confirm-modal-overlay';
  overlay.innerHTML = `
    <div class="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="cmTitle">
      <div class="confirm-modal-header">
        <div class="confirm-modal-icon ${type}">
          <i data-lucide="${type === 'danger' ? 'trash-2' : 'alert-triangle'}"></i>
        </div>
        <h3 class="confirm-modal-title" id="cmTitle">${title}</h3>
      </div>
      <div class="confirm-modal-body">${message}</div>
      <div class="confirm-modal-footer">
        <button class="btn btn-secondary btn-sm" id="cmCancel">Cancel</button>
        <button class="btn ${type === 'danger' ? 'btn-danger' : 'btn-primary'} btn-sm" id="cmConfirm">Confirm</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  if (typeof lucide !== 'undefined') lucide.createIcons();

  const close = () => overlay.remove();
  overlay.querySelector('#cmCancel').addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  overlay.querySelector('#cmConfirm').addEventListener('click', () => {
    close();
    if (typeof onConfirm === 'function') onConfirm();
  });
}

// ── Toast Utility ──────────────────────────────────────────
function hrmsToast(message, type = 'info', duration = 4000) {
  let stack = document.getElementById('toastStack');
  if (!stack) {
    stack = document.createElement('div');
    stack.className = 'toast-stack';
    stack.id = 'toastStack';
    document.body.appendChild(stack);
  }
  const iconMap = { success: 'check-circle-2', error: 'x-circle', info: 'info', warning: 'alert-triangle' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<i data-lucide="${iconMap[type] || 'info'}"></i><span>${message}</span>`;
  stack.appendChild(toast);
  if (typeof lucide !== 'undefined') lucide.createIcons();
  toast.addEventListener('click', () => toast.remove());
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 260);
  }, duration);
}

// ── Active nav item detection ──────────────────────────────
(function() {
  const path = window.location.pathname;
  let bestMatch = null;
  let maxLen = -1;

  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (!href) return;
    const cleanHref = href.split('?')[0];

    if (href === path || href === window.location.pathname + window.location.search) {
      bestMatch = item; maxLen = 99999;
    } else if (cleanHref !== '/' && (path === cleanHref || path.startsWith(cleanHref + '/'))) {
      if (cleanHref.length > maxLen) { bestMatch = item; maxLen = cleanHref.length; }
    } else if (cleanHref === '/' && path === '/' && maxLen < 0) {
      bestMatch = item; maxLen = 0;
    }
  });

  if (bestMatch) {
    document.querySelectorAll('.nav-item.active').forEach(el => el.classList.remove('active'));
    bestMatch.classList.add('active');
  }

  // Close sidebar on mobile nav click
  document.querySelectorAll('.nav-item').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) closeSidebar();
    });
  });
})();

// ── Topbar live clock ──────────────────────────────────────
const clockEl = document.getElementById('liveClock');
if (clockEl) {
  function updateClock() {
    clockEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  updateClock();
  setInterval(updateClock, 1000);
}

// ── Notification Dropdown ──────────────────────────────────
(function() {
  const btn  = document.getElementById('notifBtn');
  const drop = document.getElementById('notifDropdown');
  if (!btn || !drop) return;

  btn.addEventListener('click', e => {
    e.stopPropagation();
    const open = drop.style.display !== 'none';
    // close profile first
    const pd = document.getElementById('profileDropdown');
    if (pd) pd.style.display = 'none';
    drop.style.display = open ? 'none' : 'block';
  });
  document.addEventListener('click', e => {
    if (!btn.contains(e.target) && !drop.contains(e.target)) drop.style.display = 'none';
  });
})();

// ── Profile Dropdown ───────────────────────────────────────
(function() {
  const btn  = document.getElementById('profileBtn');
  const drop = document.getElementById('profileDropdown');
  if (!btn || !drop) return;

  btn.addEventListener('click', e => {
    e.stopPropagation();
    const open = drop.style.display !== 'none';
    // close notif first
    const nd = document.getElementById('notifDropdown');
    if (nd) nd.style.display = 'none';
    drop.style.display = open ? 'none' : 'block';
  });
  document.addEventListener('click', e => {
    if (!btn.contains(e.target) && !drop.contains(e.target)) drop.style.display = 'none';
  });
})();

// ── Global Search Ctrl+K ───────────────────────────────────
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const inp = document.getElementById('searchInput');
    if (inp) { inp.focus(); inp.select(); }
  }
  if (e.key === 'Escape') {
    const inp = document.getElementById('searchInput');
    if (inp && document.activeElement === inp) inp.blur();
    // Close all dropdowns
    ['notifDropdown','profileDropdown'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
  }
});

// ── Form submit loading state ──────────────────────────────
document.querySelectorAll('form[data-loading]').forEach(form => {
  form.addEventListener('submit', e => {
    const submitter = e.submitter;
    if (submitter && submitter.name && submitter.value) {
      if (!form.querySelector(`input[type="hidden"][name="${submitter.name}"]`)) {
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = submitter.name;
        hidden.value = submitter.value;
        form.appendChild(hidden);
      }
    }
    const btn = submitter || form.querySelector('button[type="submit"]');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Processing...';
    }
  });
});

// ── Sidebar Collapsible Groups ─────────────────────────────
document.querySelectorAll('.sidebar-group-toggle').forEach(toggle => {
  toggle.addEventListener('click', () => {
    const group = toggle.closest('.sidebar-group');
    group?.classList.toggle('open');
  });
});

// Auto-open the group containing the active nav item on page load
(function() {
  const activeItem = document.querySelector('.sidebar-group-items .nav-item.active');
  if (activeItem) {
    const group = activeItem.closest('.sidebar-group');
    group?.classList.add('open');
  }
})();

// ── Chart.js Enterprise Styling Default ────────────────────
if (typeof Chart !== 'undefined') {
  Chart.defaults.font.family = "'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = '#64748B';
  Chart.defaults.plugins.legend.position = 'bottom';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.padding = 16;
  // Smooth animations
  Chart.defaults.animation = { duration: 500, easing: 'easeInOutQuart' };
}

// ── Expose global EBT System utilities ───────────────────────
window.EBTSystem = { confirm: hrmsConfirm, toast: hrmsToast };
window.EBT = window.EBTSystem;
