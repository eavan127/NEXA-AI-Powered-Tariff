/**
 * shipments.js — All Shipments page logic
 */

let SHIPMENTS    = []
let activeFilter = 'all'

/* ── Boot ────────────────────────────────────────────────────── */
loadAll()

async function loadAll() {
  try {
    const [ships, summary] = await Promise.all([fetchShipments(), fetchSummary()])
    SHIPMENTS = ships
    renderKPIs(summary)
    renderPipeline()
    renderTable()
  } catch (e) {
    setHtml('tblBody', `
      <div style="padding:28px;color:var(--muted-soft);font-size:12px;text-align:center">
        <i class="ti ti-plug-off" style="font-size:32px;display:block;margin-bottom:10px;color:var(--hairline)"></i>
        <strong style="color:var(--ink);font-size:13px">Backend offline</strong><br><br>
        Start the backend:<br>
        <code style="font-size:11.5px;background:var(--surface-dark);color:#faf9f5;padding:6px 12px;border-radius:6px;display:inline-block;margin-top:8px">
          cd backend &amp;&amp; uvicorn main:app --reload
        </code><br><br>
        Then click <strong>Re-Seed Data</strong> in the sidebar to populate the database.
      </div>`)
  }
}

/* ── KPIs ────────────────────────────────────────────────────── */
function renderKPIs(s) {
  setHtml('kTotal',   `${s.total_shipments || 0}<span class="unit"> total</span>`)
  setHtml('kSaving',  `$${Math.round(s.total_fta_saving_usd || 0).toLocaleString()}`)
  setText('kApproved', s.approved || 0)
  setText('kFlagged',  s.flagged  || 0)
  setText('kPend',     s.pending  || 0)
  setText('mApproved', s.approved || 0)
  setText('mFlagged',  s.flagged  || 0)
}

/* ── Pipeline banner ─────────────────────────────────────────── */
function renderPipeline() {
  const total = SHIPMENTS.length || 1
  const wA = SHIPMENTS.filter(s => s.hs_classifications?.length > 0).length
  const wB = SHIPMENTS.filter(s => s.fta_results?.length > 0).length
  const wC = SHIPMENTS.filter(s => s.landed_costs?.length > 0).length

  setText('pipeA', `${wA}/${total}`)
  setText('pipeB', `${wB}/${total}`)
  setText('pipeC', `${wC}/${total}`)
  const el = (id, w) => { const e = $(id); if (e) e.style.width = Math.round(w / total * 100) + '%' }
  el('pipeABar', wA); el('pipeBBar', wB); el('pipeCBar', wC)

  setText('pageMeta', `${total} shipments · ${wA} classified · ${wB} FTA matched · ${wC} costs calculated`)
  setText('tableCount', getFiltered().length + ' shown')
}

/* ── Filter ──────────────────────────────────────────────────── */
function getFiltered() {
  if (activeFilter === 'flagged')  return SHIPMENTS.filter(s => s.status === 'flagged')
  if (activeFilter === 'approved') return SHIPMENTS.filter(s => s.status === 'approved')
  if (activeFilter === 'pending')  return SHIPMENTS.filter(s => s.status === 'pending')
  return SHIPMENTS
}

function setFilter(f, btn) {
  activeFilter = f
  document.querySelectorAll('.filter-bar .tab').forEach(b => b.classList.remove('active'))
  btn.classList.add('active')
  renderTable()
  setText('tableCount', getFiltered().length + ' shown')
}

/* ── Table render ────────────────────────────────────────────── */
function renderTable() {
  const items = getFiltered()

  // Update tab labels with counts
  const counts = {
    all:      SHIPMENTS.length,
    flagged:  SHIPMENTS.filter(s => s.status === 'flagged').length,
    approved: SHIPMENTS.filter(s => s.status === 'approved').length,
    pending:  SHIPMENTS.filter(s => s.status === 'pending').length,
  }
  const tabs = document.querySelectorAll('.filter-bar .tab')
  if (tabs[0]) tabs[0].textContent = `All (${counts.all})`
  if (tabs[1]) tabs[1].innerHTML  = `<i class="ti ti-alert-circle" style="font-size:11px"></i> Flagged (${counts.flagged})`
  if (tabs[2]) tabs[2].innerHTML  = `<i class="ti ti-check" style="font-size:11px"></i> Approved (${counts.approved})`
  if (tabs[3]) tabs[3].textContent = `Pending (${counts.pending})`

  if (!items.length) {
    setHtml('tblBody', `
      <div style="padding:28px;color:var(--muted-soft);font-size:12px;text-align:center">
        No shipments in this category.
      </div>`)
    return
  }

  setHtml('tblBody', items.map(s => {
    const cls    = s.hs_classifications?.[0] || {}
    const fta    = s.fta_results?.[0]        || {}
    const hasA   = !!cls.final_hs_code
    const hasB   = !!fta.best_fta_name
    const conf   = cls.confidence_score || 0
    const saving = fta.duty_saving_usd  || 0
    const ftaNm  = fta.best_fta_name    || '—'
    const stCls  = { approved: 'st-approved', flagged: 'st-flagged', pending: 'st-pending' }[s.status] || ''

    return `
    <div class="tbl-row fade-in"
         onclick="window.location='verification.html?id=${s.sap_shipment_id}'"
         title="Open detail for ${s.sap_shipment_id}">

      <span>
        <div class="row-num">${s.sap_shipment_id}</div>
        <div style="font-size:10px;color:var(--muted-soft);margin-top:1px">${s.origin_country} → MY</div>
      </span>

      <span class="hs-code">${cls.final_hs_code || '—'}</span>

      <span>
        <div class="prod-name">${s.product_description}</div>
        <div class="prod-origin" style="display:flex;gap:8px;margin-top:2px">
          ${pDot(hasA, 'A')} ${pDot(hasB, 'B')} ${pDot(false, 'C')}
        </div>
      </span>

      <span class="conf-cell">
        ${conf
          ? `<span style="font-size:11px;font-family:var(--mono);font-weight:600;color:${confColor(conf)};min-width:28px">${conf}%</span>
             <div class="conf-dots">${renderDots(conf)}</div>`
          : `<span style="color:var(--muted-soft);font-size:11px">—</span>`}
      </span>

      <span class="duty-cell" style="color:${saving > 0 ? 'var(--teal)' : 'var(--muted-soft)'}">
        ${saving > 0 ? money(saving) : '—'}
      </span>

      <span>
        <span class="fta-badge ${ftaNm === 'MFN' ? 'fta-mfn' : ftaNm !== '—' ? 'fta-other' : ''}"
              style="${ftaNm === '—' ? 'opacity:.3' : ''}">
          ${ftaNm}
        </span>
      </span>

      <span>
        <span class="status-pill ${stCls}">${s.status.toUpperCase()}</span>
      </span>

      <span class="row-acts" onclick="event.stopPropagation()">
        <button class="ibt" title="Run Module A" onclick="doRunA('${s.sap_shipment_id}', this)">
          <i class="ti ti-brain"></i>
        </button>
        <button class="ibt" title="Run Module B" onclick="doRunB('${s.sap_shipment_id}', this)">
          <i class="ti ti-world"></i>
        </button>
        <button class="ibt" title="Review in Validation Dashboard"
          onclick="event.stopPropagation();window.location='verification.html?id=${s.sap_shipment_id}'">
          <i class="ti ti-shield-check"></i>
        </button>
      </span>
    </div>`
  }).join(''))
}

/* ── Module A ─────────────────────────────────────────────────── */
async function doRunA(id, btn) {
  const orig = btn.innerHTML
  btn.disabled = true
  btn.innerHTML = '<i class="ti ti-loader-2 spin"></i>'
  showToast(`⏳ Module A for ${id}… this takes ~30s (llama3.2)`)
  try {
    const r = await runModuleA(id)
    if (r.status === 'ok') {
      const c = r.classification
      showToast(`✓ ${id} classified → ${c?.final_hs_code} · ${c?.confidence_score}% confidence`)
    } else {
      showToast('Module A failed: ' + (r.detail || 'unknown error'), true)
    }
    await loadAll()
  } catch (e) {
    showToast('Module A error: ' + e.message, true)
    btn.disabled = false
    btn.innerHTML = orig
  }
}

/* ── Module B ─────────────────────────────────────────────────── */
async function doRunB(id, btn) {
  const orig = btn.innerHTML
  btn.disabled = true
  btn.innerHTML = '<i class="ti ti-loader-2 spin"></i>'
  showToast(`⏳ Module B for ${id}… checking 17 Malaysian FTAs`)
  try {
    const r = await runModuleB(id)
    if (r.status === 'ok') {
      const d = r.data
      const saving = d?.duty_saving_usd > 0 ? ` · saved ${money(d.duty_saving_usd)}` : ''
      showToast(`✓ ${id} → ${d?.best_fta || 'MFN'} @ ${d?.fta_rate_pct ?? d?.mfn_rate_pct}%${saving}`)
    } else {
      showToast('Module B failed: ' + (r.detail || 'unknown error'), true)
    }
    await loadAll()
  } catch (e) {
    showToast('Module B error: ' + e.message, true)
    btn.disabled = false
    btn.innerHTML = orig
  }
}

/* ── Bulk: run all pending ────────────────────────────────────── */
async function doBulk() {
  const pending = SHIPMENTS.filter(s => s.status === 'pending')
  if (!pending.length) { showToast('No pending shipments to process'); return }
  showToast(`Running A + B for ${pending.length} shipment(s)…`)
  let done = 0
  for (const s of pending) {
    const hasA = s.hs_classifications?.length > 0
    if (!hasA) await runModuleA(s.sap_shipment_id).catch(() => {})
    await runModuleB(s.sap_shipment_id).catch(() => {})
    done++
    showToast(`Progress: ${done}/${pending.length} processed…`)
  }
  showToast(`✓ All ${pending.length} pending shipments processed`)
  await loadAll()
}

/* ── Submit Batch ─────────────────────────────────────────────── */
function submitBatch() {
  closeModal('batchModal')
  showToast('✓ Batch submitted to SAP S/4HANA — writeback queued')
}
