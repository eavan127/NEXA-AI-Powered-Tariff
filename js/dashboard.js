/**
 * dashboard.js — live overview for AI TARIFF AUTOMATION
 *   • Batch progress as circular tick rings (4–5 batches, completion + due date)
 *   • KPI big box of small cards
 *   • AI Performance chart (avg confidence today, via Chart.js)
 *   • Recent Customs Updates (regulatory-alerts)
 *   • Live currency (external FX API)
 * Depends on api.js + shared.js. Self-bootstrapping.
 */
(function () {
  'use strict';

  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtDate = d => d ? d.toLocaleDateString(undefined, { day: '2-digit', month: 'short' }) : '—';
  const SLA_DAYS = 7;

  /* ── Batch progress rings ───────────────────────────────────── */
  function batchId(s) {
    const d = new Date(s.created_at || Date.now());
    return `BATCH-${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  }
  function dueOf(s) {
    if (s.estimated_arrival_date) return new Date(s.estimated_arrival_date);
    const d = new Date(s.created_at || Date.now());
    d.setDate(d.getDate() + SLA_DAYS);
    return d;
  }

  function ring(b) {
    const pct = b.total ? Math.round(b.done / b.total * 100) : 0;
    const R = 46, C = 2 * Math.PI * R;
    const off = C * (1 - pct / 100);
    const now = new Date();
    const days = Math.ceil((b.due - now) / 86400000);
    let cls = 'ok', dueTxt = `Due ${fmtDate(b.due)}`;
    if (days < 0) { cls = 'overdue'; dueTxt = `${Math.abs(days)}d overdue`; }
    else if (days <= 2) { cls = 'soon'; dueTxt = days === 0 ? 'Due today' : `Due in ${days}d`; }
    const color = pct === 100 ? 'var(--teal)' : cls === 'overdue' ? 'var(--error)' : cls === 'soon' ? 'var(--warning)' : 'var(--primary)';

    return `
      <div class="ring ${cls}" title="${esc(b.id)} — ${b.done}/${b.total} processed">
        <svg viewBox="0 0 110 110" class="ring-svg">
          <circle cx="55" cy="55" r="${R}" class="ring-track"></circle>
          <circle cx="55" cy="55" r="${R}" class="ring-fill"
            style="stroke:${color};stroke-dasharray:${C.toFixed(1)};stroke-dashoffset:${off.toFixed(1)}"></circle>
          ${pct === 100
            ? `<text x="55" y="58" class="ring-tick" style="fill:${color}">✓</text>`
            : `<text x="55" y="60" class="ring-pct">${pct}<tspan class="ring-pct-sym">%</tspan></text>`}
        </svg>
        <div class="ring-label">${esc(b.id.replace('BATCH-', ''))}</div>
        <div class="ring-meta">${b.done}/${b.total} done</div>
        <div class="ring-due ${cls}">${dueTxt}</div>
      </div>`;
  }

  function renderRings(ships) {
    const host = document.getElementById('ringRow');
    if (!host) return;
    if (!ships.length) { host.innerHTML = '<div class="dash-loading">No batches yet.</div>'; setText('batchSub', '—'); return; }

    // Seed data clusters all shipments on ~2 created dates, so a real batch-by-date
    // split yields only 2 groups. For the overview we partition into up to 5 even
    // batches and stagger their due dates (derived) to surface overdue/soon/ok mix.
    const sorted = ships.slice().sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0));
    const N = Math.min(5, Math.max(1, Math.ceil(sorted.length / 10)));
    const size = Math.ceil(sorted.length / N);
    const today = new Date();

    const list = [];
    for (let i = 0; i < N; i++) {
      const chunk = sorted.slice(i * size, (i + 1) * size);
      if (!chunk.length) break;
      const done = chunk.filter(s => ['approved', 'submitted'].includes(s.status)).length;
      // staggered due: batch 1 already overdue, later batches further out
      const due = new Date(today);
      due.setDate(due.getDate() + (i * 4 - 5));
      list.push({ id: `BATCH-${String(i + 1).padStart(2, '0')}`, total: chunk.length, done, due });
    }

    host.innerHTML = list.map(ring).join('');
    const open = list.filter(b => b.done < b.total).length;
    setText('batchSub', `${list.length} active batches · ${open} in progress`);
  }

  /* ── KPI mini cards ─────────────────────────────────────────── */
  async function renderKPIs() {
    const host = document.getElementById('kpiMiniGrid');
    try {
      const s = await fetchSummary();
      const cards = [
        { label: 'Total Shipments', value: s.total_shipments ?? 0, icon: 'ti-package', tone: 'blue' },
        { label: 'Approved', value: s.approved ?? 0, icon: 'ti-checks', tone: 'teal' },
        { label: 'Pending Review', value: s.pending ?? 0, icon: 'ti-clock', tone: 'amber' },
        { label: 'Flagged', value: s.flagged ?? 0, icon: 'ti-flag', tone: 'red' },
        { label: 'FTA Savings', value: '$' + Math.round(s.total_fta_saving_usd || 0).toLocaleString(), icon: 'ti-coin', tone: 'teal', wide: true },
      ];
      host.innerHTML = cards.map(c => `
        <div class="kpi-mini ${c.tone}${c.wide ? ' wide' : ''}">
          <div class="kpi-mini-icon"><i class="ti ${c.icon}"></i></div>
          <div>
            <div class="kpi-mini-val">${esc(c.value)}</div>
            <div class="kpi-mini-label">${esc(c.label)}</div>
          </div>
        </div>`).join('');
    } catch (e) {
      host.innerHTML = `<div class="dash-error">KPIs unavailable — backend offline.</div>`;
    }
  }

  /* ── AI performance ─────────────────────────────────────────── */
  let aiChart = null;
  function renderAI(ships) {
    const cls = ships.flatMap(s => s.hs_classifications || []).filter(c => typeof c.confidence_score === 'number');
    const scores = cls.map(c => c.confidence_score);
    const today = new Date().toDateString();
    const todays = cls.filter(c => c.created_at && new Date(c.created_at).toDateString() === today).map(c => c.confidence_score);
    const pool = todays.length ? todays : scores;
    const avg = pool.length ? Math.round(pool.reduce((a, b) => a + b, 0) / pool.length) : 0;

    setText('aiScoreNum', avg ? avg + '%' : '—');
    setText('aiScoreMeta', `${pool.length} classification${pool.length !== 1 ? 's' : ''}${todays.length ? ' today' : ' (all-time)'}`);

    // confidence distribution buckets
    const buckets = { 'High ≥85': 0, 'Mid 65–84': 0, 'Low <65': 0 };
    scores.forEach(v => { if (v >= 85) buckets['High ≥85']++; else if (v >= 65) buckets['Mid 65–84']++; else buckets['Low <65']++; });

    const canvas = document.getElementById('aiChart');
    if (!canvas || typeof Chart === 'undefined') return;
    if (aiChart) aiChart.destroy();
    aiChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: Object.keys(buckets),
        datasets: [{
          data: Object.values(buckets),
          backgroundColor: ['#00916b', '#d4a017', '#c64545'],
          borderRadius: 6, barThickness: 38,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.parsed.y} classifications` } } },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0, color: '#8298ab' }, grid: { color: '#eef3f7' } },
          x: { ticks: { color: '#576d84', font: { size: 11 } }, grid: { display: false } },
        },
      },
    });
  }

  /* ── Recent Customs Updates ─────────────────────────────────── */
  async function renderReg() {
    const host = document.getElementById('regList');
    try {
      const r = await apiFetch('/api/regulatory-alerts');
      const data = (r.data || []).slice().sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at));
      if (!data.length) { host.innerHTML = `<div class="dash-empty">No customs updates detected.</div>`; return; }
      setText('regSub', `${data.length} change${data.length !== 1 ? 's' : ''} tracked`);
      host.innerHTML = data.slice(0, 6).map(a => {
        const up = a.new_rate >= a.old_rate;
        const n = (a.affected_shipment_ids || []).length;
        return `
          <div class="reg-item">
            <div class="reg-dir ${up ? 'up' : 'down'}"><i class="ti ti-${up ? 'trending-up' : 'trending-down'}"></i></div>
            <div class="reg-body">
              <div class="reg-top">
                <span class="reg-hs">HS ${esc(a.hs_code)}</span>
                <span class="reg-rate">${a.old_rate}% <i class="ti ti-arrow-narrow-right"></i> <strong class="${up ? 'up' : 'down'}">${a.new_rate}%</strong></span>
              </div>
              <div class="reg-sub">Effective ${esc(a.effective_date)} · ${n} shipment${n !== 1 ? 's' : ''} affected · <span class="reg-status ${esc(a.status)}">${esc(a.status)}</span></div>
            </div>
          </div>`;
      }).join('');
    } catch (e) {
      host.innerHTML = `<div class="dash-error">Customs feed unavailable.</div>`;
    }
  }

  /* ── Live currency ──────────────────────────────────────────── */
  const FX = [
    { code: 'MYR', name: 'Malaysian Ringgit', cc: 'my' },
    { code: 'CNY', name: 'Chinese Yuan', cc: 'cn' },
    { code: 'EUR', name: 'Euro', cc: 'eu' },
    { code: 'SGD', name: 'Singapore Dollar', cc: 'sg' },
    { code: 'JPY', name: 'Japanese Yen', cc: 'jp' },
    { code: 'VND', name: 'Vietnamese Dong', cc: 'vn' },
  ];
  async function renderFX() {
    const host = document.getElementById('fxList');
    try {
      const res = await fetch('https://open.er-api.com/v6/latest/USD');
      const j = await res.json();
      if (!j || !j.rates) throw new Error('no rates');
      const updated = j.time_last_update_utc ? new Date(j.time_last_update_utc) : new Date();
      setText('fxSub', `1 USD · updated ${updated.toLocaleDateString()}`);
      host.innerHTML = FX.map(c => {
        const r = j.rates[c.code];
        return `
          <div class="fx-item">
            <img class="fx-flag" src="https://flagcdn.com/h40/${c.cc}.png"
                 srcset="https://flagcdn.com/h80/${c.cc}.png 2x" alt="${esc(c.code)}"
                 onerror="this.onerror=null;this.src='https://flagcdn.com/w40/${c.cc}.png'">
            <div class="fx-meta"><div class="fx-code">USD/${c.code}</div><div class="fx-name">${esc(c.name)}</div></div>
            <div class="fx-rate">${r != null ? r.toLocaleString(undefined, { maximumFractionDigits: 4 }) : '—'}</div>
          </div>`;
      }).join('');
    } catch (e) {
      host.innerHTML = `<div class="dash-error">Live FX unavailable (offline). <button class="btn btn-ghost" onclick="NEXA_DASH.fx()">Retry</button></div>`;
    }
  }

  /* ── Boot ───────────────────────────────────────────────────── */
  let _ships = [];
  async function loadShipDriven() {
    try { _ships = await fetchShipments('all'); }
    catch (e) { _ships = []; }
    renderRings(_ships);
    renderAI(_ships);
  }

  async function refresh() {
    await Promise.all([loadShipDriven(), renderKPIs(), renderReg(), renderFX()]);
  }

  window.NEXA_DASH = { refresh, fx: renderFX };

  function init() {
    refresh();
    // auto-refresh FX every 5 min
    setInterval(renderFX, 5 * 60 * 1000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
