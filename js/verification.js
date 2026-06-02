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

/* ── Detail panel ────────────────────────────────────────────────────────────────────── */
function renderDetailPanel(s) {
  const cls = s.hs_classifications?.[0] || null
  const fta = s.fta_results?.[0]        || null
  const lc  = s.landed_costs?.[0]       || null
  const cif = (s.shipment_value_usd || 0) + (s.freight_cost_usd || 0) + (s.insurance_cost_usd || 0)

  // Header
  const statusCol = statusColor(s.status)
  setText('detailTitle', `${s.sap_shipment_id} — ${s.product_description}`)
  setText('detailMeta',  `${s.origin_country} → Malaysia · USD ${cif.toLocaleString()} CIF`)
  const pill = $('detailStatusPill')
  if (pill) {
    pill.textContent = s.status.toUpperCase()
    pill.style.cssText = `background:${statusCol}18;color:${statusCol};border:1px solid ${statusCol}40`
  }
  $('detailHeader').style.display = ''
  $('actionBar').style.display    = ''

  // Disable actions if already reviewed
  const reviewed = s.status === 'approved' || s.status === 'flagged'
  ;['btnApprove','btnEdit','btnEscalate'].forEach(id => {
    const b = $(id); if (b) b.disabled = reviewed
  })

  // Body cards
  setHtml('detailBody',
    renderModuleACard(cls) +
    renderModuleBCard(fta, cif) +
    renderModuleCCard(lc) +
    '<div id="inlineFormContainer"></div>'
  )
}

/* Module A card */
function renderModuleACard(cls) {
  if (!cls) return `
  <div class="det-card">
    <div class="det-head"><i class="ti ti-brain" style="color:var(--primary);font-size:15px"></i>
      <span class="det-title">Module A — HS Classification</span></div>
    <div class="det-body" style="color:var(--muted-soft);font-size:12px;text-align:center;padding:20px 0">
      Module A has not run yet. Go to <a href="shipments.html" style="color:var(--primary)">All Shipments</a> to run it.
    </div>
  </div>`

  const conf       = cls.confidence_score || 0
  const barColor   = confColor(conf)
  const agrees     = cls.e2open_hs_code === cls.ai_hs_code
  const overridden = !!cls.analyst_override_hs
  const statusText = overridden     ? 'Analyst Override'
                   : conf >= 85    ? '✓ Auto Passed'    : '⚠ Review Required'
  const statusCol  = overridden     ? 'var(--primary)'
                   : conf >= 85    ? 'var(--teal)'      : 'var(--amber)'

  return `
  <div class="det-card">
    <div class="det-head">
      <i class="ti ti-brain" style="color:var(--primary);font-size:15px"></i>
      <span class="det-title">Module A — HS Classification</span>
      <span style="font-size:11px;font-weight:600;color:${statusCol}">${statusText}</span>
    </div>
    <div class="det-body">
      <div style="display:grid;grid-template-columns:1fr auto 1fr auto;gap:12px;align-items:center;margin-bottom:12px">
        <div>
          <div style="font-size:10px;color:var(--muted-soft);text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">e2open</div>
          <div style="font-family:var(--mono);font-size:15px;font-weight:600;color:var(--amber)">${cls.e2open_hs_code || '—'}</div>
        </div>
        <div style="color:var(--muted-soft);font-size:14px">→</div>
        <div>
          <div style="font-size:10px;color:var(--muted-soft);text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">
            ${overridden ? 'Override' : 'AI'}
          </div>
          <div style="font-family:var(--mono);font-size:15px;font-weight:600;color:${agrees && !overridden ? 'var(--teal)' : 'var(--primary)'}">
            ${cls.final_hs_code || '—'}
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:10px;color:var(--muted-soft);margin-bottom:3px">Confidence</div>
          <div style="font-size:18px;font-weight:600;color:${barColor};font-family:var(--mono)">${conf}%</div>
        </div>
      </div>
      <div style="height:6px;background:var(--hairline);border-radius:var(--r-pill);overflow:hidden;margin-bottom:10px">
        <div style="height:100%;width:${Math.min(conf,100)}%;background:${barColor};border-radius:var(--r-pill)"></div>
      </div>
      ${!agrees && !overridden ? `<div style="padding:6px 10px;background:rgba(232,165,90,.08);border-left:3px solid var(--amber);border-radius:0 var(--r-md) var(--r-md) 0;font-size:11.5px;color:var(--body);margin-bottom:8px">
        <strong style="color:var(--amber)">⚠ Disagrees with e2open.</strong> AI overrides to <span style="font-family:var(--mono)">${cls.ai_hs_code}</span>.
      </div>` : ''}
      ${cls.reasoning_text ? `
      <details style="margin-top:8px">
        <summary style="font-size:11.5px;color:var(--muted);cursor:pointer;font-weight:500">AI Reasoning — click to expand</summary>
        <div style="margin-top:8px;padding:8px;background:var(--surface-soft);border-radius:var(--r-md);font-size:11.5px;color:var(--muted-soft);line-height:1.7">
          ${cls.reasoning_text}
        </div>
      </details>` : ''}
      ${overridden ? `<div style="margin-top:8px;font-size:11px;color:var(--teal)">✓ Analyst override on record: <span style="font-family:var(--mono)">${cls.analyst_override_hs}</span></div>` : ''}
    </div>
  </div>`
}

/* Module B card */
function renderModuleBCard(fta, cif) {
  if (!fta) return `
  <div class="det-card">
    <div class="det-head"><i class="ti ti-world" style="color:var(--teal);font-size:15px"></i>
      <span class="det-title">Module B — FTA Match</span></div>
    <div class="det-body" style="color:var(--muted-soft);font-size:12px;text-align:center;padding:16px 0">
      Module B not run yet.
    </div>
  </div>`

  const ftaRate = Math.min(Math.max(fta.best_fta_rate_pct ?? 0, 0), 100)
  const mfnRate = Math.min(Math.max(fta.mfn_rate_pct     ?? 0, 0), 100)
  const saving  = fta.duty_saving_usd || 0
  const ftaName = fta.best_fta_name   || 'MFN'
  const isFTA   = fta.module_b_status === 'fta_applied'
  const badge   = isFTA
    ? `<span style="font-size:11px;font-weight:600;color:var(--teal)">✓ ${ftaName} Applied</span>`
    : `<span style="font-size:11px;font-weight:600;color:var(--amber)">⚠ MFN Fallback</span>`

  return `
  <div class="det-card">
    <div class="det-head">
      <i class="ti ti-world" style="color:var(--teal);font-size:15px"></i>
      <span class="det-title">Module B — FTA Match</span>
      ${badge}
    </div>
    <div class="det-body">
      <div style="display:flex;gap:var(--sp-lg);margin-bottom:4px">
        <div>
          <div style="font-size:10px;color:var(--muted-soft);margin-bottom:2px">Best FTA</div>
          <div style="font-size:14px;font-weight:600;color:${isFTA ? 'var(--teal)' : 'var(--muted)'}">${ftaRate}% (${ftaName})</div>
        </div>
        <div>
          <div style="font-size:10px;color:var(--muted-soft);margin-bottom:2px">MFN Rate</div>
          <div style="font-size:14px;font-weight:600;color:var(--muted)">${mfnRate}%</div>
        </div>
        <div>
          <div style="font-size:10px;color:var(--muted-soft);margin-bottom:2px">Duty Saving</div>
          <div style="font-size:14px;font-weight:600;color:${saving > 0 ? 'var(--teal)' : 'var(--muted)'}">${saving > 0 ? money(saving) : '$0.00'}</div>
        </div>
      </div>
    </div>
  </div>`
}

/* Module C card */
function renderModuleCCard(lc) {
  if (!lc) return `
  <div class="det-card">
    <div class="det-head"><i class="ti ti-receipt" style="color:var(--amber);font-size:15px"></i>
      <span class="det-title">Module C — Landed Cost</span></div>
    <div class="det-body" style="color:var(--muted-soft);font-size:12px;text-align:center;padding:16px 0">
      Module C not run yet.
    </div>
  </div>`

  const breakdown    = lc.cost_breakdown || []
  const totalCifMyr  = breakdown.reduce((s, r) => s + (r.apportionment_metrics?.calculated_cif_myr      || 0), 0)
  const totalDutyMyr = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.customs_duty_charged   || 0), 0)
  const totalTaxMyr  = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.sales_tax_charged      || 0), 0)
  const fxEst        = totalCifMyr > 0 && lc.cif_value_usd > 0 ? totalCifMyr / lc.cif_value_usd : 4.67
  const procMyr      = Math.round((lc.other_fees_usd || 0) * fxEst * 100) / 100
  const isLmw        = breakdown[0]?.flags_applied?.is_lmw_facility ?? true
  const fmt          = n => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return `
  <div class="det-card">
    <div class="det-head">
      <i class="ti ti-receipt" style="color:var(--amber);font-size:15px"></i>
      <span class="det-title">Module C — Landed Cost</span>
      ${isLmw ? `<span style="font-size:10px;font-weight:600;color:var(--teal)">✓ LMW Exempt</span>` : ''}
    </div>
    <div class="det-body">
      <div class="cost-ln"><span class="lbl">Total CIF</span><span class="val" style="font-family:var(--mono)">MYR ${fmt(totalCifMyr)}</span></div>
      <div class="cost-ln"><span class="lbl">Customs Duty</span><span class="val" style="color:${totalDutyMyr === 0 ? 'var(--teal)' : 'var(--ink)'}">MYR ${fmt(totalDutyMyr)}</span></div>
      <div class="cost-ln"><span class="lbl">Sales Tax (10%)</span><span class="val" style="color:${totalTaxMyr === 0 ? 'var(--teal)' : 'var(--ink)'}">MYR ${fmt(totalTaxMyr)}</span></div>
      <div class="cost-ln"><span class="lbl">Processing Fee</span><span class="val" style="font-family:var(--mono)">MYR ${fmt(procMyr)}</span></div>
      <div class="cost-total"><span>Total Landed Cost</span><span class="val">USD ${fmt(lc.total_landed_cost_usd || 0)}</span></div>
      ${(lc.fta_saving_usd || 0) > 0 ? `<div style="margin-top:8px;font-size:11px;color:var(--teal);font-weight:600;text-align:center">↓ FTA saves ${money(lc.fta_saving_usd)} vs MFN</div>` : ''}
    </div>
  </div>`
}
