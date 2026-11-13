// EBT System — Enterprise SaaS main.js

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

function openSidebar()  { sidebar?.classList.add('open');   overlay?.classList.add('active'); }
function closeSidebar() { sidebar?.classList.remove('open'); overlay?.classList.remove('active'); }

hamburger?.addEventListener('click', openSidebar);
overlay?.addEventListener('click', closeSidebar);

// ── Flash message auto-dismiss ─────────────────────────────
document.querySelectorAll('.flash-msg').forEach(msg => {
  const close = msg.querySelector('.close-flash');
  close?.addEventListener('click', () => msg.remove());
  setTimeout(() => msg?.remove(), 6000);
});

// ── Confirm dialogs ────────────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

// ── Active nav item detection ──────────────────────────────
(function() {
  const path = window.location.pathname;
  let bestMatch = null;
  let maxLen = -1;

  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (!href) return;
    const cleanHref = href.split('?')[0];

    // Check exact match (or query match)
    if (href === path || href === window.location.pathname + window.location.search) {
      bestMatch = item;
      maxLen = 99999;
    } else if (cleanHref !== '/' && (path === cleanHref || path.startsWith(cleanHref + '/'))) {
      if (cleanHref.length > maxLen) {
        bestMatch = item;
        maxLen = cleanHref.length;
      }
    } else if (cleanHref === '/' && path === '/' && maxLen < 0) {
      bestMatch = item;
      maxLen = 0;
    }
  });

  if (bestMatch) {
    document.querySelectorAll('.nav-item.active').forEach(el => el.classList.remove('active'));
    bestMatch.classList.add('active');
  }

  // Close sidebar on mobile when a nav-item is clicked
  document.querySelectorAll('.nav-item').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) {
        closeSidebar();
      }
    });
  });
})();

// ── Topbar live clock ──────────────────────────────────────
const clockEl = document.getElementById('liveClock');
if (clockEl) {
  function updateClock() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  updateClock();
  setInterval(updateClock, 1000);
}

// ── Form submit loading state with button-name preservation
document.querySelectorAll('form[data-loading]').forEach(form => {
  form.addEventListener('submit', (e) => {
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

// ── Chart.js Enterprise Styling Default ────────────────────
if (typeof Chart !== 'undefined') {
  Chart.defaults.font.family = "'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.color = '#64748B';
  Chart.defaults.plugins.legend.position = 'bottom';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.padding = 16;
}
