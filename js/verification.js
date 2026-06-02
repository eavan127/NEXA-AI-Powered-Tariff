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

    // Auto-run Module C if A and B are done but C hasn't run yet
    const hasA = r.data.hs_classifications?.length > 0
    const hasB = r.data.fta_results?.length > 0
    const hasC = r.data.landed_costs?.length > 0
    if (hasA && hasB && !hasC) {
      showToast(`⏳ Auto-running Module C for ${id}…`)
      try {
        await runModuleC(id)
        const refreshed = await apiFetch(`/api/shipments/${id}`)
        renderDetailPanel(refreshed.data)
        showToast(`✓ Module C complete for ${id}`)
      } catch (cErr) {
        showToast(`Module C auto-run failed: ${cErr.message}`, true)
      }
    }
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
  // Clear any open inline form from previous item
  const prevForm = $('inlineFormContainer')
  if (prevForm) prevForm.innerHTML = ''

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

  // Show locked state if already reviewed, otherwise enable actions
  const reviewed = s.status === 'approved' || s.status === 'flagged'
  if (reviewed) {
    const label = s.status === 'approved'
      ? '✓ Approved — no further action needed'
      : '↑ Escalated — awaiting senior analyst'
    setHtml('actionBar', `
      <div style="flex:1;text-align:center;font-size:12px;color:var(--muted-soft);padding:4px 0">
        <span style="font-weight:600;color:${statusColor(s.status)}">${label}</span>
        &nbsp;·&nbsp;
        <a href="audit.html" style="color:var(--primary);text-decoration:none">View audit trail →</a>
      </div>`)
    $('actionBar').style.display = ''
  } else {
    setHtml('actionBar', `
      <button class="btn btn-primary" id="btnApprove" onclick="doApprove()"
        style="flex:1;justify-content:center;background:var(--teal);border-color:var(--teal)">
        <i class="ti ti-check"></i> Approve
      </button>
      <button class="btn" id="btnEdit" onclick="toggleEditForm()"
        style="flex:1;justify-content:center;background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.3);color:#1d4ed8">
        <i class="ti ti-edit"></i> Edit HS Code
      </button>
      <button class="btn" id="btnEscalate" onclick="toggleEscalateForm()"
        style="flex:1;justify-content:center;background:rgba(232,165,90,.08);border-color:rgba(232,165,90,.3);color:#92400e">
        <i class="ti ti-arrow-up-right"></i> Escalate
      </button>`)
    $('actionBar').style.display = ''
  }

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

/* ── Approve ─────────────────────────────────────────────────── */
async function doApprove() {
  if (!currentId) return
  const btn = $('btnApprove')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Approving…' }
  try {
    await approveShipment(currentId)
    showToast(`✓ ${currentId} approved`)
    await refreshAndAdvance(currentId, 'approved')
  } catch (e) {
    showToast('Approve failed: ' + e.message, true)
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-check"></i> Approve' }
  }
}

/* ── Edit HS Code form ───────────────────────────────────────── */
function toggleEditForm() {
  const container = $('inlineFormContainer')
  if (!container) return
  if (container.innerHTML.includes('editForm')) {
    container.innerHTML = ''
    return
  }
  container.innerHTML = ''

  const currentHS = SHIPMENTS.find(s => s.sap_shipment_id === currentId)
    ?.hs_classifications?.[0]?.final_hs_code || ''

  container.innerHTML = `
  <div class="inline-form" id="editForm">
    <div style="font-size:12px;font-weight:600;color:var(--ink);margin-bottom:var(--sp-sm)">Override HS Code</div>
    <div style="font-size:11px;color:var(--muted-soft);margin-bottom:var(--sp-sm)">
      Current: <span style="font-family:var(--mono);color:var(--primary)">${currentHS}</span>
    </div>
    <div class="field">
      <label>New HS Code <span class="required">*</span></label>
      <input type="text" id="overrideHSInput" placeholder="e.g. 8542.31" autocomplete="off">
    </div>
    <div class="field">
      <label>Reason for override <span class="required">*</span></label>
      <textarea id="overrideReasonInput" rows="3" placeholder="e.g. Confirmed as IC per supplier datasheet Rev.C"></textarea>
    </div>
    <div class="form-actions">
      <button class="btn" onclick="$('inlineFormContainer').innerHTML=''">Cancel</button>
      <button class="btn btn-primary" onclick="submitEditForm()"><i class="ti ti-check"></i> Save Override</button>
    </div>
  </div>`

  $('overrideHSInput')?.focus()
}

async function submitEditForm() {
  const hsCode = ($('overrideHSInput')?.value || '').trim()
  const reason = ($('overrideReasonInput')?.value || '').trim()

  let valid = true
  if (!hsCode) { $('overrideHSInput')?.classList.add('field-error');    valid = false }
  else           $('overrideHSInput')?.classList.remove('field-error')
  if (!reason) { $('overrideReasonInput')?.classList.add('field-error'); valid = false }
  else           $('overrideReasonInput')?.classList.remove('field-error')
  if (!valid) return

  const btn = document.querySelector('#editForm .btn-primary')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Saving…' }
  try {
    await overrideHSCode(currentId, hsCode, reason)
    showToast(`✓ ${currentId} HS code overridden to ${hsCode}`)
    $('inlineFormContainer').innerHTML = ''
    await refreshAndAdvance(currentId, 'approved')
  } catch (e) {
    showToast('Override failed: ' + e.message, true)
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-check"></i> Save Override' }
  }
}

/* ── Escalate form ───────────────────────────────────────────── */
function toggleEscalateForm() {
  const container = $('inlineFormContainer')
  if (!container) return
  if (container.innerHTML.includes('escalateForm')) {
    container.innerHTML = ''
    return
  }
  container.innerHTML = ''

  container.innerHTML = `
  <div class="inline-form" id="escalateForm">
    <div style="font-size:12px;font-weight:600;color:var(--ink);margin-bottom:var(--sp-sm)">Escalate to Senior Analyst</div>
    <div class="field">
      <label>Assign to</label>
      <select id="escalateAssignee">
        <option value="James Tan">James Tan — Senior Trade Compliance Analyst</option>
        <option value="Priya Nair">Priya Nair — Compliance Manager</option>
      </select>
    </div>
    <div class="field">
      <label>Notes <span class="required">*</span></label>
      <textarea id="escalateNotes" rows="3" placeholder="Describe the issue requiring senior review…"></textarea>
    </div>
    <div class="form-actions">
      <button class="btn" onclick="$('inlineFormContainer').innerHTML=''">Cancel</button>
      <button class="btn" id="btnEscalateSubmit"
        style="background:rgba(232,165,90,.1);border-color:var(--amber);color:#92400e"
        onclick="submitEscalateForm()">
        <i class="ti ti-arrow-up-right"></i> Escalate
      </button>
    </div>
  </div>`

  $('escalateNotes')?.focus()
}

async function submitEscalateForm() {
  const assignee = $('escalateAssignee')?.value || 'Senior Analyst'
  const notes    = ($('escalateNotes')?.value || '').trim()

  if (!notes) { $('escalateNotes')?.classList.add('field-error'); return }
  $('escalateNotes')?.classList.remove('field-error')

  const btn = $('btnEscalateSubmit')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Escalating…' }
  try {
    await escalateShipment(currentId, assignee, notes)
    showToast(`✓ ${currentId} escalated to ${assignee}`)
    $('inlineFormContainer').innerHTML = ''
    await refreshAndAdvance(currentId, 'flagged')
  } catch (e) {
    showToast('Escalate failed: ' + e.message, true)
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-arrow-up-right"></i> Escalate' }
  }
}

/* ── Refresh + auto-advance ──────────────────────────────────── */
async function refreshAndAdvance(id, newStatus) {
  // Update local state immediately (optimistic update)
  const ship = SHIPMENTS.find(s => s.sap_shipment_id === id)
  if (ship) ship.status = newStatus

  updateQueueHeader()
  renderQueue()
  updateBulkApproveBtn()
  updateNavBadge()

  // Check if all items are reviewed
  const allReviewed = SHIPMENTS.every(s => s.status === 'approved' || s.status === 'flagged')
  if (allReviewed) {
    showCompletionState()
    return
  }

  // Advance to next pending item
  const currentIndex = SHIPMENTS.findIndex(s => s.sap_shipment_id === id)
  const remaining    = SHIPMENTS.filter(s => s.status === 'pending')
  if (remaining.length > 0) {
    // Prefer next item after current in list order
    const next = SHIPMENTS.slice(currentIndex + 1).find(s => s.status === 'pending')
              || remaining[0]
    await selectItem(next.sap_shipment_id)
  }
}

/* ── Completion state ────────────────────────────────────────── */
function showCompletionState() {
  currentId = null
  renderQueue()

  const approved  = SHIPMENTS.filter(s => s.status === 'approved').length
  const escalated = SHIPMENTS.filter(s => s.status === 'flagged').length
  const total     = SHIPMENTS.length

  $('detailHeader').style.display = 'none'
  $('actionBar').style.display    = 'none'

  setHtml('detailBody', `
    <div style="display:flex;align-items:center;justify-content:center;flex:1;min-height:300px">
      <div class="completion-card">
        <div class="completion-icon"><i class="ti ti-circle-check"></i></div>
        <div class="completion-title">All ${total} items reviewed</div>
        <div class="completion-sub">Every shipment has a recorded human decision.<br>Ready for SAP submission.</div>
        <div class="completion-stats">
          <div class="stat-box">
            <div class="stat-val" style="color:var(--teal)">${approved}</div>
            <div class="stat-lbl">Approved</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color:var(--amber)">${escalated}</div>
            <div class="stat-lbl">Escalated</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color:var(--ink)">${total}</div>
            <div class="stat-lbl">Total</div>
          </div>
        </div>
        <div style="display:flex;gap:var(--sp-sm);justify-content:center">
          <button class="btn btn-primary" onclick="showToast('SAP writeback queued — feature coming soon')">
            <i class="ti ti-send"></i> Submit to SAP
          </button>
          <button class="btn" onclick="location.assign('audit.html')">
            <i class="ti ti-download"></i> View Audit Trail
          </button>
        </div>
      </div>
    </div>`)
}
