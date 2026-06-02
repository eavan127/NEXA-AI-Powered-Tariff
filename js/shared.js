/**
 * shared.js — utilities used across ALL NEXA pages
 * Load BEFORE api.js and any page-specific JS.
 * index.html does NOT load this (it uses app.js which has its own helpers).
 */

/* ── DOM helpers ──────────────────────────────────────────────── */
const $ = id => document.getElementById(id)
function setHtml(id, h) { const e = $(id); if (e) e.innerHTML = h }
function setText(id, t) { const e = $(id); if (e) e.textContent = t }

/* ── Formatters ───────────────────────────────────────────────── */
function money(n) {
  return '$' + (+n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function pct(n)       { return (n ?? 0) + '%' }
function confColor(c) {
  if (c >= 95) return 'var(--teal)'
  if (c >= 85) return 'var(--amber)'
  return 'var(--error)'
}
function statusColor(s) {
  approved: 'var(--teal)', flagged: 'var(--error)', pending: 'var(--amber)', submitted: '#6366f1' }[s] || 'var(--muted)'
}
function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
function timeAgo(iso) {
  if (!iso) return '—'
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60)    return diff + 's ago'
  if (diff < 3600)  return Math.floor(diff / 60) + 'm ago'
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago'
  return new Date(iso).toLocaleDateString()
}
function pDot(done, lbl) {
  return done
    ? `<span style="font-size:10px;color:var(--teal)">✓ ${lbl}</span>`
    : `<span style="font-size:10px;color:#ccc">○ ${lbl}</span>`
}
function renderDots(c) {
  const f  = c >= 95 ? 5 : c >= 85 ? 4 : c >= 75 ? 3 : 2
  const lv = c >= 95 ? 'hi' : c >= 85 ? 'mid' : 'lo'
  return Array.from({ length: 5 }, (_, i) =>
    `<div class="cdot${i < f ? ' ' + lv : ''}"></div>`
  ).join('')
}

/* ── Toast ────────────────────────────────────────────────────── */
function showToast(msg, isError = false) {
  const t = $('toast'); if (!t) return
  const msgEl = $('toastMsg')
  if (msgEl) msgEl.textContent = msg; else t.childNodes[0] && (t.childNodes[0].textContent = msg)
  t.style.background = isError ? '#dc2626' : '#0d9488'
  t.classList.add('show')
  // clear any previous auto-close timer
  clearTimeout(t._autoClose)
  // auto-close errors after 10 s, success messages after 7 s — user can also click ×
  t._autoClose = setTimeout(() => t.classList.remove('show'), isError ? 10000 : 7000)
}

/* ── Modal helpers ────────────────────────────────────────────── */
function openModal(id)  { $(id)?.classList.add('open') }
function closeModal(id) { $(id)?.classList.remove('open') }

/* ── Seed (available from any page) ──────────────────────────── */
async function runSeedAndRefresh() {
  showToast('Seeding database… please wait')
  try {
    const r = await runSeed()
    const n   = r.result?.shipments || 0
    const cls = r.result?.mock_classifications || 0
    showToast(`✓ Seed done — ${n} shipments, ${cls} classifications loaded. Reloading…`)
    document.body.style.pointerEvents = 'none'
    document.body.style.opacity = '0.6'
    setTimeout(() => location.reload(), 600)
  } catch (e) { showToast('Seed failed: ' + e.message, true) }
}

/* ── Overlay close on backdrop click / Escape ─────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.overlay').forEach(o =>
    o.addEventListener('click', e => { if (e.target === o) o.classList.remove('open') })
  )
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape')
      document.querySelectorAll('.overlay.open').forEach(o => o.classList.remove('open'))
  })
})

/* ── Nav auto-highlight based on filename ─────────────────────── */
;(function () {
  const page = window.location.pathname.split('/').pop().replace('.html', '') || 'index'
  document.querySelectorAll('.nav-item[data-page]').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-page') === page)
  })
})()
