/**
 * app.js — NEXA AI Tariff · Live API Integration
 * Module A: HS Classification  |  Module B: FTA Matching  |  Module C: Landed Cost (pending)
 */

/* ─── State ────────────────────────────────────────────────────── */
let SHIPMENTS   = []   // raw from Supabase via backend
let selectedIdx = 0
let activeFilter = 'all'

/* ─── Helpers ──────────────────────────────────────────────────── */
function setHtml(id, html) {
  const el = document.getElementById(id)
  if (el) el.innerHTML = html
}
function setText(id, txt) {
  const el = document.getElementById(id)
  if (el) el.textContent = txt
}
function confColor(c) {
  if (c >= 95) return 'var(--teal)'
  if (c >= 85) return 'var(--amber)'
  return 'var(--error)'
}
function renderDots(conf) {
  if (!conf) return ''
  const filled = conf >= 95 ? 5 : conf >= 85 ? 4 : conf >= 75 ? 3 : 2
  const level  = conf >= 95 ? 'hi' : conf >= 85 ? 'mid' : 'lo'
  return Array.from({length:5}, (_,i) =>
    `<div class="cdot${i < filled ? ' '+level : ''}"></div>`
  ).join('')
}
function pipelineDot(done, label) {
  return done
    ? `<span style="font-size:10px;color:var(--teal)">✓ ${label}</span>`
    : `<span style="font-size:10px;color:#ccc">○ ${label}</span>`
}

/* ─── Boot ─────────────────────────────────────────────────────── */
async function init() {
  try {
    await Promise.all([loadSummary(), loadShipments()])
  } catch(e) {
    console.error('Init failed:', e)
  }
}

/* ─── KPI Summary ──────────────────────────────────────────────── */
async function loadSummary() {
  try {
    const s = await fetchSummary()
    setHtml('kpiTotal',   `${s.total_shipments}<span class="unit"> total</span>`)
    setHtml('kpiSaving',  `$${Math.round(s.total_fta_saving_usd || 0).toLocaleString()}`)
    setText('kpiFlagged', s.flagged  || 0)
    setText('kpiPending', s.pending  || 0)
  } catch(e) { console.warn('Summary failed:', e) }
}

/* ─── Load Shipments ───────────────────────────────────────────── */
async function loadShipments() {
  setHtml('tblBody', `<div style="padding:20px;color:var(--muted-soft);font-size:12px">Loading from Supabase…</div>`)
  try {
    SHIPMENTS = await fetchShipments()
    renderTable()
    updatePipelineCounts()
    if (SHIPMENTS.length > 0) renderDetail(0)
  } catch(e) {
    setHtml('tblBody', `
      <div style="padding:20px;color:var(--error);font-size:12px;line-height:1.8">
        ⚠ Cannot reach backend.<br>
        <span style="font-family:var(--mono);color:var(--muted-soft)">
          cd backend &amp;&amp; uvicorn main:app --reload
        </span>
      </div>`)
  }
}

/* ─── Pipeline Counts ──────────────────────────────────────────── */
function updatePipelineCounts() {
  const total  = SHIPMENTS.length
  const withA  = SHIPMENTS.filter(s => s.hs_classifications?.length > 0).length
  const withB  = SHIPMENTS.filter(s => s.fta_results?.length > 0).length
  setText('modACount', `${withA} / ${total} classified`)
  setText('modBCount', `${withB} / ${total} matched`)
}

/* ─── Table ────────────────────────────────────────────────────── */
function getFiltered() {
  if (activeFilter === 'flagged')  return SHIPMENTS.filter(s => s.status === 'flagged')
  if (activeFilter === 'approved') return SHIPMENTS.filter(s => s.status === 'approved')
  if (activeFilter === 'pending')  return SHIPMENTS.filter(s => s.status === 'pending')
  return SHIPMENTS
}

function renderTable() {
  const items = getFiltered()

  // Update filter tab labels with live counts
  const total = SHIPMENTS.length
  const flag  = SHIPMENTS.filter(s => s.status === 'flagged').length
  const appr  = SHIPMENTS.filter(s => s.status === 'approved').length
  const tabs  = document.querySelectorAll('.filter-bar .tab')
  if (tabs[0]) tabs[0].textContent = `All (${total})`
  if (tabs[1]) tabs[1].innerHTML   = `<i class="ti ti-alert-circle" style="font-size:11px"></i> Flagged (${flag})`
  if (tabs[2]) tabs[2].innerHTML   = `<i class="ti ti-check" style="font-size:11px"></i> Approved (${appr})`

  if (!items.length) {
    setHtml('tblBody', `<div style="padding:20px;color:var(--muted-soft);font-size:12px">No shipments found.</div>`)
    return
  }

  setHtml('tblBody', items.map(s => {
    const realIdx = SHIPMENTS.indexOf(s)
    const sel     = realIdx === selectedIdx
    const cls     = s.hs_classifications?.[0] || {}
    const fta     = s.fta_results?.[0]        || {}
    const hasA    = !!cls.final_hs_code
    const hasB    = !!fta.best_fta_name
    const hs      = cls.final_hs_code || '—'
    const conf    = cls.confidence_score || 0
    const ftaName = fta.best_fta_name   || '—'
    const saving  = fta.duty_saving_usd || 0

    return `
      <div class="tbl-row${sel ? ' sel' : ''}" onclick="selectItem(${realIdx})">
        <span class="row-num">${s.sap_shipment_id}</span>
        <span class="hs-code">${hs}</span>
        <span>
          <div class="prod-name">${s.product_description}</div>
          <div class="prod-origin" style="display:flex;gap:8px;margin-top:2px">
            ${pipelineDot(hasA,'A')}
            ${pipelineDot(hasB,'B')}
            ${pipelineDot(false,'C')}
          </div>
        </span>
        <span class="conf-cell">
          ${conf
            ? `<span style="font-size:11.5px;font-family:var(--mono);font-weight:500;color:${confColor(conf)};min-width:29px">${conf}%</span>
               <div class="conf-dots">${renderDots(conf)}</div>`
            : `<span style="color:var(--muted-soft);font-size:11px">Not run</span>`}
        </span>
        <span class="duty-cell" style="color:${saving > 0 ? 'var(--teal)' : 'var(--muted-soft)'}">
          ${saving > 0 ? '$'+saving.toLocaleString()+' saved' : '—'}
        </span>
        <span class="fta-badge ${ftaName==='MFN'?'fta-mfn':ftaName!=='—'?'fta-other':''}"
          style="${ftaName==='—'?'opacity:.35':''}">
          ${ftaName}
        </span>
        <span class="row-acts">
          <button class="ibt" title="Run Module A — HS Classification"
            onclick="event.stopPropagation();runSingleA('${s.sap_shipment_id}')">
            <i class="ti ti-brain"></i>
          </button>
          <button class="ibt" title="Run Module B — FTA Matching"
            onclick="event.stopPropagation();runSingleB('${s.sap_shipment_id}')">
            <i class="ti ti-world"></i>
          </button>
          <button class="ibt" title="View details" onclick="event.stopPropagation();selectItem(${realIdx})">
            <i class="ti ti-eye"></i>
          </button>
        </span>
      </div>`
  }).join(''))
}

/* ─── Select Row → Detail Panel ────────────────────────────────── */
function selectItem(idx) {
  selectedIdx = idx
  renderTable()
  renderDetail(idx)
}

function setFilter(filter, btn) {
  activeFilter = filter
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'))
  btn.classList.add('active')
  renderTable()
}

/* ─── Detail Panel ─────────────────────────────────────────────── */
function renderDetail(idx) {
  const s = SHIPMENTS[idx]
  if (!s) return

  const cls = s.hs_classifications?.[0] || null
  const fta = s.fta_results?.[0]        || null
  const cif = (s.shipment_value_usd||0) + (s.freight_cost_usd||0) + (s.insurance_cost_usd||0)

  /* ── Card 1: Shipment Info ── */
  setHtml('detTitle', `${s.sap_shipment_id}`)
  const statusColor = {approved:'var(--teal)', flagged:'var(--error)', pending:'var(--amber)'}[s.status] || 'var(--muted-soft)'
  const pill = document.getElementById('detStatusPill')
  if (pill) { pill.textContent = s.status; pill.style.color = statusColor; pill.style.background = 'transparent'; pill.style.border = `1px solid ${statusColor}` }

  setHtml('detProduct', s.product_description)
  setHtml('detHS',      cls?.final_hs_code
    ? `<span style="font-family:var(--mono)">${cls.final_hs_code}</span>`
    : `<span style="color:var(--muted-soft)">Run Module A first</span>`)
  setHtml('detOrigin',  `${s.origin_country} <span style="color:var(--muted-soft)">→</span> ${s.destination_country}`)
  setHtml('detValue',   `<span style="font-family:var(--mono)">USD ${cif.toLocaleString()}</span> CIF`)
  setHtml('detRVC',     s.supplier_rvc_pct ? `${s.supplier_rvc_pct}%` : '—')

  /* ── Card 2: Module A ── */
  const btnA = document.getElementById('btnRunA')
  if (btnA) btnA.setAttribute('data-id', s.sap_shipment_id)

  if (cls) {
    const aPassed = cls.module_a_status === 'auto_passed'
    const aColor  = aPassed ? 'var(--teal)' : 'var(--amber)'
    const aPill   = document.getElementById('modAStatusPill')
    if (aPill) { aPill.textContent = aPassed ? '✓ Auto Passed' : '⚠ Low Confidence'; aPill.style.color = aColor; aPill.style.background = 'transparent'; aPill.style.border = `1px solid ${aColor}` }

    setHtml('modABody', `
      <div class="d-row">
        <span class="d-lbl">e2open hint</span>
        <span class="d-val mono">${cls.e2open_hs_code || '—'}</span>
      </div>
      <div class="d-row">
        <span class="d-lbl">AI selected</span>
        <span class="d-val mono" style="color:var(--teal);font-weight:600">${cls.ai_hs_code}</span>
      </div>
      <div class="d-row">
        <span class="d-lbl">Confidence</span>
        <span class="d-val" style="color:${confColor(cls.confidence_score)}">
          ${cls.confidence_score}%
          <span style="color:var(--muted-soft)">
            — ${cls.confidence_score >= 85 ? 'auto approved' : 'analyst review needed'}
          </span>
        </span>
      </div>
      <div style="margin-top:10px;padding:10px;background:var(--bg-alt,#f9f9f8);border-radius:4px;font-size:11px;line-height:1.7;color:var(--muted-soft)">
        <strong style="color:var(--ink);display:block;margin-bottom:4px">AI Reasoning (llama3.2):</strong>
        ${cls.reasoning_text || '—'}
      </div>
      ${cls.rag_sources?.length ? `
        <div style="margin-top:8px;font-size:10.5px;color:var(--muted-soft)">
          <strong style="color:var(--ink)">pgvector RAG matches:</strong>
          ${cls.rag_sources.map(r => `
            <div style="margin-top:3px;display:flex;justify-content:space-between;gap:8px">
              <span class="mono">${r.hs_code}</span>
              <span style="flex:1;color:var(--muted-soft)">${r.description || ''}</span>
              <span style="color:var(--teal)">${Math.round((r.similarity||0)*100)}%</span>
            </div>`).join('')}
        </div>` : ''}
    `)
  } else {
    const aPill = document.getElementById('modAStatusPill')
    if (aPill) { aPill.textContent = 'Not run'; aPill.style.color = 'var(--muted-soft)'; aPill.style.background = 'transparent'; aPill.style.border = '1px solid var(--border)' }
    setHtml('modABody', `
      <div style="color:var(--muted-soft);font-size:11.5px;line-height:1.8">
        Module A has not run for this shipment.<br>
        When you click <strong>Run Module A</strong>, it will:<br>
        <span style="font-size:11px">
          1. Read the product description from Supabase<br>
          2. Convert it to a vector using <strong>nomic-embed-text</strong> (Ollama)<br>
          3. Search <code>hs_reference</code> table with <strong>pgvector</strong> for top 3 matches<br>
          4. Ask <strong>llama3.2</strong> to pick the correct HS code<br>
          5. Save result to <code>hs_classifications</code> table
        </span>
      </div>
    `)
  }

  /* ── Card 3: Module B ── */
  const btnB = document.getElementById('btnRunB')
  if (btnB) btnB.setAttribute('data-id', s.sap_shipment_id)

  if (fta) {
    const bStatus = fta.module_b_status || ''
    const bColor  = bStatus === 'fta_applied' ? 'var(--teal)' :
                    bStatus === 'mfn_applied'  ? 'var(--amber)' : 'var(--error)'
    const bLabel  = {fta_applied:'✓ FTA Applied', mfn_applied:'⚠ MFN Fallback', no_fta_available:'✗ No FTA'}[bStatus] || bStatus
    const bPill   = document.getElementById('modBStatusPill')
    if (bPill) { bPill.textContent = bLabel; bPill.style.color = bColor; bPill.style.background = 'transparent'; bPill.style.border = `1px solid ${bColor}` }

    const allFTAs = Array.isArray(fta.applicable_ftas) ? fta.applicable_ftas : []
    setHtml('modBBody', `
      <div class="d-row">
        <span class="d-lbl">Best FTA</span>
        <span class="d-val" style="color:${bColor};font-weight:600">${fta.best_fta_name}</span>
      </div>
      <div class="d-row">
        <span class="d-lbl">FTA Rate</span>
        <span class="d-val mono" style="color:var(--teal)">${fta.best_fta_rate_pct}%</span>
      </div>
      <div class="d-row">
        <span class="d-lbl">MFN Rate</span>
        <span class="d-val mono">${fta.mfn_rate_pct}% <span style="color:var(--muted-soft)">(without FTA)</span></span>
      </div>
      <div class="d-row">
        <span class="d-lbl">Duty Saved</span>
        <span class="d-val mono" style="color:var(--teal);font-weight:600">$${(fta.duty_saving_usd||0).toLocaleString()}</span>
      </div>
      <div class="d-row">
        <span class="d-lbl">Rule of Origin</span>
        <span class="d-val">${fta.roo_type || '—'} · RVC ${fta.rvc_supplier_declared||0}% ≥ ${fta.rvc_threshold||0}% threshold</span>
      </div>
      ${allFTAs.length ? `
        <div style="margin-top:10px;font-size:10.5px;color:var(--muted-soft)">
          <strong style="color:var(--ink);display:block;margin-bottom:4px">All FTAs checked:</strong>
          ${allFTAs.map(f => `
            <div style="margin-top:3px;display:flex;justify-content:space-between;gap:8px;padding:2px 0;border-bottom:1px solid var(--border)">
              <span style="font-weight:500;color:var(--ink)">${f.fta_name}</span>
              <span style="flex:1;color:var(--muted-soft);font-size:10px">${f.reason || ''}</span>
              <span style="color:${f.qualifies ? 'var(--teal)' : 'var(--muted-soft)'}">
                ${f.qualifies ? `✓ ${f.rate}%` : '✗ fail'}
              </span>
            </div>`).join('')}
        </div>` : ''}
    `)
  } else {
    const bPill = document.getElementById('modBStatusPill')
    if (bPill) { bPill.textContent = 'Not run'; bPill.style.color = 'var(--muted-soft)'; bPill.style.background = 'transparent'; bPill.style.border = '1px solid var(--border)' }
    setHtml('modBBody', `
      <div style="color:var(--muted-soft);font-size:11.5px;line-height:1.8">
        Module B has not run for this shipment.<br>
        When you click <strong>Run Module B</strong>, it will:<br>
        <span style="font-size:11px">
          1. Read the HS code from Module A output<br>
          2. Find all FTAs that include the origin country<br>
          3. Check Rules of Origin (RVC %, tariff shift) for each FTA<br>
          4. Pick the FTA with the lowest duty rate<br>
          5. Calculate duty saving vs MFN rate<br>
          6. Save result to <code>fta_results</code> table
        </span>
      </div>
    `)
  }

  /* ── Card 4: Module C inputs (for teammate) ── */
  setHtml('mcHSCode',  cls?.final_hs_code
    ? `<span style="font-family:var(--mono);color:var(--teal)">${cls.final_hs_code}</span>`
    : `<span style="color:var(--muted-soft)">⬆ run Module A first</span>`)
  setHtml('mcFTARate', fta
    ? `<span style="font-family:var(--mono);color:var(--teal)">${fta.best_fta_rate_pct}%</span> (${fta.best_fta_name})`
    : `<span style="color:var(--muted-soft)">⬆ run Module B first</span>`)
  setHtml('mcCIF',     `<span style="font-family:var(--mono)">USD ${cif.toLocaleString()}</span>`)
  setHtml('mcDuty',    fta
    ? `<span style="font-family:var(--mono);color:var(--teal)">$${((fta.best_fta_rate_pct/100)*cif).toFixed(2)}</span>`
    : `<span style="color:var(--muted-soft)">? × CIF</span>`)
}

/* ─── Module A: Run ────────────────────────────────────────────── */
async function triggerModuleA() {
  const btn = document.getElementById('btnRunA')
  const id  = btn?.getAttribute('data-id')
  if (!id) return
  await runSingleA(id)
}

async function runSingleA(shipmentId) {
  showToast(`⏳ Module A running for ${shipmentId}… (llama3.2 may take ~30s)`)
  const btn = document.getElementById('btnRunA')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Running…' }
  try {
    const r = await runModuleA(shipmentId)
    if (r.status === 'ok') {
      const c = r.classification
      showToast(`✓ Module A — ${c?.final_hs_code || '?'} · ${c?.confidence_score || '?'}% confidence`)
    } else {
      showToast('Module A failed: ' + (r.detail || 'unknown'), true)
    }
    await loadShipments()
    const idx = SHIPMENTS.findIndex(s => s.sap_shipment_id === shipmentId)
    if (idx >= 0) { selectedIdx = idx; renderDetail(idx) }
  } catch(e) {
    showToast('Module A error: ' + e.message, true)
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-brain"></i> Run Module A' }
  }
}

/* ─── Module B: Run ────────────────────────────────────────────── */
async function triggerModuleB() {
  const btn = document.getElementById('btnRunB')
  const id  = btn?.getAttribute('data-id')
  if (!id) return
  await runSingleB(id)
}

async function runSingleB(shipmentId) {
  showToast(`⏳ Module B running for ${shipmentId}…`)
  const btn = document.getElementById('btnRunB')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Running…' }
  try {
    const r = await runModuleB(shipmentId)
    if (r.status === 'ok') {
      const d = r.data
      showToast(`✓ Module B — ${d?.best_fta} @ ${d?.fta_rate_pct}% · saved $${d?.duty_saving_usd}`)
    } else {
      showToast('Module B failed: ' + (r.detail || 'unknown'), true)
    }
    await loadShipments()
    const idx = SHIPMENTS.findIndex(s => s.sap_shipment_id === shipmentId)
    if (idx >= 0) { selectedIdx = idx; renderDetail(idx) }
  } catch(e) {
    showToast('Module B error: ' + e.message, true)
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-world"></i> Run Module B' }
  }
}

/* ─── Bulk: Run both modules for all pending ───────────────────── */
async function doBulk() {
  const pending = SHIPMENTS.filter(s => s.status === 'pending')
  if (!pending.length) { showToast('No pending shipments'); return }
  showToast(`Running Module A + B for ${pending.length} pending shipments…`)
  for (const s of pending) {
    const hasA = s.hs_classifications?.length > 0
    if (!hasA) await runSingleA(s.sap_shipment_id).catch(() => {})
    await runSingleB(s.sap_shipment_id).catch(() => {})
  }
  showToast('✓ All pending shipments processed')
}

/* ─── Seed ─────────────────────────────────────────────────────── */
async function runSeedAndRefresh() {
  showToast('Seeding database…')
  try {
    const r = await runSeed()
    showToast(`✓ Seed complete — ${r.result?.shipments || 0} shipments`)
    await loadShipments()
    await loadSummary()
  } catch(e) { showToast('Seed failed: ' + e.message, true) }
}

/* ─── Approve / Submit ─────────────────────────────────────────── */
function approveItem() { openModal('approvedModal') }
function submitBatch()  { closeModal('batchModal'); showToast('✓ Batch submitted to SAP S/4HANA') }

/* ─── Toast ────────────────────────────────────────────────────── */
function showToast(msg, isError = false) {
  const t = document.getElementById('toast')
  if (!t) return
  t.textContent = msg
  t.style.background = isError ? '#ef4444' : '#0d9488'
  t.classList.add('show')
  setTimeout(() => t.classList.remove('show'), 4500)
}

/* ─── Modals ───────────────────────────────────────────────────── */
function openModal(id)  { document.getElementById(id)?.classList.add('open') }
function closeModal(id) { document.getElementById(id)?.classList.remove('open') }
document.querySelectorAll('.overlay').forEach(o =>
  o.addEventListener('click', e => { if (e.target === o) o.classList.remove('open') })
)
document.addEventListener('keydown', e => {
  if (e.key === 'Escape')
    document.querySelectorAll('.overlay.open').forEach(o => o.classList.remove('open'))
})

/* ─── Go ───────────────────────────────────────────────────────── */
init()
