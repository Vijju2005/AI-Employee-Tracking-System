// EBT System — Enterprise SaaS main.js

// ── Initialize Lucide Icons ────────────────────────────────
function initLucideIcons() {
  if (typeof lucide !== 'undefined' && lucide.createIcons) {
    lucide.createIcons();
  }
}

document.addEventListener('DOMContentLoaded', initLucideIcons);

// ── Sidebar Dropdown & Navigation System ────────────────────
function initSidebarNavigation() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const hamburger = document.getElementById('hamburger');
  const sidebarClose = document.getElementById('sidebarClose');

  // Mobile drawer controls
  function openSidebar() {
    sidebar?.classList.add('open');
    overlay?.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    sidebar?.classList.remove('open');
    overlay?.classList.remove('active');
    document.body.style.overflow = '';
  }

  hamburger?.addEventListener('click', openSidebar);
  sidebarClose?.addEventListener('click', closeSidebar);
  overlay?.addEventListener('click', closeSidebar);

  // Close sidebar on mobile when a link is clicked
  document.querySelectorAll('.sidebar-sublink, .sidebar-direct-link').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 1024) {
        closeSidebar();
      }
    });
  });

  // Main section dropdown toggle
  document.querySelectorAll('.sidebar-menu-btn[data-toggle="dropdown"]').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      const submenu = this.nextElementSibling;
      if (!submenu) return;
      const isOpen = submenu.classList.contains('open');

      if (isOpen) {
        submenu.classList.remove('open');
        this.classList.remove('expanded');
        this.setAttribute('aria-expanded', 'false');
      } else {
        submenu.classList.add('open');
        this.classList.add('expanded');
        this.setAttribute('aria-expanded', 'true');
      }
    });
  });

  // Nested dropdown toggle (e.g. Leaves inside Attendance)
  document.querySelectorAll('.sidebar-nested-btn[data-toggle="nested"]').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      const nestedMenu = this.nextElementSibling;
      if (!nestedMenu) return;
      const isOpen = nestedMenu.classList.contains('open');

      if (isOpen) {
        nestedMenu.classList.remove('open');
        this.classList.remove('expanded');
        this.setAttribute('aria-expanded', 'false');
      } else {
        nestedMenu.classList.add('open');
        this.classList.add('expanded');
        this.setAttribute('aria-expanded', 'true');
      }
    });
  });

  // Highlight active menu and auto-expand parent section
  highlightActiveSidebarMenu();
}

function highlightActiveSidebarMenu() {
  const currentPath = window.location.pathname;
  const currentSearch = window.location.search;
  const fullUrl = currentPath + currentSearch;

  // 1. Direct links check (e.g. Holidays)
  document.querySelectorAll('.sidebar-direct-link').forEach(link => {
    const href = link.getAttribute('href');
    if (href && (href === fullUrl || href === currentPath)) {
      link.classList.add('active');
    }
  });

  // 2. Submenu links check
  const sublinks = Array.from(document.querySelectorAll('.sidebar-sublink'));
  if (!sublinks.length) return;

  // Exact match (including query params, e.g. view=grid vs view=list)
  let matchedLink = sublinks.find(link => link.getAttribute('href') === fullUrl);

  // If not matched, try pathname match (longest path wins)
  if (!matchedLink) {
    const matches = sublinks
      .filter(link => {
        const href = link.getAttribute('href');
        if (!href || href === '/') return false;
        const cleanHref = href.split('?')[0];
        return currentPath === cleanHref || (cleanHref !== '/' && currentPath.startsWith(cleanHref));
      })
      .sort((a, b) => b.getAttribute('href').length - a.getAttribute('href').length);

    if (matches.length > 0) {
      matchedLink = matches[0];
    }
  }

  // If on root path '/', match dashboard
  if (!matchedLink && currentPath === '/') {
    matchedLink = sublinks.find(link => {
      const h = link.getAttribute('href');
      return h && (h.includes('/dashboard/admin') || h.includes('/dashboard/employee'));
    });
  }

  if (matchedLink) {
    matchedLink.classList.add('active');

    // If inside nested menu (e.g. Leaves), expand nested menu & toggle button
    const nestedMenu = matchedLink.closest('.sidebar-nested-menu');
    if (nestedMenu) {
      nestedMenu.classList.add('open');
      const nestedBtn = nestedMenu.previousElementSibling;
      if (nestedBtn && nestedBtn.classList.contains('sidebar-nested-btn')) {
        nestedBtn.classList.add('expanded');
        nestedBtn.setAttribute('aria-expanded', 'true');
      }
    }

    // Expand parent submenu & toggle button
    const parentSubmenu = matchedLink.closest('.sidebar-submenu');
    if (parentSubmenu) {
      parentSubmenu.classList.add('open');
      const parentBtn = parentSubmenu.previousElementSibling;
      if (parentBtn && parentBtn.classList.contains('sidebar-menu-btn')) {
        parentBtn.classList.add('expanded', 'active-parent');
        parentBtn.setAttribute('aria-expanded', 'true');
      }
    }
  }
}

document.addEventListener('DOMContentLoaded', initSidebarNavigation);

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
