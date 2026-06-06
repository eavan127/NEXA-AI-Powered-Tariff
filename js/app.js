/**
 * app.js — NEXA AI Tariff Intelligence
 * Data Analyst / Boss view: search → drill-down per shipment
 */

/* ─── State ──────────────────────────────────────────────────────── */
let SHIPMENTS    = []
let currentShip  = null   // currently analysed shipment full object
let activeFilter = 'all'
let activeView   = 'lookup'

/* ─── Helpers ────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id)
function setHtml(id, h) { const e = $(id); if (e) e.innerHTML = h }
function setText(id, t) { const e = $(id); if (e) e.textContent = t }
function confColor(c)   {
  if (c >= 95) return 'var(--teal)'
  if (c >= 85) return 'var(--amber)'
  return 'var(--error)'
}
function renderDots(c) {
  const f = c >= 95 ? 5 : c >= 85 ? 4 : c >= 75 ? 3 : 2
  const lv = c >= 95 ? 'hi' : c >= 85 ? 'mid' : 'lo'
  return Array.from({length:5},(_,i)=>`<div class="cdot${i<f?' '+lv:''}"></div>`).join('')
}
function pDot(done, lbl) {
  return done
    ? `<span style="font-size:10px;color:var(--teal)">✓ ${lbl}</span>`
    : `<span style="font-size:10px;color:#ccc">○ ${lbl}</span>`
}
function money(n) { return '$' + (n||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}) }
function pct(n)   { return (n||0) + '%' }

/* ─── View switching ─────────────────────────────────────────────── */
function showView(v) {
  activeView = v
  $('viewLookup').style.display = v === 'lookup' ? '' : 'none'
  $('viewBatch').style.display  = v === 'batch'  ? '' : 'none'
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'))
  if (v === 'lookup') document.querySelectorAll('.nav-item')[0]?.classList.add('active')
  if (v === 'batch')  document.querySelectorAll('.nav-item')[1]?.classList.add('active')
  const crumb = $('topbarCrumb')
  if (crumb) crumb.innerHTML = v === 'lookup'
    ? `NEXA <i class="ti ti-chevron-right"></i> <strong>Shipment Lookup</strong>`
    : `NEXA <i class="ti ti-chevron-right"></i> <strong>All Shipments</strong>`
  if (v === 'batch') renderTable()
}

/* ─── Boot ───────────────────────────────────────────────────────── */
async function init() {
  try {
    await Promise.all([loadSummary(), loadShipments()])
  } catch(e) { console.error('Init failed:', e) }

  // Handle ?id=SHIP001 deep-link (from shipments.html / audit.html row click)
  const preId = new URLSearchParams(window.location.search).get('id')
  if (preId) {
    const inp = $('searchInput')
    if (inp) inp.value = preId.toUpperCase()
    showView('lookup')
    await analyzeShipment()
  }
}

/* ─── Summary KPIs ───────────────────────────────────────────────── */
async function loadSummary() {
  try {
    const s = await fetchSummary()
    setHtml('kpiTotal',   `${s.total_shipments}<span class="unit"> total</span>`)
    setHtml('kpiSaving',  `$${Math.round(s.total_fta_saving_usd||0).toLocaleString()}`)
    setText('kpiFlagged', s.flagged || 0)
    setText('kpiPending', s.pending || 0)
    // batch modal
    setText('modalApproved', s.approved || 0)
    setText('modalFlagged',  s.flagged  || 0)
  } catch(e) { console.warn('Summary failed:', e) }
}

/* ─── Load all shipments ─────────────────────────────────────────── */
async function loadShipments() {
  try {
    SHIPMENTS = await fetchShipments()
    updatePipelineCounts()
    if (activeView === 'batch') renderTable()
    const total = SHIPMENTS.length
    const withA = SHIPMENTS.filter(s => s.hs_classifications?.length > 0).length
    setHtml('kpiModA', `${withA}<span class="unit">/${total}</span>`)
  } catch(e) {
    setHtml('tblBody', `<div style="padding:20px;color:var(--error);font-size:12px">
      ⚠ Backend offline — run: <code>uvicorn main:app --reload</code> in /backend
    </div>`)
  }
}

function updatePipelineCounts() {
  const total = SHIPMENTS.length
  const wA = SHIPMENTS.filter(s => s.hs_classifications?.length > 0).length
  const wB = SHIPMENTS.filter(s => s.fta_results?.length > 0).length
  const wC = SHIPMENTS.filter(s => s.landed_costs?.length > 0).length
  setText('pipeACount', `${wA}/${total}`)
  setText('pipeBCount', `${wB}/${total}`)
  setText('pipeCCount', `${wC}/${total}`)
  setText('batchMeta',  `${total} shipments · ${wA} classified · ${wB} FTA matched · ${wC} landed`)
  setText('tableCountMeta', `${total} total`)
}

/* ─── SEARCH: Quick chip ─────────────────────────────────────────── */
function quickSearch(id) {
  $('searchInput').value = id
  analyzeShipment()
}

/* ─── SEARCH: Analyze a shipment ID ──────────────────────────────── */
async function analyzeShipment() {
  const raw = ($('searchInput')?.value || '').trim().toUpperCase()
  if (!raw) { showToast('Enter a shipment ID first', true); return }

  showToast(`🔍 Looking up ${raw}…`)
  try {
    const r = await apiFetch(`/api/shipments/${raw}`)
    currentShip = r.data
    renderShipmentResult(r.data, r.audit_trail || [])
    $('resultSection').style.display = ''
    $('resultSection').scrollIntoView({ behavior: 'smooth', block: 'start' })
    showToast(`✓ Loaded ${raw}`)
  } catch(e) {
    const isOffline = e.message.toLowerCase().includes('fetch') || e.message.includes('NetworkError')
    if (isOffline) {
      showToast('⚠ Backend offline — run: uvicorn main:app --reload in /backend', true)
    } else if (e.message.includes('not found') || e.message.includes('404')) {
      showToast(`${raw} not in database — click "Re-Seed Data" in the sidebar first`, true)
    } else {
      showToast(`Error: ${e.message}`, true)
    }
    $('resultSection').style.display = 'none'
  }
}

/* ─── Render full shipment result ────────────────────────────────── */
function renderShipmentResult(s, auditTrail) {
  const cls = s.hs_classifications?.[0] || null
  const fta = s.fta_results?.[0]        || null
  const cif = (s.shipment_value_usd||0) + (s.freight_cost_usd||0) + (s.insurance_cost_usd||0)

  // ── Shipment Hero ──
  setText('shipIdTag', s.sap_shipment_id)
  setText('shipName',  s.product_description)
  const statusColor = {approved:'var(--teal)',flagged:'var(--error)',pending:'var(--amber)'}[s.status]||'var(--muted)'
  setHtml('shipMeta', `
    <span class="ship-meta-item"><i class="ti ti-map-pin"></i> <strong>${s.origin_country}</strong> → ${s.destination_country}</span>
    <span class="ship-meta-item"><i class="ti ti-currency-dollar"></i> <strong>USD ${cif.toLocaleString()}</strong> CIF</span>
    <span class="ship-meta-item"><i class="ti ti-percentage"></i> Supplier RVC <strong>${s.supplier_rvc_pct||0}%</strong></span>
    <span class="ship-meta-item">
      <span style="display:inline-flex;align-items:center;gap:4px;padding:2px 10px;border-radius:9999px;border:1px solid ${statusColor};color:${statusColor};font-size:11px;font-weight:600">
        ${s.status.toUpperCase()}
      </span>
    </span>
  `)

  // set data-id on run buttons
  ;['btnRunA','btnRunA2','btnRunB','btnRunB2'].forEach(id => {
    const el = $(id); if (el) el.setAttribute('data-id', s.sap_shipment_id)
  })

  // ── Show/hide Resolve button based on escalation status ──
  const isEscalated = s.status === 'flagged'
  const btnResolve  = $('btnResolve')
  const btnEscalate = $('btnEscalate')
  const btnApprove  = $('btnApprove')
  if (btnResolve)  btnResolve.style.display  = isEscalated ? 'flex'   : 'none'
  if (btnEscalate) btnEscalate.style.display  = isEscalated ? 'none'   : 'flex'
  if (btnApprove)  btnApprove.style.display   = isEscalated ? 'none'   : 'flex'

  // ── Module A Card ──
  renderModuleACard(cls)

  // ── Module B Card ──
  renderModuleBCard(fta, cif)

  // ── Module C Card ──
  const lc = s.landed_costs?.[0] || null
  renderModuleCCard(cls, fta, cif, lc)

  // ── Audit Trail ──
  renderAuditTrail(s.sap_shipment_id, auditTrail)
}

/* ─── Module A card ──────────────────────────────────────────────── */
function renderModuleACard(cls) {
  if (!cls) {
    setHtml('modABadge', 'Not run')
    $('modABadge').style.cssText = 'background:var(--surface-cream);color:var(--muted)'
    setHtml('modABody', `
      <div style="color:var(--muted-soft);font-size:12px;line-height:1.8;text-align:center;padding:20px 0">
        <i class="ti ti-brain" style="font-size:32px;display:block;margin-bottom:8px;color:var(--hairline)"></i>
        <strong style="color:var(--ink);font-size:13px">Module A not run yet</strong><br>
        Click <em>Run Module A</em> below.<br>
        <span style="font-size:11px">Uses: nomic-embed-text → pgvector → llama3.2</span>
      </div>`)
    return
  }

  const passed = cls.module_a_status === 'auto_passed'
  const bColor = passed ? 'var(--teal)' : 'var(--amber)'
  const bText  = passed ? '✓ Auto Passed' : '⚠ Low Confidence'
  const badge  = $('modABadge')
  if (badge) { badge.textContent = bText; badge.style.cssText = `background:${passed?'rgba(93,184,166,.12)':'rgba(232,165,90,.12)'};color:${bColor}` }

  const conf = cls.confidence_score || 0
  const barW = Math.min(conf, 100)
  const barColor = conf >= 95 ? '#5db8a6' : conf >= 85 ? '#e8a55a' : '#c64545'
  const thresh = 85

  // RAG sources
  const ragHtml = (cls.rag_sources || []).map(r => `
    <div class="rag-row">
      <span class="rag-code">${r.hs_code}</span>
      <span style="flex:1;font-size:10.5px;color:var(--muted-soft);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.description||''}</span>
      <div class="rag-bar" style="margin:0 8px;width:60px"><div class="rag-fill" style="width:${Math.round((r.similarity||0)*100)}%"></div></div>
      <span class="rag-pct">${Math.round((r.similarity||0)*100)}%</span>
    </div>`).join('')

  setHtml('modABody', `
    <div style="display:flex;align-items:flex-end;gap:10px;margin-bottom:4px">
      <div class="hs-big">${cls.final_hs_code}</div>
      <div style="font-size:11px;color:var(--muted-soft);margin-bottom:6px">final HS code</div>
    </div>
    <div class="hs-desc">e2open hint: <span style="font-family:var(--mono);color:var(--primary)">${cls.e2open_hs_code||'—'}</span>
      ${cls.e2open_hs_code === cls.ai_hs_code
        ? `<span style="color:var(--teal);margin-left:6px">✓ AI agrees</span>`
        : `<span style="color:var(--amber);margin-left:6px">⚠ AI overrides to ${cls.ai_hs_code}</span>`}
    </div>

    <div class="conf-bar-wrap">
      <div class="conf-bar-label">
        <span>AI Confidence</span>
        <span class="val" style="color:${barColor}">${conf}% — ${passed ? 'auto approved' : 'analyst review needed'}</span>
      </div>
      <div class="conf-track">
        <div class="conf-fill" style="width:${barW}%;background:${barColor}"></div>
      </div>
      <div style="position:relative;height:14px;margin-top:2px">
        <div style="position:absolute;left:${thresh}%;transform:translateX(-50%);font-size:9px;color:var(--muted-soft)">85% threshold</div>
      </div>
    </div>

    <button class="expand-toggle" onclick="toggleExpand('reasonExpand')">
      <i class="ti ti-brain" style="font-size:15px"></i> AI Reasoning &amp; RAG Sources — click to expand
      <i class="ti ti-chevron-down" style="font-size:14px;margin-left:auto"></i>
    </button>
    <div class="expand-body" id="reasonExpand">
      <div style="padding:10px;background:var(--surface-soft);border-radius:var(--r-md);font-size:11.5px;line-height:1.7;color:var(--muted-soft);margin-bottom:10px">
        <strong style="color:var(--ink);display:block;margin-bottom:4px">llama3.2 reasoning:</strong>
        ${cls.reasoning_text || '—'}
      </div>
      ${ragHtml ? `<div style="margin-top:8px"><div style="font-size:10.5px;font-weight:500;color:var(--muted-soft);margin-bottom:4px">pgvector similarity matches:</div>${ragHtml}</div>` : ''}
    </div>
  `)
}

/* ─── Module B card ──────────────────────────────────────────────── */
function renderModuleBCard(fta, cif) {
  if (!fta) {
    setHtml('modBBadge', 'Not run')
    $('modBBadge').style.cssText = 'background:var(--surface-cream);color:var(--muted)'
    setHtml('modBBody', `
      <div style="color:var(--muted-soft);font-size:12px;line-height:1.8;text-align:center;padding:20px 0">
        <i class="ti ti-world" style="font-size:32px;display:block;margin-bottom:8px;color:var(--hairline)"></i>
        <strong style="color:var(--ink);font-size:13px">Module B not run yet</strong><br>
        Click <em>Run Module B</em> below.<br>
        <span style="font-size:11px">Checks 17 Malaysian FTAs · Rules of Origin</span>
      </div>`)
    return
  }

  const bStatus = fta.module_b_status || ''
  const bColor  = bStatus === 'fta_applied' ? 'var(--teal)' :
                  bStatus === 'mfn_applied'  ? 'var(--amber)' : 'var(--error)'
  const bLabel  = {fta_applied:'✓ FTA Applied',mfn_applied:'⚠ MFN Fallback',no_fta_available:'✗ No FTA'}[bStatus] || bStatus

  const badge = $('modBBadge')
  if (badge) {
    badge.textContent = bLabel
    badge.style.cssText = `background:${bStatus==='fta_applied'?'rgba(93,184,166,.12)':bStatus==='mfn_applied'?'rgba(232,165,90,.12)':'rgba(198,69,69,.10)'};color:${bColor}`
  }

  // Cap at 100 to guard against dirty legacy records (e.g. rate=853400)
  const mfn  = Math.min(Math.max(fta.mfn_rate_pct  || 0, 0), 100)
  const ftaR = Math.min(Math.max(fta.best_fta_rate_pct ?? 0, 0), 100)
  const mfnW = mfn > 0 ? 100 : 0
  const ftaW = mfn > 0 ? Math.round((ftaR / mfn) * 100) : 0
  const saving = fta.duty_saving_usd || 0

  const allFTAs = Array.isArray(fta.applicable_ftas) ? fta.applicable_ftas : []
  const ftaListHtml = allFTAs.map(f => `
    <div class="fta-list-item">
      <span class="fta-check" style="color:${f.qualifies?'var(--teal)':'var(--surface-cream)'}">
        ${f.qualifies ? '✓' : '✗'}
      </span>
      <span class="fta-nm">${f.fta_name}</span>
      <span class="fta-reason">${f.reason||''}</span>
      <span class="fta-rate-val" style="color:${f.qualifies?'var(--teal)':'var(--muted-soft)'}">
        ${f.qualifies ? pct(f.rate) : '—'}
      </span>
    </div>`).join('')

  setHtml('modBBody', `
    ${saving > 0 ? `
    <div class="savings-badge">
      <div class="savings-label">Duty Saving Identified</div>
      <div class="savings-amount">${money(saving)}</div>
      <div class="savings-sub">${mfn}% MFN → ${ftaR}% ${fta.best_fta_name} · ${mfn > 0 ? Math.round((1-ftaR/mfn)*100) : 100}% reduction</div>
    </div>` : `
    <div style="background:rgba(198,69,69,.06);border:1px solid rgba(198,69,69,.15);border-radius:var(--r-lg);padding:14px 16px;text-align:center;margin-bottom:14px">
      <div style="font-size:11px;color:var(--muted-soft);margin-bottom:4px">Duty Saving</div>
      <div style="font-size:20px;font-weight:600;color:var(--error)">$0.00</div>
      <div style="font-size:11px;color:var(--muted-soft);margin-top:2px">${bStatus === 'no_fta_available' ? 'No FTA covers this origin' : 'RVC threshold not met'}</div>
    </div>`}

    <div class="rate-compare">
      <div style="font-size:10.5px;color:var(--muted-soft);margin-bottom:10px;font-weight:500;text-transform:uppercase;letter-spacing:.05em">Rate Comparison</div>
      <div class="rate-row">
        <span class="rate-label">Without FTA</span>
        <div class="rate-bar-wrap"><div class="rate-bar mfn" style="width:${mfnW}%"></div></div>
        <span class="rate-pct">${pct(mfn)}</span>
      </div>
      <div class="rate-row">
        <span class="rate-label" style="color:var(--teal)">${fta.best_fta_name}</span>
        <div class="rate-bar-wrap"><div class="rate-bar fta" style="width:${Math.max(ftaW,2)}%"></div></div>
        <span class="rate-pct" style="color:var(--teal)">${pct(ftaR)}</span>
      </div>
    </div>

    <div style="font-size:14px;color:var(--muted-soft);margin-bottom:8px;line-height:1.7">
      RoO: <strong style="color:var(--ink)">${fta.roo_type||'—'}</strong>
      · Supplier RVC <strong style="color:var(--ink)">${fta.rvc_supplier_declared||0}%</strong>
      ${fta.rvc_threshold ? `≥ ${fta.rvc_threshold}% threshold` : ''}
    </div>

    ${allFTAs.length ? `
    <button class="expand-toggle" onclick="toggleExpand('ftaListExpand')">
      <i class="ti ti-list" style="font-size:15px"></i> All ${allFTAs.length} FTAs checked — click to expand
      <i class="ti ti-chevron-down" style="font-size:14px;margin-left:auto"></i>
    </button>
    <div class="expand-body" id="ftaListExpand">
      ${ftaListHtml}
    </div>` : ''}
  `)
}

/* ─── Module C card ──────────────────────────────────────────────── */
function renderModuleCCard(cls, fta, cif, lc) {
  const hs   = cls?.final_hs_code
  const rate = fta?.best_fta_rate_pct

  const badge = $('modCBadge')
  if (badge) {
    if (lc) {
      badge.textContent = '✓ Complete'
      badge.style.cssText = 'background:rgba(93,184,166,.12);color:var(--teal)'
    } else {
      badge.textContent = '⬅ Build This'
      badge.style.cssText = 'background:rgba(217,119,6,.10);color:#d97706'
    }
  }

  if (!lc) {
    setHtml('mcHS',   hs   ? `<span style="font-family:var(--mono);color:var(--teal)">${hs}</span>`
                           : `<span style="color:var(--muted-soft)">⬆ run Module A</span>`)
    setHtml('mcRate', rate != null
      ? `<span style="font-family:var(--mono);color:var(--teal)">${rate}% (${fta.best_fta_name})</span>`
      : `<span style="color:var(--muted-soft)">⬆ run Module B</span>`)
    setHtml('mcCIF',  `<span style="font-family:var(--mono)">USD ${cif.toLocaleString()}</span>`)
    setHtml('mcTotal', `<span style="color:#d97706">Awaiting Module C</span>`)
    return
  }

  const breakdown    = lc.cost_breakdown || []
  const totalCifMyr  = breakdown.reduce((s, r) => s + (r.apportionment_metrics?.calculated_cif_myr      || 0), 0)
  const totalDutyMyr = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.customs_duty_charged   || 0), 0)
  const totalAddMyr  = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.anti_dumping_duty_charged || 0), 0)
  const totalTaxMyr  = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.sales_tax_charged      || 0), 0)
  const fxEst        = totalCifMyr > 0 && lc.cif_value_usd > 0 ? totalCifMyr / lc.cif_value_usd : 4.67
  const processingMyr = Math.round((lc.other_fees_usd || 0) * fxEst * 100) / 100
  const isLmw        = breakdown[0]?.flags_applied?.is_lmw_facility ?? true
  const hasAdd       = breakdown.some(r => r.flags_applied?.anti_dumping_matched)
  const fmt          = n => n.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})

  setHtml('modCBody', `
    <div style="font-size:11.5px;color:var(--muted-soft);margin-bottom:10px">
      Malaysian RMCD landed cost breakdown
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
      ${isLmw ? `<span style="padding:3px 10px;border-radius:9999px;background:rgba(93,184,166,.1);color:var(--teal);font-size:11px;font-weight:600">✓ LMW Exempt</span>` : ''}
      ${hasAdd ? `<span style="padding:3px 10px;border-radius:9999px;background:rgba(232,165,90,.1);color:var(--amber);font-size:11px;font-weight:600">⚠ ADD Applied</span>` : ''}
    </div>
    <div class="formula-row">
      <span class="formula-lbl">HS Code <em style="font-style:normal;color:var(--teal);font-size:10px">(from A)</em></span>
      <span class="formula-val"><span style="font-family:var(--mono);color:var(--teal)">${hs || '—'}</span></span>
    </div>
    <div class="formula-row">
      <span class="formula-lbl">FTA Rate <em style="font-style:normal;color:var(--teal);font-size:10px">(from B)</em></span>
      <span class="formula-val"><span style="font-family:var(--mono);color:var(--teal)">${rate ?? '—'}% (${fta?.best_fta_name || '—'})</span></span>
    </div>
    <div style="border-top:1px solid var(--hairline);margin:10px 0"></div>
    <div class="formula-row">
      <span class="formula-lbl">Total CIF (MYR)</span>
      <span class="formula-val"><span style="font-family:var(--mono)">MYR ${fmt(totalCifMyr)}</span></span>
    </div>
    <div class="formula-row">
      <span class="formula-lbl">Customs Duty</span>
      <span class="formula-val" style="color:${totalDutyMyr === 0 ? 'var(--teal)' : 'var(--ink)'}">
        <span style="font-family:var(--mono)">MYR ${fmt(totalDutyMyr)}</span>
      </span>
    </div>
    ${totalAddMyr > 0 ? `
    <div class="formula-row">
      <span class="formula-lbl">Anti-Dumping Duty</span>
      <span class="formula-val" style="color:var(--amber)"><span style="font-family:var(--mono)">MYR ${fmt(totalAddMyr)}</span></span>
    </div>` : ''}
    <div class="formula-row">
      <span class="formula-lbl">Sales Tax (10%)</span>
      <span class="formula-val" style="color:${totalTaxMyr === 0 ? 'var(--teal)' : 'var(--ink)'}">
        <span style="font-family:var(--mono)">MYR ${fmt(totalTaxMyr)}</span>
      </span>
    </div>
    <div class="formula-row">
      <span class="formula-lbl">Processing Fee</span>
      <span class="formula-val"><span style="font-family:var(--mono)">MYR ${fmt(processingMyr)}</span></span>
    </div>
    <div class="formula-total" style="margin-top:14px">
      <span class="formula-total-lbl"><i class="ti ti-calculator" style="margin-right:4px"></i>Total Landed Cost</span>
      <span class="formula-total-val" id="mcTotal" style="color:var(--teal)">
        USD ${fmt(lc.total_landed_cost_usd || 0)}
      </span>
    </div>
    ${(lc.fta_saving_usd || 0) > 0 ? `
    <div style="margin-top:8px;text-align:center;font-size:11px;color:var(--teal);font-weight:600">
      ↓ FTA saves USD ${fmt(lc.fta_saving_usd)} vs MFN scenario
    </div>` : ''}
  `)
}

/* ─── Audit Trail ────────────────────────────────────────────────── */
function renderAuditTrail(shipId, trail) {
  setText('auditMeta', shipId)
  if (!trail || !trail.length) {
    setHtml('auditBody', `<div style="padding:16px 0;color:var(--muted-soft);font-size:12px">No audit records for this shipment yet.</div>`)
    return
  }
  setHtml('auditBody', trail.map(e => `
    <div class="audit-row">
      <span class="audit-time">${new Date(e.created_at).toLocaleTimeString()}</span>
      <i class="ti ti-circle-check audit-ico" style="color:var(--teal)"></i>
      <span class="audit-msg">${e.analyst_note || e.event_type || JSON.stringify(e)}</span>
    </div>`).join(''))
}

/* ─── Expand toggle ──────────────────────────────────────────────── */
function toggleExpand(id) {
  const el = $(id)
  if (!el) return
  el.classList.toggle('open')
  const btn = el.previousElementSibling
  if (btn) {
    const icon = btn.querySelector('.ti-chevron-down, .ti-chevron-up')
    if (icon) {
      icon.classList.toggle('ti-chevron-down', !el.classList.contains('open'))
      icon.classList.toggle('ti-chevron-up',   el.classList.contains('open'))
    }
  }
}

/* ─── Module triggers ────────────────────────────────────────────── */
function getActiveId() {
  const el = $('btnRunA'); return el?.getAttribute('data-id') || null
}

async function triggerA() {
  const id = getActiveId()
  if (!id) { showToast('Search for a shipment first', true); return }
  await runSingleA(id)
}
async function triggerB() {
  const id = getActiveId()
  if (!id) { showToast('Search for a shipment first', true); return }
  await runSingleB(id)
}

async function runSingleA(shipmentId) {
  showToast(`⏳ Module A running for ${shipmentId}… (llama3.2, ~30s)`)
  const btns = ['btnRunA','btnRunA2'].map(i=>$(i)).filter(Boolean)
  btns.forEach(b => { b.disabled = true; b.innerHTML = '<i class="ti ti-loader-2 spin"></i> Running…' })
  try {
    const r = await runModuleA(shipmentId)
    if (r.status === 'ok') {
      const c = r.classification
      showToast(`✓ Module A — ${c?.final_hs_code} · ${c?.confidence_score}% confidence`)
    } else {
      showToast('Module A failed: ' + (r.detail||'unknown'), true)
    }
    await reloadCurrentShipment(shipmentId)
  } catch(e) { showToast('Module A error: ' + e.message, true) }
  finally {
    btns.forEach(b => { b.disabled = false; b.innerHTML = '<i class="ti ti-brain"></i> Run Module A' })
  }
}

async function runSingleB(shipmentId) {
  showToast(`⏳ Module B running for ${shipmentId}…`)
  const btns = ['btnRunB','btnRunB2'].map(i=>$(i)).filter(Boolean)
  btns.forEach(b => { b.disabled = true; b.innerHTML = '<i class="ti ti-loader-2 spin"></i> Running…' })
  try {
    const r = await runModuleB(shipmentId)
    if (r.status === 'ok') {
      const d = r.data
      showToast(`✓ Module B — ${d?.best_fta} @ ${d?.fta_rate_pct}% · saved ${money(d?.duty_saving_usd)}`)
      await reloadCurrentShipment(shipmentId)
      await runSingleC(shipmentId)
    } else {
      showToast('Module B failed: ' + (r.detail||'unknown'), true)
      await reloadCurrentShipment(shipmentId)
    }
  } catch(e) { showToast('Module B error: ' + e.message, true) }
  finally {
    btns.forEach(b => { b.disabled = false; b.innerHTML = '<i class="ti ti-world"></i> Run Module B' })
  }
}

async function triggerC() {
  const id = getActiveId()
  if (!id) { showToast('Search for a shipment first', true); return }
  await runSingleC(id)
}

async function runSingleC(shipmentId) {
  showToast(`⏳ Module C running for ${shipmentId}…`)
  const btns = ['btnRunC','btnRunC2'].map(i => $(i)).filter(Boolean)
  btns.forEach(b => { b.disabled = true; b.innerHTML = '<i class="ti ti-loader-2 spin"></i> Running…' })
  try {
    const r = await runModuleC(shipmentId)
    if (r.status === 'ok') {
      const d = r.data
      showToast(`✓ Module C — Landed USD ${money(d?.total_landed_usd)} | LMW=${d?.is_lmw_facility}`)
    } else {
      showToast('Module C failed: ' + (r.detail || 'unknown'), true)
    }
    await reloadCurrentShipment(shipmentId)
  } catch(e) { showToast('Module C error: ' + e.message, true) }
  finally {
    btns.forEach(b => { b.disabled = false; b.innerHTML = '<i class="ti ti-calculator"></i> Run Module C' })
  }
}

async function reloadCurrentShipment(id) {
  await loadShipments()
  await loadSummary()
  try {
    const r = await apiFetch(`/api/shipments/${id}`)
    currentShip = r.data
    renderShipmentResult(r.data, r.audit_trail || [])
  } catch(e) { console.warn('Reload failed:', e) }
}

/* ─── All Shipments table ────────────────────────────────────────── */
function getFiltered() {
  if (activeFilter === 'flagged')  return SHIPMENTS.filter(s => s.status === 'flagged')
  if (activeFilter === 'approved') return SHIPMENTS.filter(s => s.status === 'approved')
  if (activeFilter === 'pending')  return SHIPMENTS.filter(s => s.status === 'pending')
  return SHIPMENTS
}

function setFilter(f, btn) {
  activeFilter = f
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'))
  btn.classList.add('active')
  renderTable()
}

function renderTable() {
  const items = getFiltered()
  const total = SHIPMENTS.length
  const flag  = SHIPMENTS.filter(s => s.status==='flagged').length
  const appr  = SHIPMENTS.filter(s => s.status==='approved').length
  const pend  = SHIPMENTS.filter(s => s.status==='pending').length
  const tabs  = document.querySelectorAll('.filter-bar .tab')
  if (tabs[0]) tabs[0].textContent = `All (${total})`
  if (tabs[1]) tabs[1].innerHTML = `<i class="ti ti-alert-circle" style="font-size:11px"></i> Flagged (${flag})`
  if (tabs[2]) tabs[2].innerHTML = `<i class="ti ti-check" style="font-size:11px"></i> Approved (${appr})`
  if (tabs[3]) tabs[3].textContent = `Pending (${pend})`

  if (!items.length) {
    setHtml('tblBody', `<div style="padding:20px;color:var(--muted-soft);font-size:12px">No shipments.</div>`)
    return
  }

  setHtml('tblBody', items.map(s => {
    const cls  = s.hs_classifications?.[0] || {}
    const fta  = s.fta_results?.[0]        || {}
    const lc   = s.landed_costs?.[0]       || {}
    const hasA = !!cls.final_hs_code
    const hasB = !!fta.best_fta_name
    const hasC = !!lc.total_landed_cost_usd
    const conf   = cls.confidence_score || 0
    const saving = fta.duty_saving_usd  || 0
    const ftaName = fta.best_fta_name || '—'
    return `
      <div class="tbl-row" onclick="quickSearch('${s.sap_shipment_id}');showView('lookup')">
        <span class="row-num">${s.sap_shipment_id}</span>
        <span class="hs-code">${cls.final_hs_code||'—'}</span>
        <span>
          <div class="prod-name">${s.product_description}</div>
          <div class="prod-origin" style="display:flex;gap:8px;margin-top:2px">
            ${pDot(hasA,'A')} ${pDot(hasB,'B')} ${pDot(hasC,'C')}
          </div>
        </span>
        <span class="conf-cell">
          ${conf ? `<span style="font-size:11.5px;font-family:var(--mono);font-weight:500;color:${confColor(conf)};min-width:29px">${conf}%</span><div class="conf-dots">${renderDots(conf)}</div>`
                 : `<span style="color:var(--muted-soft);font-size:11px">Not run</span>`}
        </span>
        <span class="duty-cell" style="color:${saving>0?'var(--teal)':'var(--muted-soft)'}">
          ${saving>0 ? money(saving) : '—'}
        </span>
        <span class="fta-badge ${ftaName==='MFN'?'fta-mfn':ftaName!=='—'?'fta-other':''}"
          style="${ftaName==='—'?'opacity:.3':''}">
          ${ftaName}
        </span>
        <span class="row-acts">
          <button class="ibt" title="Run Module A" onclick="event.stopPropagation();runSingleA('${s.sap_shipment_id}')">
            <i class="ti ti-brain"></i></button>
          <button class="ibt" title="Run Module B" onclick="event.stopPropagation();runSingleB('${s.sap_shipment_id}')">
            <i class="ti ti-world"></i></button>
          <button class="ibt" title="Open detail" onclick="event.stopPropagation();quickSearch('${s.sap_shipment_id}');showView('lookup')">
            <i class="ti ti-arrow-right"></i></button>
        </span>
      </div>`
  }).join(''))
}

/* ─── Bulk ───────────────────────────────────────────────────────── */
async function doBulk() {
  const pending = SHIPMENTS.filter(s => s.status==='pending')
  if (!pending.length) { showToast('No pending shipments'); return }
  showToast(`Running A + B for ${pending.length} shipments…`)
  for (const s of pending) {
    const hasA = s.hs_classifications?.length > 0
    if (!hasA) await runSingleA(s.sap_shipment_id).catch(()=>{})
    await runSingleB(s.sap_shipment_id).catch(()=>{})
  }
  showToast('✓ All pending processed')
  await loadShipments()
}

/* ─── Seed ───────────────────────────────────────────────────────── */
async function runSeedAndRefresh() {
  showToast('Seeding database… please wait')
  try {
    const r = await runSeed()
    const n   = r.result?.shipments || 0
    const cls = r.result?.mock_classifications || 0
    showToast(`✓ Seed done — ${n} shipments, ${cls} classifications loaded`)
    await loadShipments()
    await loadSummary()
    // Refresh the displayed shipment so the result section is not stale
    if (currentShip) {
      await reloadCurrentShipment(currentShip.sap_shipment_id)
    }
  } catch(e) { showToast('Seed failed: ' + e.message, true) }
}

/* ─── Toast ──────────────────────────────────────────────────────── */
function showToast(msg, isError = false) {
  const t = $('toast'); if (!t) return
  const msgEl = $('toastMsg')
  if (msgEl) msgEl.textContent = msg; else t.childNodes[0] && (t.childNodes[0].textContent = msg)
  t.style.background = isError ? '#dc2626' : '#0d9488'
  t.classList.add('show')
  clearTimeout(t._autoClose)
  t._autoClose = setTimeout(() => t.classList.remove('show'), isError ? 10000 : 7000)
}

/* ─── Approve / Submit ───────────────────────────────────────────── */
function approveItem() { openModal('approvedModal') }
function submitBatch()  { closeModal('batchModal'); showToast('✓ Batch submitted to SAP S/4HANA') }

/* ─── Escalate ───────────────────────────────────────────────────── */
async function submitEscalation() {
  const id = getActiveId()
  if (!id) { showToast('No shipment selected', true); return }

  const assignee = $('escalateAssignee')?.value?.trim() || 'Senior Analyst'
  const notes    = $('escalateNotes')?.value?.trim()    || ''
  if (!notes) { showToast('Please enter escalation notes', true); return }

  const btn = $('escalateSubmitBtn')
  btn.disabled = true
  btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Sending…'

  try {
    const r = await escalateShipment(id, assignee, notes)
    if (r.status === 'ok') {
      closeModal('escalateModal')
      $('escalateNotes').value = ''
      showToast(`⬆ ${id} escalated to ${assignee}`)
      await reloadCurrentShipment(id)
    } else {
      showToast('Escalation failed: ' + (r.detail || 'unknown'), true)
    }
  } catch(e) { showToast('Escalation error: ' + e.message, true) }
  finally {
    btn.disabled = false
    btn.innerHTML = '<i class="ti ti-send"></i> Send to Senior'
  }
}

/* ─── Resolve Escalation ─────────────────────────────────────────── */
function toggleResolveOverride() {
  const action = $('resolveAction')?.value
  const fields = $('resolveOverrideFields')
  if (fields) fields.style.display = action === 'override' ? 'block' : 'none'
}

async function submitResolve() {
  const id = getActiveId()
  if (!id) { showToast('No shipment selected', true); return }

  const action = $('resolveAction')?.value
  const note   = $('resolveNote')?.value?.trim() || ''
  const btn    = $('resolveSubmitBtn')

  btn.disabled = true
  btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Processing…'

  try {
    if (action === 'override') {
      const hsCode = $('resolveHsCode')?.value?.trim()
      const reason = $('resolveReason')?.value?.trim()
      if (!hsCode) { showToast('Please enter the manual HS code', true); btn.disabled=false; btn.innerHTML='<i class="ti ti-check"></i> Confirm & Unblock'; return }
      if (!reason) { showToast('Please enter a reason for the override', true); btn.disabled=false; btn.innerHTML='<i class="ti ti-check"></i> Confirm & Unblock'; return }
      await overrideHSCode(id, hsCode, reason + (note ? ` | Senior note: ${note}` : ''))
      showToast(`✏ ${id} overridden to ${hsCode} and approved`)
    } else {
      await approveShipment(id)
      showToast(`✓ ${id} resolved and approved by Senior Analyst`)
    }
    closeModal('resolveModal')
    $('resolveNote').value = ''
    $('resolveHsCode') && ($('resolveHsCode').value = '')
    $('resolveReason') && ($('resolveReason').value = '')
    await reloadCurrentShipment(id)
  } catch(e) { showToast('Resolve error: ' + e.message, true) }
  finally {
    btn.disabled = false
    btn.innerHTML = '<i class="ti ti-check"></i> Confirm & Unblock'
  }
}

/* ─── Modals ─────────────────────────────────────────────────────── */
function openModal(id)  { $(id)?.classList.add('open') }
function closeModal(id) { $(id)?.classList.remove('open') }
document.querySelectorAll('.overlay').forEach(o =>
  o.addEventListener('click', e => { if (e.target===o) o.classList.remove('open') })
)
document.addEventListener('keydown', e => {
  if (e.key==='Escape') document.querySelectorAll('.overlay.open').forEach(o=>o.classList.remove('open'))
})

/* ─── Boot ───────────────────────────────────────────────────────── */
init()
