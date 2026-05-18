/**
 * app.js — Application logic
 * Jabil AI Tariff Calculation Engine · Use Case 2
 */

/* ── State ─────────────────────────────────────────────────────── */
let selectedIdx = 13; // Default: item #14 (flagged)
let activeFilter = 'all';

/* ── Utilities ─────────────────────────────────────────────────── */
function confColor(c) {
  if (c >= 95) return 'var(--teal)';
  if (c >= 85) return 'var(--amber)';
  return 'var(--error)';
}

function confLevel(c) {
  if (c >= 95) return 'hi';
  if (c >= 85) return 'mid';
  return 'lo';
}

function renderDots(conf) {
  const level  = confLevel(conf);
  const filled = conf >= 95 ? 5 : conf >= 85 ? 4 : conf >= 75 ? 3 : 2;
  return Array.from({ length: 5 }, (_, i) =>
    `<div class="cdot${i < filled ? ' ' + level : ''}"></div>`
  ).join('');
}

function ftaClass(fta) {
  if (fta === 'CPTPP') return 'fta-cptpp';
  if (fta === 'MFN')   return 'fta-mfn';
  return 'fta-other';
}

function formatDuty(duty) {
  if (duty === 0) return '$0';
  return '$' + duty.toLocaleString();
}

/* ── Table rendering ────────────────────────────────────────────── */
function renderTable() {
  const filtered = getFilteredItems();

  const html = filtered.map(item => {
    const realIdx = ITEMS.indexOf(item);
    const isSelected = realIdx === selectedIdx;

    return `
      <div class="tbl-row${isSelected ? ' sel' : ''}" onclick="selectItem(${realIdx})">
        <span class="row-num">${item.id}</span>
        <span class="hs-code">${item.hs.slice(0, 7)}</span>
        <span>
          <div class="prod-name">${item.name}</div>
          <div class="prod-origin">${item.origin} · ${item.status}</div>
        </span>
        <span class="conf-cell">
          <span style="font-size:11.5px;font-family:var(--mono);font-weight:500;color:${confColor(item.conf)};min-width:29px">
            ${item.conf}%
          </span>
          <div class="conf-dots">${renderDots(item.conf)}</div>
        </span>
        <span class="duty-cell" style="color:${item.duty === 0 ? 'var(--teal)' : 'var(--ink)'}">
          ${formatDuty(item.duty)}
        </span>
        <span class="fta-badge ${ftaClass(item.fta)}">${item.fta}</span>
        <span class="row-acts">
          <button
            class="ibt${item.status === 'approved' ? ' ok' : ''}"
            title="${item.status === 'approved' ? 'Approved' : 'Approve'}"
            onclick="event.stopPropagation(); approveRow(${realIdx})"
          ><i class="ti ti-check"></i></button>
          <button class="ibt flag-it" title="Flag" onclick="event.stopPropagation()">
            <i class="ti ti-flag"></i>
          </button>
          <button class="ibt" title="View details">
            <i class="ti ti-eye"></i>
          </button>
        </span>
      </div>`;
  }).join('');

  document.getElementById('tblBody').innerHTML = html;
}

function getFilteredItems() {
  switch (activeFilter) {
    case 'flagged':
      return ITEMS.filter(i => i.conf < 85 || i.status === 'flagged');
    case 'approved':
      return ITEMS.filter(i => i.status === 'approved');
    default:
      return ITEMS;
  }
}

/* ── Item selection ─────────────────────────────────────────────── */
function selectItem(idx) {
  selectedIdx = idx;
  renderTable();
}

/* ── Filter ─────────────────────────────────────────────────────── */
function setFilter(filter, btn) {
  activeFilter = filter;
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTable();
}

/* ── Approve single row ─────────────────────────────────────────── */
function approveRow(idx) {
  ITEMS[idx].status = 'approved';
  renderTable();
}

/* ── Bulk approve ───────────────────────────────────────────────── */
function doBulk() {
  ITEMS.forEach(item => {
    if (item.conf >= 95) item.status = 'approved';
  });
  renderTable();
}

/* ── Approve selected item (from detail panel) ──────────────────── */
function approveItem() {
  ITEMS[selectedIdx].status = 'approved';
  renderTable();
  openModal('approvedModal');
}

/* ── Submit batch ───────────────────────────────────────────────── */
function submitBatch() {
  closeModal('batchModal');

  // Update batch status pill
  const pill = document.getElementById('batchPill');
  if (pill) {
    pill.textContent = 'Submitted';
    pill.className = 'pill pill-submitted';
  }
}

/* ── Modal helpers ──────────────────────────────────────────────── */
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('open');
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('open');
}

// Close modal on overlay click
document.querySelectorAll('.overlay').forEach(overlay => {
  overlay.addEventListener('click', e => {
    if (e.target === overlay) overlay.classList.remove('open');
  });
});

// Close modal on Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.overlay.open').forEach(o => o.classList.remove('open'));
  }
});

/* ── Init ───────────────────────────────────────────────────────── */
renderTable();
