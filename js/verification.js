/**
 * verification.js — Human Validation Dashboard
 * Analyst must take an action on every shipment before SAP submission.
 */

/* ── State ────────────────────────────────────────────────────── */
let SHIPMENTS    = []
let currentId    = null
let activeFilter = 'all'

/* ── Boot ────────────────────────────────────────────────────── */
async function init() {
  setHtml('queueList', `
    <div style="padding:24px;text-align:center;color:var(--muted-soft);font-size:12px">
      <i class="ti ti-loader-2 spin" style="font-size:20px;display:block;margin-bottom:8px"></i>
      Loading queue…
    </div>`)
  try {
    SHIPMENTS = await fetchShipments()
    updateQueueHeader()
    renderQueue()
    updateBulkApproveBtn()
    updateNavBadge()

    // Deep-link: verification.html?id=SHIP001
    const preId = new URLSearchParams(window.location.search).get('id')
    if (preId && SHIPMENTS.find(s => s.sap_shipment_id === preId)) {
      selectItem(preId)
    } else {
      // Auto-select first non-approved item
      const first = SHIPMENTS.find(s => s.status !== 'approved') || SHIPMENTS[0]
      if (first) selectItem(first.sap_shipment_id)
    }
  } catch (e) {
    showToast('Failed to load queue: ' + e.message, true)
    setHtml('queueList', `
      <div style="padding:24px;color:var(--error);font-size:12px;text-align:center">
        <i class="ti ti-plug-off" style="font-size:24px;display:block;margin-bottom:8px"></i>
        Backend offline — run uvicorn in /backend
      </div>`)
  }
}

/* ── Queue header ────────────────────────────────────────────── */
function updateQueueHeader() {
  const total    = SHIPMENTS.length
  const reviewed = SHIPMENTS.filter(s => s.status === 'approved' || s.status === 'flagged').length
  const pct      = total > 0 ? Math.round(reviewed / total * 100) : 0

  setText('queueMeta', `${reviewed} of ${total} reviewed · ${total - reviewed} remaining`)
  const fill = $('queueProgressFill')
  if (fill) fill.style.width = pct + '%'
  setText('navPending', total - reviewed || 0)
}

/* ── Queue filter ────────────────────────────────────────────── */
function getFiltered() {
  if (activeFilter === 'flagged')  return SHIPMENTS.filter(s => s.status === 'flagged')
  if (activeFilter === 'pending')  return SHIPMENTS.filter(s => s.status === 'pending')
  if (activeFilter === 'approved') return SHIPMENTS.filter(s => s.status === 'approved')
  return SHIPMENTS
}

function setQueueFilter(f, btn) {
  activeFilter = f
  document.querySelectorAll('.queue-panel .tab').forEach(b => b.classList.remove('active'))
  btn.classList.add('active')
  renderQueue()
}

/* ── Queue render ────────────────────────────────────────────── */
function renderQueue() {
  const items = getFiltered()
  if (!items.length) {
    setHtml('queueList', `
      <div style="padding:24px;text-align:center;color:var(--muted-soft);font-size:12px">
        No shipments in this category.
      </div>`)
    return
  }
  setHtml('queueList', items.map(renderQueueItem).join(''))
}

function renderQueueItem(s) {
  const cls      = s.hs_classifications?.[0] || {}
  const conf     = cls.confidence_score || 0
  const selected = s.sap_shipment_id === currentId

  const borderCol = s.status === 'approved' ? 'var(--teal)'
                  : s.status === 'flagged'  ? 'var(--error)'
                  : conf >= 95              ? 'var(--teal)'
                  : conf >= 85              ? 'var(--amber)'
                  :                          'var(--error)'

  const statusLabel = { approved: '✓ Approved', flagged: 'Escalated', pending: 'Pending' }[s.status] || s.status
  const statusCol   = statusColor(s.status)

  return `
  <div class="queue-item${selected ? ' selected' : ''}"
       onclick="selectItem('${s.sap_shipment_id}')"
       style="border-left-color:${borderCol}">
    <div class="qi-top">
      <span class="qi-id">${s.sap_shipment_id}</span>
      <span style="padding:1px 6px;border-radius:var(--r-pill);font-size:9px;font-weight:600;background:${statusCol}20;color:${statusCol}">
        ${statusLabel}
      </span>
    </div>
    <div class="qi-name" title="${s.product_description}">${s.product_description}</div>
    <div class="qi-conf">
      <div class="conf-track">
        <div class="conf-fill" style="width:${conf}%;background:${confColor(conf)}"></div>
      </div>
      <span style="color:${confColor(conf)};font-size:10px;font-weight:600;font-family:var(--mono);min-width:28px;text-align:right">
        ${conf ? conf + '%' : '—'}
      </span>
    </div>
  </div>`
}

/* ── Select item ─────────────────────────────────────────────── */
async function selectItem(id) {
  currentId = id
  renderQueue()

  const detailHeader = $('detailHeader')
  const actionBar    = $('actionBar')
  if (detailHeader) detailHeader.style.display = 'none'
  if (actionBar)    actionBar.style.display    = 'none'
  setHtml('detailBody', `
    <div class="detail-empty">
      <div><i class="ti ti-loader-2 spin" style="font-size:32px;display:block;margin-bottom:10px;color:var(--hairline)"></i></div>
    </div>`)

  const el = document.querySelector('.queue-item.selected')
  if (el) el.scrollIntoView({ block: 'nearest' })

  try {
    const r = await apiFetch(`/api/shipments/${id}`)
    renderDetailPanel(r.data)
  } catch (e) {
    setHtml('detailBody', `
      <div class="detail-empty">
        <div style="color:var(--error)">
          <i class="ti ti-alert-circle" style="font-size:32px;display:block;margin-bottom:8px"></i>
          Failed to load: ${e.message}
        </div>
      </div>`)
  }
}

/* ── Nav pending badge ───────────────────────────────────────── */
function updateNavBadge() {
  const pending = SHIPMENTS.filter(s => s.status === 'pending' || s.status === 'flagged').length
  setText('navPending', pending || '0')
}

/* ── Bulk approve ────────────────────────────────────────────── */
function updateBulkApproveBtn() {
  const eligible = SHIPMENTS.filter(s => {
    const conf = s.hs_classifications?.[0]?.confidence_score || 0
    return s.status === 'pending' && conf >= 95
  })
  const btn = $('bulkApproveBtn')
  if (!btn) return
  btn.disabled = eligible.length === 0
  btn.innerHTML = `<i class="ti ti-checks"></i> Bulk Approve ≥95% (${eligible.length})`
}

async function doBulkApprove() {
  const eligible = SHIPMENTS.filter(s => {
    const conf = s.hs_classifications?.[0]?.confidence_score || 0
    return s.status === 'pending' && conf >= 95
  })
  if (!eligible.length) return

  const btn = $('bulkApproveBtn')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Approving…' }

  let done = 0
  for (const s of eligible) {
    try {
      await approveShipment(s.sap_shipment_id)
      s.status = 'approved'
      done++
    } catch (e) {
      console.warn('Bulk approve failed for', s.sap_shipment_id, e.message)
    }
  }

  showToast(`✓ Bulk approved ${done} shipments`)
  SHIPMENTS = await fetchShipments()
  updateQueueHeader()
  renderQueue()
  updateBulkApproveBtn()
  updateNavBadge()
  if (currentId) selectItem(currentId)
}

init()
