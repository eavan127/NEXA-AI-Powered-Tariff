/**
 * reports.js — Analytics page logic
 * All charts are pure CSS (no external chart library needed)
 */

let SHIPS = []

/* ── Boot ────────────────────────────────────────────────────── */
loadPage()

async function loadPage() {
  try {
    const [ships, summary] = await Promise.all([fetchShipments(), fetchSummary()])
    SHIPS = ships
    renderKPIs(ships, summary)
    renderSavingsChart(ships)
    renderStatusChart(ships)
    renderOriginChart(ships)
    renderPipeline(ships)
    renderConfidence(ships)
    renderTopSavings(ships)
    setText('reportMeta', `Based on ${ships.length} shipments · ${new Date().toLocaleString()}`)
  } catch (e) {
    showToast('Failed to load analytics: ' + e.message, true)
    setHtml('savingsChart', `<div style="color:var(--error);font-size:12px;padding:12px">Backend offline</div>`)
  }
}

/* ── KPIs ────────────────────────────────────────────────────── */
function renderKPIs(ships, summary) {
  setHtml('rSaving', `$${Math.round(summary.total_fta_saving_usd || 0).toLocaleString()}`)

  // Average confidence across classified shipments
  const classifiedConfs = ships
    .map(s => s.hs_classifications?.[0]?.confidence_score)
    .filter(c => c != null)
  const avgConf = classifiedConfs.length
    ? Math.round(classifiedConfs.reduce((a, b) => a + b, 0) / classifiedConfs.length)
    : 0
  setHtml('rAvgConf', avgConf ? `${avgConf}<span class="unit">%</span>` : '—')

  // FTA coverage rate
  const withFTA = ships.filter(s => s.fta_results?.[0]?.module_b_status === 'fta_applied').length
  const ftaCovPct = ships.length ? Math.round(withFTA / ships.length * 100) : 0
  setHtml('rFtaCoverage', ships.length ? `${ftaCovPct}<span class="unit">%</span>` : '—')

  // Compliance rate (approved out of total)
  const approved = ships.filter(s => s.status === 'approved').length
  const compPct  = ships.length ? Math.round(approved / ships.length * 100) : 0
  setHtml('rCompliance', ships.length ? `${compPct}<span class="unit">%</span>` : '—')
}

/* ── FTA savings breakdown chart ─────────────────────────────── */
function renderSavingsChart(ships) {
  // Group by best_fta_name
  const byFTA = {}
  for (const s of ships) {
    const fta  = s.fta_results?.[0]
    const name = fta?.best_fta_name || 'None'
    const sav  = fta?.duty_saving_usd || 0
    if (!byFTA[name]) byFTA[name] = { count: 0, saving: 0 }
    byFTA[name].count++
    byFTA[name].saving += sav
  }

  const rows = Object.entries(byFTA)
    .sort((a, b) => b[1].saving - a[1].saving)

  const maxSav = Math.max(...rows.map(r => r[1].saving), 1)

  const FTA_COLORS = {
    RCEP: '#5db8a6', CPTPP: '#e8a55a', ACFTA: '#cc785c',
    AKFTA: '#a09d96', AJCEP: '#6b8cba', MFN: '#8e8b82', None: '#e6dfd8'
  }

  setHtml('savingsChart', rows.map(([name, d]) => {
    const w     = Math.max(Math.round(d.saving / maxSav * 100), d.saving > 0 ? 4 : 0)
    const color = FTA_COLORS[name] || 'var(--primary)'
    const label = name === 'None' ? 'No FTA' : name
    return `
    <div class="bar-chart-row">
      <span class="bar-lbl" title="${label}">${label}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${w}%;background:${color}"></div>
      </div>
      <span class="bar-val">
        ${d.saving > 0
          ? `<span style="color:var(--teal);font-weight:600">${money(d.saving)}</span>`
          : `<span style="color:var(--muted-soft)">$0.00</span>`}
        <span style="font-size:10px;color:var(--muted-soft);display:block">${d.count} shipment${d.count !== 1 ? 's' : ''}</span>
      </span>
    </div>`
  }).join(''))
}

/* ── Status distribution ─────────────────────────────────────── */
function renderStatusChart(ships) {
  const total    = ships.length || 1
  const approved = ships.filter(s => s.status === 'approved').length
  const flagged  = ships.filter(s => s.status === 'flagged').length
  const pending  = ships.filter(s => s.status === 'pending').length

  const row = (label, count, color) => {
    const w = Math.round(count / total * 100)
    return `
    <div class="bar-chart-row">
      <span class="bar-lbl">${label}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${w}%;background:${color}"></div>
      </div>
      <span class="bar-val">
        <span style="font-weight:600;color:${color}">${count}</span>
        <span style="font-size:10px;color:var(--muted-soft);display:block">${w}%</span>
      </span>
    </div>`
  }

  setHtml('statusChart', [
    row('Approved', approved, 'var(--teal)'),
    row('Flagged',  flagged,  'var(--error)'),
    row('Pending',  pending,  'var(--amber)'),
  ].join(''))
}

/* ── Origin country breakdown ────────────────────────────────── */
function renderOriginChart(ships) {
  const total   = ships.length || 1
  const byOrig  = {}
  for (const s of ships) {
    byOrig[s.origin_country] = (byOrig[s.origin_country] || 0) + 1
  }
  const rows = Object.entries(byOrig).sort((a, b) => b[1] - a[1])

  const ORIG_COLORS = {
    'Vietnam': '#5db8a6', 'China': '#cc785c',
    'South Korea': '#a09d96', 'Taiwan': '#e8a55a', 'India': '#b85d5d'
  }

  setHtml('originChart', rows.map(([name, count]) => {
    const w     = Math.round(count / total * 100)
    const color = ORIG_COLORS[name] || 'var(--muted-soft)'
    return `
    <div class="bar-chart-row">
      <span class="bar-lbl" title="${name}">${name}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${w}%;background:${color}"></div>
      </div>
      <span class="bar-val">${count} <span style="font-size:10px;color:var(--muted-soft)">(${w}%)</span></span>
    </div>`
  }).join(''))
}

/* ── Module pipeline completion ──────────────────────────────── */
function renderPipeline(ships) {
  const total = ships.length || 1
  const wA    = ships.filter(s => s.hs_classifications?.length > 0).length
  const wB    = ships.filter(s => s.fta_results?.length > 0).length
  const wC    = ships.filter(s => s.landed_costs?.length > 0).length

  const pipe = (label, count, color, note) => `
  <div style="margin-bottom:var(--sp-lg)">
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">
      <span style="font-size:13px;font-weight:500;color:var(--ink)">${label}</span>
      <span style="font-family:var(--mono);font-size:13px;font-weight:600;color:${color}">${count}/${total}</span>
    </div>
    <div class="progress-track" style="height:8px">
      <div class="progress-fill" style="width:${Math.round(count/total*100)}%;background:${color};border-radius:var(--r-pill)"></div>
    </div>
    <div style="font-size:11px;color:var(--muted-soft);margin-top:4px">${note}</div>
  </div>`

  setHtml('pipelinePanel', [
    pipe('Module A · HS Classification', wA, 'var(--teal)',
         'nomic-embed-text → pgvector → qwen2.5:1.5b'),
    pipe('Module B · FTA Matching', wB, 'var(--primary)',
         '17 Malaysian FTAs · Rules of Origin check'),
    pipe('Module C · Landed Cost', wC, '#d97706',
         'Duty + SST + fees → total landed cost (teammate C building this)'),
  ].join(''))
}

/* ── Confidence distribution ─────────────────────────────────── */
function renderConfidence(ships) {
  const classified = ships.filter(s => s.hs_classifications?.length > 0)
  if (!classified.length) {
    setHtml('confDist', `<div style="color:var(--muted-soft);font-size:12px;text-align:center;padding:20px">
      No classified shipments yet — run Module A first.
    </div>`)
    return
  }

  const buckets = [
    { label: '95–100%', min: 95, max: 100, color: '#5db8a6' },
    { label: '85–94%',  min: 85, max: 94,  color: '#e8a55a' },
    { label: '70–84%',  min: 70, max: 84,  color: '#cc785c' },
    { label: '< 70%',   min:  0, max: 69,  color: 'var(--error)' },
  ]

  const maxCount = Math.max(...buckets.map(b =>
    classified.filter(s => {
      const c = s.hs_classifications[0].confidence_score
      return c >= b.min && c <= b.max
    }).length
  ), 1)

  setHtml('confDist', buckets.map(b => {
    const ships_in = classified.filter(s => {
      const c = s.hs_classifications[0].confidence_score
      return c >= b.min && c <= b.max
    })
    const w = Math.round(ships_in.length / maxCount * 100)
    const passFail = b.min >= 85
      ? `<span style="color:var(--teal);font-size:10px">✓ Auto-pass threshold</span>`
      : `<span style="color:var(--error);font-size:10px">⚠ Needs review</span>`
    return `
    <div class="bar-chart-row" style="margin-bottom:12px">
      <span class="bar-lbl">${b.label}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${w}%;background:${b.color}"></div>
      </div>
      <span class="bar-val">
        <span style="font-weight:600;color:${b.color}">${ships_in.length}</span>
        <div style="margin-top:2px">${passFail}</div>
      </span>
    </div>`
  }).join(''))
}

/* ── Top shipments by saving ─────────────────────────────────── */
function renderTopSavings(ships) {
  const withSaving = ships
    .filter(s => (s.fta_results?.[0]?.duty_saving_usd || 0) > 0)
    .sort((a, b) => (b.fta_results[0].duty_saving_usd) - (a.fta_results[0].duty_saving_usd))

  if (!withSaving.length) {
    setHtml('topSavings', `<div style="padding:24px;color:var(--muted-soft);font-size:12px;text-align:center">
      No FTA savings computed yet — run Module B on your shipments.
    </div>`)
    return
  }

  setHtml('topSavings', withSaving.map(s => {
    const cls  = s.hs_classifications?.[0] || {}
    const fta  = s.fta_results[0]
    return `
    <div class="top-tbl-row fade-in" onclick="location='index.html?id=${s.sap_shipment_id}'" title="Open detail">
      <span style="font-family:var(--mono);font-size:11.5px;color:var(--primary);font-weight:600">${s.sap_shipment_id}</span>
      <span style="font-family:var(--mono);font-size:12px;color:var(--ink)">${cls.final_hs_code || '—'}</span>
      <span style="font-size:12.5px;color:var(--body);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.product_description}</span>
      <span>
        <span class="fta-badge fta-other">${fta.best_fta_name}</span>
      </span>
      <span style="font-family:var(--mono);font-weight:600;color:var(--teal);text-align:right">
        ${money(fta.duty_saving_usd)}
      </span>
    </div>`
  }).join(''))
}

/* ── Export CSV ──────────────────────────────────────────────── */
function exportCSV() {
  if (!SHIPS.length) { showToast('No data to export', true); return }

  const headers = ['Shipment ID', 'Product', 'Origin', 'HS Code', 'Confidence %',
                   'FTA', 'MFN Rate %', 'FTA Rate %', 'Saving USD', 'Status']
  const rows = SHIPS.map(s => {
    const cls = s.hs_classifications?.[0] || {}
    const fta = s.fta_results?.[0]        || {}
    return [
      s.sap_shipment_id,
      `"${s.product_description}"`,
      s.origin_country,
      cls.final_hs_code || '',
      cls.confidence_score || '',
      fta.best_fta_name || '',
      fta.mfn_rate_pct ?? '',
      fta.best_fta_rate_pct ?? '',
      fta.duty_saving_usd || 0,
      s.status
    ].join(',')
  })

  const csv  = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `nexa-shipments-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  showToast('✓ CSV exported')
}
