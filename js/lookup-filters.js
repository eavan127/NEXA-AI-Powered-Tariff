/**
 * lookup-filters.js — AI Tariff Filters page
 * Reusable FilterBlock: a ticket-style filter panel + professional results
 * table with column visibility, in-table search, pagination, and a WORKING
 * Excel (.xlsx) export via SheetJS. "New Filter" stacks independent blocks
 * on the same page, each with its own filters and export.
 *
 * Self-contained (index.html does not load shared.js). Depends on api.js.
 */
(function () {
  'use strict';

  /* ── shared shipment cache (fetched once, reused by every block) ── */
  let _cache = null, _loading = null;

  async function getShipments() {
    if (_cache) return _cache;
    if (_loading) return _loading;
    _loading = (async () => {
      let raw = [];
      try {
        if (typeof fetchShipments === 'function') raw = await fetchShipments('all');
      } catch (_) { /* offline → fall back */ }
      if (!raw || !raw.length) raw = fallbackFromItems();
      _cache = raw.map(normalize);
      return _cache;
    })();
    return _loading;
  }

  function fallbackFromItems() {
    const items = (typeof ITEMS !== 'undefined' && Array.isArray(ITEMS)) ? ITEMS : [];
    if (!items.length) return [];
    const now = Date.now();
    return items.map((it, i) => ({
      sap_shipment_id: 'SHIP' + String(it.id || i + 1).padStart(3, '0'),
      product_description: it.name,
      origin_country: it.origin,
      destination_country: 'United States',
      shipment_value_usd: it.shipmentValue || 0,
      status: it.status || 'pending',
      created_at: new Date(now - (it.id || i) * 86400000 * 1.5).toISOString(),
      estimated_arrival_date: null,
      transport_mode: null,
      regulatory_flag: false,
    }));
  }

  /* ── normalize either data shape into one record ─────────────── */
  function normalize(s) {
    const value = +(s.shipment_value_usd ?? s.shipmentValue ?? 0) || 0;
    const reg = !!s.regulatory_flag;
    let priority = 'Low';
    if (reg || value >= 50000) priority = 'High';
    else if (value >= 10000) priority = 'Medium';
    return {
      ref:        s.sap_shipment_id || s.id || '—',
      product:    s.product_description || s.name || '—',
      origin:     s.origin_country || s.origin || '—',
      dest:       s.destination_country || 'Malaysia',
      value,
      status:     (s.status || 'pending').toLowerCase(),
      created:    s.created_at ? new Date(s.created_at) : null,
      eta:        s.estimated_arrival_date ? new Date(s.estimated_arrival_date) : null,
      transport:  s.transport_mode || null,
      reg,
      priority,
    };
  }

  /* ── small helpers ───────────────────────────────────────────── */
  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const money = n => '$' + (+n || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  const fmtD = d => d ? d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
  const fmtDdmy = d => d ? `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${d.getFullYear()}` : '—';
  const titleCase = s => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  function periodRange(period) {
    const now = new Date();
    const y = now.getFullYear(), m = now.getMonth();
    switch (period) {
      case 'this_month':  return [new Date(y, m, 1), new Date(y, m + 1, 0, 23, 59, 59)];
      case 'last_month':  return [new Date(y, m - 1, 1), new Date(y, m, 0, 23, 59, 59)];
      case 'this_quarter':{ const q = Math.floor(m / 3) * 3; return [new Date(y, q, 1), new Date(y, q + 3, 0, 23, 59, 59)]; }
      case 'this_year':   return [new Date(y, 0, 1), new Date(y, 11, 31, 23, 59, 59)];
      default:            return [null, null]; // all time
    }
  }

  const statusPill = s => `<span class="pill pill-${esc(s)}">${esc(titleCase(s))}</span>`;
  const prioPill   = p => `<span class="prio prio-${p.toLowerCase()}">${p}</span>`;

  /* ── column definitions ──────────────────────────────────────── */
  const COLS = [
    { key: 'ref',      label: '#',         render: r => `<span class="mono">${esc(r.ref)}</span>` },
    { key: 'product',  label: 'Shipment',  render: r => `<span class="cell-strong">${esc(r.product)}</span>` },
    { key: 'route',    label: 'Route',     render: r => `${esc(r.origin)} <i class="ti ti-arrow-narrow-right"></i> ${esc(r.dest)}` },
    { key: 'status',   label: 'Status',    render: r => statusPill(r.status) },
    { key: 'priority', label: 'Priority',  render: r => prioPill(r.priority) },
    { key: 'value',    label: 'Value',     render: r => `<span class="mono">${money(r.value)}</span>` },
    { key: 'created',  label: 'Created',   render: r => fmtD(r.created) },
    { key: 'tags',     label: 'Tags',      render: r => r.reg ? '<span class="tag tag-reg">Regulatory</span>' : '<span class="muted">—</span>' },
  ];

  /* ── FilterBlock ─────────────────────────────────────────────── */
  let SEQ = 0;
  class FilterBlock {
    constructor(host, opts = {}) {
      this.id = ++SEQ;
      this.host = host;
      this.name = opts.name || (this.id === 1 ? 'Monthly report' : 'Filter ' + this.id);
      this.state = {
        status: 'all', origin: 'all', dest: 'all', priority: 'all',
        transport: 'all', period: 'this_month', dateField: 'created',
        tags: 'all', groupBy: 'none',
        search: '', pageSize: 25, page: 1, isDefault: false,
        ...opts.state,
      };
      this.visible = new Set(COLS.map(c => c.key));
      this.rows = [];
      this.render();
      this.apply();
    }

    el(sel) { return this.wrap.querySelector(sel); }

    render() {
      this.wrap = document.createElement('section');
      this.wrap.className = 'filter-block';
      this.wrap.innerHTML = `
        <div class="fb-panel">
          <div class="fb-panel-head">
            <div class="fb-title">AI Tariff Filters
              <input class="fb-name" value="${esc(this.name)}" title="Filter template name">
            </div>
            <div class="fb-panel-actions">
              <button class="btn btn-ghost fb-reset"><i class="ti ti-rotate"></i> Reset</button>
              <button class="btn btn-primary fb-apply"><i class="ti ti-filter"></i> Apply Filter</button>
              ${this.id === 1 ? '' : '<button class="btn btn-ghost fb-remove" title="Remove this filter"><i class="ti ti-x"></i></button>'}
            </div>
          </div>
          <div class="fb-grid"></div>
          <div class="fb-panel-foot">
            <label class="fb-check"><input type="checkbox" class="fb-default"> Set as Default</label>
            <span class="fb-report"><i class="ti ti-circle-check-filled"></i> ${esc(this.name)}</span>
          </div>
        </div>

        <div class="fb-results card">
          <div class="dt-toolbar">
            <div class="dt-left">
              <select class="dt-size">
                <option>10</option><option selected>25</option><option>50</option><option>100</option>
              </select>
              <div class="dt-colvis">
                <button class="btn btn-ghost dt-colvis-btn"><i class="ti ti-columns"></i> Column visibility</button>
                <div class="dt-colvis-menu"></div>
              </div>
              <button class="btn btn-ghost dt-export"><i class="ti ti-file-spreadsheet"></i> Export Excel</button>
            </div>
            <div class="dt-right">
              <i class="ti ti-search"></i>
              <input class="dt-search" type="text" placeholder="Search…">
            </div>
          </div>
          <div class="dt-caption"></div>
          <div class="dt-table-wrap">
            <table class="dt-table"><thead></thead><tbody></tbody></table>
          </div>
          <div class="dt-foot">
            <div class="dt-info"></div>
            <div class="dt-pager"></div>
          </div>
        </div>`;
      this.host.appendChild(this.wrap);
      this.buildFilterGrid();
      this.buildColVis();
      this.wire();
    }

    buildFilterGrid() {
      // option lists derived after data loads; start with static, refresh later
      const sel = (label, key, options) => `
        <div class="fb-field">
          <label>${label}</label>
          <select data-key="${key}">${options.map(o =>
            `<option value="${o.v}"${this.state[key] === o.v ? ' selected' : ''}>${esc(o.t)}</option>`).join('')}</select>
        </div>`;

      const statusOpts = [['all','All'],['pending','Pending'],['approved','Approved'],['flagged','Flagged'],['submitted','Submitted']];
      const prioOpts   = [['all','All'],['High','High'],['Medium','Medium'],['Low','Low']];
      const periodOpts = [['this_month','This Month'],['last_month','Last Month'],['this_quarter','This Quarter'],['this_year','This Year'],['all','All Time']];
      const dateOpts   = [['created','Created Date'],['eta','Est. Arrival']];
      const tagOpts    = [['all','All'],['reg','Regulatory only'],['none','No flag']];
      const groupOpts  = [['none','None'],['status','Status'],['origin','Origin'],['dest','Destination'],['priority','Priority']];

      const map = a => a.map(([v, t]) => ({ v, t }));
      this.el('.fb-grid').innerHTML =
        sel('Status', 'status', map(statusOpts)) +
        sel('Origin', 'origin', map([['all','All Origins']])) +
        sel('Destination', 'dest', map([['all','All Destinations']])) +
        sel('Priority', 'priority', map(prioOpts)) +
        sel('Service / Mode', 'transport', map([['all','All Modes']])) +
        sel('Period', 'period', map(periodOpts)) +
        sel('Filter By Date', 'dateField', map(dateOpts)) +
        sel('Tags', 'tags', map(tagOpts)) +
        sel('Group By', 'groupBy', map(groupOpts));
    }

    async refreshDynamicOptions() {
      const all = await getShipments();
      const distinct = key => [...new Set(all.map(r => r[key]).filter(Boolean))].sort();
      const fill = (selKey, values, allLabel) => {
        const s = this.el(`select[data-key="${selKey}"]`);
        if (!s) return;
        const cur = this.state[selKey];
        s.innerHTML = `<option value="all">${allLabel}</option>` +
          values.map(v => `<option value="${esc(v)}"${cur === v ? ' selected' : ''}>${esc(v)}</option>`).join('');
      };
      fill('origin', distinct('origin'), 'All Origins');
      fill('dest', distinct('dest'), 'All Destinations');
      fill('transport', distinct('transport'), 'All Modes');
    }

    buildColVis() {
      this.el('.dt-colvis-menu').innerHTML = COLS.map(c => `
        <label><input type="checkbox" data-col="${c.key}" ${this.visible.has(c.key) ? 'checked' : ''}> ${esc(c.label)}</label>`).join('');
    }

    wire() {
      this.el('.fb-apply').addEventListener('click', () => this.apply());
      this.el('.fb-reset').addEventListener('click', () => this.reset());
      this.el('.fb-remove')?.addEventListener('click', () => this.remove());
      this.el('.fb-name').addEventListener('input', e => {
        this.name = e.target.value || 'Filter ' + this.id;
        this.el('.fb-report').innerHTML = `<i class="ti ti-circle-check-filled"></i> ${esc(this.name)}`;
      });
      this.el('.fb-default').addEventListener('change', e => { this.state.isDefault = e.target.checked; });

      this.el('.dt-size').addEventListener('change', e => { this.state.pageSize = +e.target.value; this.state.page = 1; this.draw(); });
      this.el('.dt-search').addEventListener('input', e => { this.state.search = e.target.value.toLowerCase(); this.state.page = 1; this.draw(); });
      this.el('.dt-export').addEventListener('click', () => this.exportExcel());

      const cvBtn = this.el('.dt-colvis-btn'), cvMenu = this.el('.dt-colvis-menu');
      cvBtn.addEventListener('click', e => { e.stopPropagation(); cvMenu.classList.toggle('open'); });
      cvMenu.addEventListener('click', e => e.stopPropagation());
      cvMenu.addEventListener('change', e => {
        const k = e.target.getAttribute('data-col');
        if (e.target.checked) this.visible.add(k); else this.visible.delete(k);
        this.draw();
      });
      document.addEventListener('click', () => cvMenu.classList.remove('open'));
    }

    readFilters() {
      this.el('.fb-grid').querySelectorAll('select[data-key]').forEach(s => {
        this.state[s.getAttribute('data-key')] = s.value;
      });
    }

    async apply() {
      this.readFilters();
      const all = await getShipments();
      const [from, to] = periodRange(this.state.period);
      const f = this.state;

      this.rows = all.filter(r => {
        if (f.status !== 'all' && r.status !== f.status) return false;
        if (f.origin !== 'all' && r.origin !== f.origin) return false;
        if (f.dest !== 'all' && r.dest !== f.dest) return false;
        if (f.priority !== 'all' && r.priority !== f.priority) return false;
        if (f.transport !== 'all' && r.transport !== f.transport) return false;
        if (f.tags === 'reg' && !r.reg) return false;
        if (f.tags === 'none' && r.reg) return false;
        if (from && to) {
          const d = f.dateField === 'eta' ? r.eta : r.created;
          if (!d || d < from || d > to) return false;
        }
        return true;
      });

      this.range = [from, to];
      this.state.page = 1;
      this.draw();
    }

    reset() {
      Object.assign(this.state, {
        status: 'all', origin: 'all', dest: 'all', priority: 'all',
        transport: 'all', period: 'this_month', dateField: 'created', tags: 'all', groupBy: 'none',
        search: '', page: 1,
      });
      this.el('.dt-search').value = '';
      this.buildFilterGrid();
      this.refreshDynamicOptions().then(() => this.apply());
    }

    remove() { this.wrap.remove(); const i = BLOCKS.indexOf(this); if (i >= 0) BLOCKS.splice(i, 1); }

    /* visible + search-filtered rows */
    filteredRows() {
      const q = this.state.search;
      if (!q) return this.rows;
      return this.rows.filter(r =>
        [r.ref, r.product, r.origin, r.dest, r.status, r.priority].join(' ').toLowerCase().includes(q));
    }

    draw() {
      let rows = this.filteredRows();
      const cols = COLS.filter(c => this.visible.has(c.key));
      const thead = this.el('.dt-table thead');
      const tbody = this.el('.dt-table tbody');

      thead.innerHTML = `<tr>${cols.map(c => `<th>${esc(c.label)}</th>`).join('')}</tr>`;

      // group-by header rows
      const group = this.state.groupBy;
      const keyOf = r => group === 'origin' ? r.origin : group === 'dest' ? r.dest
        : group === 'priority' ? r.priority : group === 'status' ? titleCase(r.status) : null;

      // cluster rows by group key so each group appears once
      if (group !== 'none') {
        rows = [...rows].sort((a, b) => String(keyOf(a)).localeCompare(String(keyOf(b))));
      }

      // pagination
      const size = this.state.pageSize;
      const pages = Math.max(1, Math.ceil(rows.length / size));
      this.state.page = Math.min(this.state.page, pages);
      const start = (this.state.page - 1) * size;
      const pageRows = rows.slice(start, start + size);

      let html = '', lastGroup = null;
      if (!pageRows.length) {
        html = `<tr><td class="dt-empty" colspan="${cols.length}">No shipments match this filter.</td></tr>`;
      } else {
        pageRows.forEach(r => {
          if (group !== 'none') {
            const g = keyOf(r);
            if (g !== lastGroup) {
              html += `<tr class="dt-group"><td colspan="${cols.length}"><i class="ti ti-folder"></i> ${esc(g)}</td></tr>`;
              lastGroup = g;
            }
          }
          html += `<tr>${cols.map(c => `<td>${c.render(r)}</td>`).join('')}</tr>`;
        });
      }
      tbody.innerHTML = html;

      // caption
      const [from, to] = this.range || [null, null];
      this.el('.dt-caption').innerHTML = (from && to)
        ? `for Period <strong>${fmtDdmy(from)}</strong> to <strong>${fmtDdmy(to)}</strong> · ${rows.length} record${rows.length !== 1 ? 's' : ''}`
        : `All time · ${rows.length} record${rows.length !== 1 ? 's' : ''}`;

      // info + pager
      const showFrom = rows.length ? start + 1 : 0;
      const showTo = Math.min(start + size, rows.length);
      this.el('.dt-info').textContent = `Showing ${showFrom} to ${showTo} of ${rows.length} entries`;
      this.el('.dt-pager').innerHTML = this.pagerHtml(pages);
      this.el('.dt-pager').querySelectorAll('[data-pg]').forEach(b =>
        b.addEventListener('click', () => { this.state.page = +b.getAttribute('data-pg'); this.draw(); }));
    }

    pagerHtml(pages) {
      if (pages <= 1) return '';
      const p = this.state.page;
      let out = `<button class="pg" data-pg="${Math.max(1, p - 1)}" ${p === 1 ? 'disabled' : ''}>Prev</button>`;
      for (let i = 1; i <= pages; i++) {
        if (i === 1 || i === pages || Math.abs(i - p) <= 1) out += `<button class="pg ${i === p ? 'active' : ''}" data-pg="${i}">${i}</button>`;
        else if (Math.abs(i - p) === 2) out += `<span class="pg-dots">…</span>`;
      }
      out += `<button class="pg" data-pg="${Math.min(pages, p + 1)}" ${p === pages ? 'disabled' : ''}>Next</button>`;
      return out;
    }

    /* ── Excel export (SheetJS) ───────────────────────────────── */
    exportExcel() {
      if (typeof XLSX === 'undefined') {
        (window.showToast || alert)('Excel library not loaded — check your connection and retry.');
        return;
      }
      const rows = this.filteredRows();
      if (!rows.length) { (window.showToast || alert)('Nothing to export — no rows match this filter.'); return; }

      const data = rows.map(r => ({
        'Shipment ID': r.ref,
        'Product': r.product,
        'Origin': r.origin,
        'Destination': r.dest,
        'Status': titleCase(r.status),
        'Priority': r.priority,
        'Value (USD)': r.value,
        'Regulatory Flag': r.reg ? 'Yes' : 'No',
        'Created': fmtD(r.created),
        'Est. Arrival': fmtD(r.eta),
      }));

      const ws = XLSX.utils.json_to_sheet(data);
      ws['!cols'] = [{ wch: 14 }, { wch: 40 }, { wch: 16 }, { wch: 16 }, { wch: 12 }, { wch: 10 }, { wch: 14 }, { wch: 16 }, { wch: 14 }, { wch: 14 }];
      const wb = XLSX.utils.book_new();
      const safe = (this.name || 'filter').replace(/[^\w-]+/g, '_').slice(0, 28);
      XLSX.utils.book_append_sheet(wb, ws, safe.slice(0, 31) || 'Export');
      const stamp = new Date().toISOString().slice(0, 10);
      XLSX.writeFile(wb, `AI-Tariff_${safe}_${stamp}.xlsx`);
      (window.showToast || function () {})(`Exported ${rows.length} rows to Excel.`);
    }
  }

  /* ── page wiring ─────────────────────────────────────────────── */
  const BLOCKS = [];
  let HOST = null;

  function addBlock(opts) {
    const b = new FilterBlock(HOST, opts);
    BLOCKS.push(b);
    b.refreshDynamicOptions().then(() => b.apply());
    return b;
  }

  // global search hook used by shell.js
  window.applyGlobalSearch = function (q) {
    if (!BLOCKS.length) return;
    const first = BLOCKS[0];
    first.state.search = (q || '').toLowerCase();
    const inp = first.el('.dt-search'); if (inp) inp.value = q || '';
    first.state.page = 1;
    first.draw();
    first.wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  function init() {
    HOST = document.getElementById('filterBlocks');
    if (!HOST) return;

    const url = new URLSearchParams(location.search);
    const first = addBlock({ name: 'Monthly report' });

    document.getElementById('newFilterBtn')?.addEventListener('click', () => {
      const b = addBlock({ name: 'Filter ' + (BLOCKS.length) });
      b.wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    // honor ?q= and ?batch= from shell navigation
    const q = url.get('q');
    if (q) setTimeout(() => window.applyGlobalSearch(q), 400);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
