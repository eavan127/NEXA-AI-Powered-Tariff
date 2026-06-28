/**
 * shell.js — global app shell for AI TARIFF AUTOMATION
 * Renders the unified sidebar (NEXA logo + profile + nav + To-Do) and the
 * topbar (global search + inbox / alerts / notifications). Self-contained:
 * depends only on api.js (optional) and runs on every page.
 *
 * It REPLACES any existing <aside class="sidebar"> and <div class="topbar">
 * so the six pages stay in sync without hand-editing each one.
 */
(function () {
  'use strict';

  const PROFILE = {
    name:  'Sarah Lim',
    role:  'Trade Compliance Analyst',
    email: 'sarah.lim@jabil.com',
    initials: 'SL',
  };

  const NAV = [
    { group: 'Analysis', items: [
      { page: 'dashboard',    label: 'Dashboard',       icon: 'ti-layout-dashboard', href: 'dashboard.html' },
      { page: 'index',        label: 'Tariff Filters',  icon: 'ti-filter',        href: 'index.html' },
      { page: 'shipments',    label: 'All Shipments',   icon: 'ti-list-check',    href: 'shipments.html' },
      { page: 'verification', label: 'Validation',      icon: 'ti-shield-check',  href: 'verification.html' },
      { page: 'audit',        label: 'Audit Trail',     icon: 'ti-clock-history', href: 'audit.html' },
    ]},
    { group: 'Intelligence', items: [
      { page: 'chat',         label: 'AI Assistant',    icon: 'ti-message-chatbot', href: 'chat.html' },
      { page: 'fta-library',  label: 'FTA Library',     icon: 'ti-world',         href: 'fta-library.html' },
      { page: 'reports',      label: 'Analytics',       icon: 'ti-chart-bar',     href: 'reports.html' },
    ]},
    { group: 'System', items: [
      { page: '_seed',        label: 'Re-Seed Data',    icon: 'ti-database',      onclick: 'runSeedAndRefresh && runSeedAndRefresh()' },
      { page: '_config',      label: 'Configuration',   icon: 'ti-settings',      onclick: "(window.showToast||alert)('Configuration — coming soon')" },
    ]},
  ];

  const currentPage = (location.pathname.split('/').pop() || 'index.html').replace('.html', '') || 'index';

  /* ── escape helper ─────────────────────────────────────────── */
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ── inline SVG icons (bulletproof — no webfont dependency) ─── */
  const SVG = {
    menu:   '<path d="M3 6h18M3 12h18M3 18h18"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    plus:   '<path d="M12 5v14M5 12h14"/>',
    arrow:  '<path d="M5 12h14M13 6l6 6-6 6"/>',
    mail:   '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    alert:  '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4M12 17h.01"/>',
    bell:   '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
  };
  const svg = (name, sz = 20) =>
    `<svg viewBox="0 0 24 24" width="${sz}" height="${sz}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${SVG[name]}</svg>`;

  /* ── Sidebar markup ────────────────────────────────────────── */
  function sidebarHtml() {
    const nav = NAV.map(sec => `
      <div class="nav-section">
        <div class="nav-label">${sec.group}</div>
        ${sec.items.map(it => {
          const active = it.page === currentPage ? ' active' : '';
          const handler = it.onclick ? `onclick="${it.onclick}"` : `onclick="location='${it.href}'"`;
          return `<div class="nav-item${active}" data-page="${it.page}" ${handler}><i class="ti ${it.icon}"></i> ${it.label}</div>`;
        }).join('')}
      </div>`).join('');

    return `
      <div class="sidebar-brand" onclick="location='dashboard.html'" style="cursor:pointer" title="Go to Dashboard">
        <img class="brand-logo" src="assets/nexa-logo.png" alt="NEXA"
             onerror="this.classList.add('missing');this.outerHTML='<span class=&quot;brand-logo-text&quot;>NE<b>X</b>A</span>'">
        <div class="brand-system">AI TARIFF AUTOMATION</div>
      </div>

      <div class="sidebar-profile">
        <div class="profile-avatar">${esc(PROFILE.initials)}</div>
        <div class="profile-meta">
          <div class="profile-name">${esc(PROFILE.name)}</div>
          <div class="profile-email" title="${esc(PROFILE.email)}">${esc(PROFILE.email)}</div>
          <div class="profile-role">${esc(PROFILE.role)}</div>
        </div>
      </div>

      <nav class="nav">${nav}</nav>`;
  }

  /* ── Topbar markup ─────────────────────────────────────────── */
  function topbarHtml() {
    return `
      <button class="topbar-burger" title="Menu" onclick="document.body.classList.toggle('sidebar-hidden')">
        ${svg('menu')}
      </button>

      <form class="global-search" id="globalSearchForm" autocomplete="off">
        ${svg('search', 18)}
        <input id="globalSearchInput" type="text" placeholder="Search shipments, HS codes, contacts…">
        <button type="submit" class="global-search-btn">${svg('arrow', 18)}</button>
      </form>

      <div class="topbar-actions">
        <button class="topbar-add" title="New filter" onclick="location='index.html#new'">${svg('plus')}</button>

        <div class="topbar-menu" data-menu="inbox">
          <button class="topbar-icon" title="Inbox">${svg('mail')}<span class="badge badge-amber">1</span></button>
          <div class="topbar-pop">
            <div class="pop-head"><i class="ti ti-mail"></i> Inbox <span class="pop-tag">1 new</span></div>
            <div class="pop-list" id="popInbox"><div class="pop-loading">Loading…</div></div>
            <div class="pop-foot">Internal messages</div>
          </div>
        </div>

        <div class="topbar-menu" data-menu="alerts">
          <button class="topbar-icon" title="Alerts">${svg('alert')}<span class="badge badge-teal" id="alertBadge">·</span></button>
          <div class="topbar-pop">
            <div class="pop-head"><i class="ti ti-alert-triangle"></i> Regulatory Alerts <span class="pop-tag" id="alertTag">live</span></div>
            <div class="pop-list" id="popAlerts"><div class="pop-loading">Loading…</div></div>
            <div class="pop-foot"><a href="dashboard.html">Open dashboard →</a></div>
          </div>
        </div>

        <div class="topbar-menu" data-menu="notif">
          <button class="topbar-icon" title="Notifications">${svg('bell')}<span class="badge badge-blue">2</span></button>
          <div class="topbar-pop">
            <div class="pop-head"><i class="ti ti-bell"></i> Notifications <span class="pop-tag">2 new</span></div>
            <div class="pop-list" id="popNotif"><div class="pop-loading">Loading…</div></div>
            <div class="pop-foot"><a href="audit.html">View audit trail →</a></div>
          </div>
        </div>
      </div>`;
  }

  /* ── Mount: replace existing sidebar / topbar ──────────────── */
  function mount() {
    let aside = document.querySelector('aside.sidebar');
    if (!aside) {
      aside = document.createElement('aside');
      aside.className = 'sidebar';
      document.querySelector('.app')?.prepend(aside);
    }
    aside.classList.add('sidebar');
    aside.innerHTML = sidebarHtml();

    let topbar = document.querySelector('.topbar');
    if (!topbar) {
      topbar = document.createElement('div');
      topbar.className = 'topbar';
      (document.querySelector('.main') || document.body).prepend(topbar);
    }
    topbar.classList.add('topbar', 'topbar-shell');
    topbar.innerHTML = topbarHtml();

    wireSearch();
    wireMenus();
    loadPanels();
  }

  /* ── Dropdown menus (inbox / alerts / notifications) ───────── */
  function wireMenus() {
    const menus = [...document.querySelectorAll('.topbar-menu')];
    menus.forEach(m => {
      const btn = m.querySelector('.topbar-icon');
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const wasOpen = m.classList.contains('open');
        menus.forEach(x => x.classList.remove('open'));
        if (!wasOpen) m.classList.add('open');
      });
      m.querySelector('.topbar-pop').addEventListener('click', e => e.stopPropagation());
    });
    document.addEventListener('click', () => menus.forEach(x => x.classList.remove('open')));
  }

  function popRow(icon, tone, title, sub, time) {
    return `<div class="pop-item">
      <div class="pop-ico ${tone}"><i class="ti ${icon}"></i></div>
      <div class="pop-body"><div class="pop-title">${esc(title)}</div><div class="pop-sub">${esc(sub)}</div></div>
      ${time ? `<div class="pop-time">${esc(time)}</div>` : ''}
    </div>`;
  }

  async function loadPanels() {
    // Inbox (internal messages)
    const inbox = document.getElementById('popInbox');
    if (inbox) inbox.innerHTML = [
      popRow('ti-message', 'blue', 'Compliance review request', 'Please verify HS 8542.31 on BATCH-02', '2h'),
      popRow('ti-user-check', 'teal', 'Manager approved batch', 'BATCH-01 cleared for SAP submission', '5h'),
      popRow('ti-file-text', 'amber', 'New supplier declaration', 'COO certificate uploaded for SHIP034', '1d'),
    ].join('');

    // Notifications (activity)
    const notif = document.getElementById('popNotif');
    if (notif) notif.innerHTML = [
      popRow('ti-robot', 'blue', 'AI classification complete', '74 shipments classified · avg 76% confidence', 'now'),
      popRow('ti-coin', 'teal', 'FTA savings updated', '$18,226 total duty saved this month', '3h'),
    ].join('');

    // Alerts (LIVE from regulatory-alerts)
    const alerts = document.getElementById('popAlerts');
    if (!alerts) return;
    try {
      const r = await apiFetch('/api/regulatory-alerts');
      const data = (r.data || []).sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at));
      const badge = document.getElementById('alertBadge'), tag = document.getElementById('alertTag');
      if (badge) badge.textContent = data.length || '0';
      if (tag) tag.textContent = data.length ? `${data.length} active` : 'none';
      alerts.innerHTML = data.length ? data.slice(0, 5).map(a => {
        const up = a.new_rate >= a.old_rate;
        const n = (a.affected_shipment_ids || []).length;
        return popRow(up ? 'ti-trending-up' : 'ti-trending-down', up ? 'red' : 'teal',
          `HS ${a.hs_code}: ${a.old_rate}% → ${a.new_rate}%`,
          `Effective ${a.effective_date} · ${n} shipment${n !== 1 ? 's' : ''} affected`, '');
      }).join('') : '<div class="pop-empty">No active alerts.</div>';
    } catch (e) {
      alerts.innerHTML = '<div class="pop-empty">Alerts feed offline.</div>';
      const badge = document.getElementById('alertBadge'); if (badge) badge.textContent = '!';
    }
  }

  /* ── Global search → jump to lookup on Enter ───────────────── */
  function wireSearch() {
    const form = document.getElementById('globalSearchForm');
    const input = document.getElementById('globalSearchInput');
    if (!form || !input) return;

    // Pre-fill from ?q= so the term survives the redirect
    const q0 = new URLSearchParams(location.search).get('q');
    if (q0) input.value = q0;

    form.addEventListener('submit', e => {
      e.preventDefault();
      const q = input.value.trim();
      // On the lookup page we filter in place; elsewhere we jump to it.
      if (currentPage === 'index' && typeof window.applyGlobalSearch === 'function') {
        window.applyGlobalSearch(q);
      } else {
        location.href = 'index.html?q=' + encodeURIComponent(q) + '#lookup';
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
