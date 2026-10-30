// EBT System — main.js

// ── Sidebar toggle (mobile) ────────────────────────────────
const sidebar  = document.getElementById('sidebar');
const overlay  = document.getElementById('sidebarOverlay');
const hamburger = document.getElementById('hamburger');

function openSidebar()  { sidebar?.classList.add('open');   overlay?.classList.add('active'); }
function closeSidebar() { sidebar?.classList.remove('open'); overlay?.classList.remove('active'); }

hamburger?.addEventListener('click', openSidebar);
overlay?.addEventListener('click', closeSidebar);

// ── Flash message auto-dismiss ─────────────────────────────
document.querySelectorAll('.flash-msg').forEach(msg => {
  const close = msg.querySelector('.close-flash');
  close?.addEventListener('click', () => msg.remove());
  setTimeout(() => msg?.remove(), 5000);
});

// ── Confirm dialogs ────────────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

// ── Active nav item ────────────────────────────────────────
(function() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (href && href !== '/' && path.startsWith(href)) {
      item.classList.add('active');
    } else if (href === '/' && path === '/') {
      item.classList.add('active');
    }
  });
})();

// ── Clock in topbar ────────────────────────────────────────
const clockEl = document.getElementById('liveClock');
if (clockEl) {
  function updateClock() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  updateClock();
  setInterval(updateClock, 1000);
}

// ── Form submit loading state ──────────────────────────────
document.querySelectorAll('form[data-loading]').forEach(form => {
  form.addEventListener('submit', (e) => {
    // If the submitter is a button with a name/value (e.g. approve/reject), preserve its value via hidden input before disabling
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
      btn.innerHTML = '<span class="spinner"></span> Please wait...';
    }
  });
});

// ── Chart.js default styling ───────────────────────────────
if (typeof Chart !== 'undefined') {
  Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = '#64748B';
  Chart.defaults.plugins.legend.position = 'bottom';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.padding = 16;
}
