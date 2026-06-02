/**
 * audit.js — Audit Trail page logic
 */

let ALL_ENTRIES = []
let activeShip  = 'all'

/* ── Boot ────────────────────────────────────────────────────── */
loadPage()

async function loadPage() {
  try {
    const [auditRes, ships] = await Promise.all([
      fetchAuditTrail().catch(() => ({ data: [] })),
      fetchShipments().catch(() => [])
    ])

    ALL_ENTRIES = auditRes.data || []

    // Cross-reference shipment_id → sap_shipment_id
    const idMap = {}
    for (const s of ships) { idMap[s.id] = s.sap_shipment_id }
    ALL_ENTRIES = ALL_ENTRIES.map(e => ({
      ...e,
      sap_id: idMap[e.shipment_id] || e.shipment_id?.slice(0, 8) || '—'
    }))

    // Populate filter dropdown
    const uniqueShips = [...new Set(ALL_ENTRIES.map(e => e.sap_id))]
      .filter(id => id && id !== '—')
      .sort()

    const sel = $('shipFilter')
    if (sel) {
      uniqueShips.forEach(id => {
        const opt = document.createElement('option')
        opt.value = id; opt.textContent = id
        sel.appendChild(opt)
      })
    }

    // Stats
    setText('auditTotal', ALL_ENTRIES.length)
    setText('auditShips', uniqueShips.length)
    setText('auditPageMeta',
      `${ALL_ENTRIES.length} events across ${uniqueShips.length} shipments · last updated ${new Date().toLocaleTimeString()}`)

    renderTimeline()
  } catch (e) {
    showToast('Failed to load audit trail: ' + e.message, true)
    setHtml('timelineBody', `
      <div style="padding:20px;color:var(--error);font-size:12px;text-align:center">
        <i class="ti ti-plug-off" style="font-size:24px;display:block;margin-bottom:8px"></i>
        Backend offline — run uvicorn in /backend
      </div>`)
  }
}

/* ── Filter ──────────────────────────────────────────────────── */
function applyFilter() {
  const sel = $('shipFilter')
  activeShip = sel?.value || 'all'
  renderTimeline()
}

function getFiltered() {
  if (activeShip === 'all') return ALL_ENTRIES
  return ALL_ENTRIES.filter(e => e.sap_id === activeShip)
}

/* ── Timeline render ─────────────────────────────────────────── */
function renderTimeline() {
  const items = getFiltered()
  setText('auditMeta',     `${items.length} event${items.length !== 1 ? 's' : ''}`)
  setText('filteredCount', `${items.length} shown`)

  if (!items.length) {
    setHtml('timelineBody', `
      <div class="empty-trail">
        <i class="ti ti-lock-off"></i>
        <strong>No audit events yet</strong><br>
        Approve or flag a shipment from the <a href="shipments.html"
          style="color:var(--primary)">All Shipments</a> page to create the first entry.
        <div class="empty-note">
          <strong style="color:var(--ink)">Events that will appear here:</strong>
          <ul style="margin-top:6px;padding-left:16px">
            <li>Shipment approved by analyst</li>
            <li>Shipment flagged for review</li>
            <li>HS code overridden manually</li>
            <li>Module A / B / C executions (future)</li>
          </ul>
        </div>
      </div>`)
    return
  }

  // Group by date
  const groups = {}
  for (const e of items) {
    const dt  = e.created_at ? new Date(e.created_at) : new Date()
    const key = dt.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
    if (!groups[key]) groups[key] = []
    groups[key].push(e)
  }

  const html = Object.entries(groups).map(([date, events]) => `
    <div class="timeline-group">
      <div class="timeline-date">${date}</div>
      ${events.map(e => renderEntry(e)).join('')}
    </div>`
  ).join('')

  setHtml('timelineBody', html)
}

function renderEntry(e) {
  const action = (e.analyst_note || e.event_type || 'System event').toLowerCase()
  const isApprove = action.includes('approved')
  const isFlag    = action.includes('flagged')
  const dotClass  = isApprove ? '' : isFlag ? 'flag' : 'info'
  const icon      = isApprove ? 'ti-check-circle' : isFlag ? 'ti-flag' : 'ti-bolt'
  const iconColor = isApprove ? 'var(--teal)' : isFlag ? 'var(--error)' : 'var(--primary)'
  const time      = e.created_at ? new Date(e.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '—'

  return `
  <div class="timeline-item fade-in">
    <div class="tl-dot ${dotClass}"></div>
    <span class="tl-time">${time}</span>
    <span class="tl-ship" onclick="location='index.html?id=${e.sap_id}'" style="cursor:pointer;text-decoration:underline;text-underline-offset:2px" title="Open shipment detail">
      ${e.sap_id}
    </span>
    <span class="tl-msg">
      <i class="ti ${icon}" style="font-size:13px;color:${iconColor};margin-right:5px"></i>
      ${e.analyst_note || e.event_type || 'System event'}
    </span>
  </div>`
}

/* ── Export CSV ──────────────────────────────────────────────── */
function exportAuditCSV() {
  const items = getFiltered()
  if (!items.length) { showToast('No events to export', true); return }

  const headers = ['Shipment ID', 'Action', 'Timestamp']
  const rows    = items.map(e => [
    e.sap_id,
    `"${(e.analyst_note || e.event_type || '').replace(/"/g, '""')}"`,
    e.created_at || ''
  ].join(','))

  const csv  = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `nexa-audit-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  showToast('✓ Audit trail exported')
}
