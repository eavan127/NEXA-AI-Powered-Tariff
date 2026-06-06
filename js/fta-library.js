/**
 * fta-library.js — FTA Library page logic
 */

/* ── Static FTA metadata — 17 Malaysian FTAs ─────────────────── */
const FTA_META = {
  RCEP:    { full: 'Regional Comprehensive Economic Partnership', year: 2022, color: '#5db8a6',
             desc: 'World\'s largest trading bloc. Covers 30% of global GDP and world population. Includes all major East Asian economies.',
             countries: ['🇻🇳 Vietnam', '🇨🇳 China', '🇯🇵 Japan', '🇰🇷 S. Korea', '🇦🇺 Australia', '🇳🇿 New Zealand', '🇮🇩 Indonesia', '🇹🇭 Thailand', '🇸🇬 Singapore', '🇵🇭 Philippines', '🇲🇲 Myanmar', '🇰🇭 Cambodia', '🇱🇦 Laos', '🇧🇳 Brunei'],
             roo: 'RVC ≥ 35% (RCEP formula) or CTC at heading level' },
  CPTPP:   { full: 'Comprehensive & Progressive TPP', year: 2022, color: '#e8a55a',
             desc: 'High-standard FTA covering goods, services, investment and IP. Excludes the US but covers key Asia-Pacific markets.',
             countries: ['🇦🇺 Australia', '🇧🇳 Brunei', '🇨🇦 Canada', '🇨🇱 Chile', '🇯🇵 Japan', '🇲🇽 Mexico', '🇳🇿 New Zealand', '🇵🇪 Peru', '🇸🇬 Singapore', '🇻🇳 Vietnam'],
             roo: 'RVC ≥ 40% (build-up) or CTC at subheading level' },
  ACFTA:   { full: 'ASEAN-China Free Trade Area', year: 2005, color: '#cc785c',
             desc: 'Eliminates tariffs on most goods. China is Malaysia\'s largest trading partner.',
             countries: ['🇨🇳 China'],
             roo: 'RVC ≥ 40% or CTC at heading level (CTH)' },
  AKFTA:   { full: 'ASEAN-Korea Free Trade Agreement', year: 2007, color: '#a09d96',
             desc: 'Covers trade in goods with the Republic of Korea. Zero tariff on electronics and electrical goods.',
             countries: ['🇰🇷 South Korea'],
             roo: 'RVC ≥ 40% or CTC' },
  AJCEP:   { full: 'ASEAN-Japan Comprehensive Economic Partnership', year: 2008, color: '#6b8cba',
             desc: 'Comprehensive EPA covering goods, services, investment and movement of natural persons.',
             countries: ['🇯🇵 Japan'],
             roo: 'RVC ≥ 40% or CTC at subheading level (CTSH)' },
  AANZFTA: { full: 'ASEAN-Australia-New Zealand FTA', year: 2010, color: '#5db872',
             desc: 'Broad agreement covering goods, services and investment with Australia and New Zealand.',
             countries: ['🇦🇺 Australia', '🇳🇿 New Zealand'],
             roo: 'RVC ≥ 40% or CTC (choice of method)' },
  AIFTA:   { full: 'ASEAN-India Free Trade Agreement', year: 2010, color: '#b85d5d',
             desc: 'Covers trade in goods. India is a growing market for Malaysian electronics and palm oil.',
             countries: ['🇮🇳 India'],
             roo: 'RVC ≥ 35% or CTC at heading level' },
  AHKFTA:  { full: 'ASEAN-Hong Kong Free Trade Agreement', year: 2019, color: '#8b5db8',
             desc: 'Malaysia\'s most recent ASEAN-plus FTA. Extends ASEAN trade benefits to Hong Kong.',
             countries: ['🇭🇰 Hong Kong'],
             roo: 'RVC ≥ 35% or CTC' },
  MJEPA:   { full: 'Malaysia-Japan Economic Partnership Agreement', year: 2006, color: '#6b8cba',
             desc: 'Bilateral EPA with Japan. Covers goods, services, investment and cooperation. Broader than AJCEP.',
             countries: ['🇯🇵 Japan'],
             roo: 'RVC ≥ 40% or CTSH' },
  MKFTA:   { full: 'Malaysia-Korea Free Trade Agreement', year: 2007, color: '#a09d96',
             desc: 'Direct bilateral FTA with South Korea complementing AKFTA.',
             countries: ['🇰🇷 South Korea'],
             roo: 'RVC ≥ 40% or CTC' },
  MPCEPA:  { full: 'Malaysia-Pakistan Closer Economic Partnership', year: 2008, color: '#8ba05d',
             desc: 'Bilateral trade agreement covering goods and investment.',
             countries: ['🇵🇰 Pakistan'],
             roo: 'RVC ≥ 35%' },
  MIFTA:   { full: 'Malaysia-India CECA', year: 2011, color: '#b85d5d',
             desc: 'Comprehensive Economic Cooperation Agreement covering goods, services and investment.',
             countries: ['🇮🇳 India'],
             roo: 'RVC ≥ 35% or CTC' },
  MNZFTA:  { full: 'Malaysia-New Zealand Free Trade Agreement', year: 2010, color: '#5db872',
             desc: 'Bilateral FTA with New Zealand. Covers 99% of NZ goods exports to Malaysia.',
             countries: ['🇳🇿 New Zealand'],
             roo: 'RVC ≥ 40% or CTSH' },
  MCIFTA:  { full: 'Malaysia-Chile Free Trade Agreement', year: 2012, color: '#a05d8b',
             desc: 'Malaysia\'s only bilateral FTA with a Latin American country.',
             countries: ['🇨🇱 Chile'],
             roo: 'RVC ≥ 40% or CTC' },
  MTFTA:   { full: 'Malaysia-Turkey Free Trade Agreement', year: 2015, color: '#cc785c',
             desc: 'Bilateral FTA covering goods. Turkey is an emerging market for Malaysian exports.',
             countries: ['🇹🇷 Turkey'],
             roo: 'RVC ≥ 40%' },
  MAUFTA:  { full: 'Malaysia-Australia Free Trade Agreement', year: 2013, color: '#5db872',
             desc: 'Bilateral FTA with Australia. Complements AANZFTA with additional concessions.',
             countries: ['🇦🇺 Australia'],
             roo: 'RVC ≥ 40% or CTSH' },
  AFTA:    { full: 'ASEAN Free Trade Area', year: 1993, color: '#5db8a6',
             desc: 'Foundational ASEAN agreement. Uses CEPT (Common Effective Preferential Tariff) scheme for intra-ASEAN trade.',
             countries: ['🇮🇩 Indonesia', '🇹🇭 Thailand', '🇸🇬 Singapore', '🇵🇭 Philippines', '🇻🇳 Vietnam', '🇲🇲 Myanmar', '🇰🇭 Cambodia', '🇱🇦 Laos', '🇧🇳 Brunei'],
             roo: 'RVC ≥ 40% (ASEAN content)' },
}

const FTA_ORDER = ['RCEP','CPTPP','ACFTA','AKFTA','AJCEP','AANZFTA','AIFTA','AHKFTA',
                   'MJEPA','MKFTA','MPCEPA','MIFTA','MNZFTA','MCIFTA','MTFTA','MAUFTA','AFTA']

let SHIPMENTS    = []
let COVERAGE_MAP = {} // fta_name → [hs_chapters]

/* ── Boot ────────────────────────────────────────────────────── */
loadPage()

async function loadPage() {
  try {
    const [ships, cov] = await Promise.all([
      fetchShipments().catch(() => []),
      fetchFTACoverage().catch(() => ({ data: [] }))
    ])
    SHIPMENTS = ships

    // Build coverage map: fta_name → Set of hs_chapters
    COVERAGE_MAP = {}
    for (const row of (cov.data || [])) {
      if (!COVERAGE_MAP[row.fta_name]) COVERAGE_MAP[row.fta_name] = new Set()
      COVERAGE_MAP[row.fta_name].add(row.hs_chapter)
    }

    // Count unique partner countries
    const allCountries = new Set()
    for (const meta of Object.values(FTA_META)) {
      meta.countries.forEach(c => allCountries.add(c))
    }
    setText('ftaCountryCount', allCountries.size)

    renderGrid()
  } catch (e) {
    console.error('FTA page load error:', e)
    setHtml('ftaGrid', `<div style="color:var(--error);font-size:12px;padding:20px">Backend offline</div>`)
  }
}

/* ── Render FTA grid ─────────────────────────────────────────── */
function renderGrid() {
  // Compute which FTAs are used in our shipments
  const usedFTAs = {}
  for (const s of SHIPMENTS) {
    const fta = s.fta_results?.[0]
    if (fta?.best_fta_name) {
      usedFTAs[fta.best_fta_name] = (usedFTAs[fta.best_fta_name] || 0) + 1
    }
  }

  setHtml('ftaGrid', FTA_ORDER.map(key => {
    const m    = FTA_META[key]
    const used = usedFTAs[key] || 0
    const chap = COVERAGE_MAP[key]?.size || 0

    return `
    <div class="fta-card${used > 0 ? ' used' : ''}" onclick="toggleFTA('${key}')">
      <div class="fta-card-top" style="background:${m.color}"></div>
      <div class="fta-card-body">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:6px">
          <div class="fta-card-name" style="color:${m.color}">${key}</div>
          <div class="fta-card-year" style="flex-shrink:0">since ${m.year}</div>
        </div>
        <div class="fta-card-full">${m.full}</div>
        <div class="fta-card-countries">
          ${m.countries.slice(0, 5).map(c =>
            `<span class="fta-country-chip">${c}</span>`
          ).join('')}
          ${m.countries.length > 5 ? `<span class="fta-country-chip">+${m.countries.length - 5} more</span>` : ''}
        </div>
        <div style="font-size:11px;color:var(--muted-soft)">
          <i class="ti ti-rule" style="font-size:11px"></i> RoO: ${m.roo.split(' or ')[0]}…
        </div>
      </div>
      <div class="fta-card-footer">
        ${used > 0
          ? `<i class="ti ti-check-circle" style="font-size:13px;color:var(--teal)"></i>
             <span>Used in <strong>${used}</strong> shipment${used > 1 ? 's' : ''}</span>`
          : `<i class="ti ti-circle" style="font-size:13px"></i>
             <span>${chap > 0 ? `${chap} HS chapters covered` : 'No active shipments'}</span>`}
        <span style="margin-left:auto;font-size:11px;color:var(--muted-soft)">
          <i class="ti ti-chevron-down" style="font-size:11px"></i>
        </span>
      </div>
      <div class="fta-expand-body" id="expand_${key}">
        <div style="padding:16px 16px 14px">
          <p style="font-size:12.5px;color:var(--body);margin-bottom:12px;line-height:1.6">${m.desc}</p>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">
            <div style="font-size:11.5px">
              <span style="color:var(--muted-soft);font-size:10.5px;text-transform:uppercase;letter-spacing:.8px;display:block;margin-bottom:3px">Rules of Origin</span>
              <span style="color:var(--ink);font-weight:500">${m.roo}</span>
            </div>
            <div style="font-size:11.5px">
              <span style="color:var(--muted-soft);font-size:10.5px;text-transform:uppercase;letter-spacing:.8px;display:block;margin-bottom:3px">Partner Countries</span>
              <span style="color:var(--ink);font-weight:500">${m.countries.length} countr${m.countries.length > 1 ? 'ies' : 'y'}</span>
            </div>
          </div>
          <div style="display:flex;gap:8px">
            <button class="btn" style="font-size:12px;height:30px"
              onclick="event.stopPropagation();prefillSearch('${key}')">
              <i class="ti ti-zoom-money" style="font-size:12px"></i> Search Rates
            </button>
            ${used > 0
              ? `<button class="btn" style="font-size:12px;height:30px;color:var(--teal)"
                   onclick="event.stopPropagation();location='shipments.html'">
                   <i class="ti ti-arrow-right" style="font-size:12px"></i> See Shipments
                 </button>`
              : ''}
          </div>
        </div>
      </div>
    </div>`
  }).join(''))
}

/* ── Expand a card ───────────────────────────────────────────── */
function toggleFTA(key) {
  const el = $('expand_' + key)
  if (!el) return
  const isOpen = el.classList.contains('open')
  // Close all others
  document.querySelectorAll('.fta-expand-body.open').forEach(e => e.classList.remove('open'))
  if (!isOpen) el.classList.add('open')
}

/* ── HS Rate search ──────────────────────────────────────────── */
async function searchRates() {
  const raw = ($('hsInput')?.value || '').trim()
  if (!raw) { showToast('Enter an HS code first', true); return }

  setText('searchedCode', raw)
  $('searchResults').style.display = ''
  setHtml('rateBody', `
    <div style="padding:20px;text-align:center;color:var(--muted-soft);font-size:12px">
      <i class="ti ti-loader-2 spin" style="font-size:20px;display:block;margin-bottom:6px"></i>
      Searching fta_rates table for HS ${raw}…
    </div>`)

  try {
    const r = await fetchFTARates(raw)
    const rows = r.data || []
    setText('rateCount', `${rows.length} rate${rows.length !== 1 ? 's' : ''} found`)

    if (!rows.length) {
      setHtml('rateBody', `
        <div style="padding:24px;text-align:center;color:var(--muted-soft);font-size:12.5px">
          <i class="ti ti-search-off" style="font-size:28px;display:block;margin-bottom:8px;color:var(--hairline)"></i>
          No preferential rates found for <strong style="font-family:var(--mono);color:var(--ink)">${raw}</strong><br>
          <span style="font-size:11.5px">This HS code may not be in the scraped JKDM rate database yet,
          or may only be subject to MFN tariff (typically 5%).</span>
        </div>`)
      return
    }

    setHtml('rateBody', rows.map(row => {
      const r   = row.preferential_rate_pct ?? 0
      const mfn = 5 // standard Malaysian MFN
      const color = r < mfn ? 'var(--teal)' : r === 0 ? 'var(--teal)' : 'var(--amber)'
      const save  = r < mfn ? `Save ${mfn - r}%` : r === mfn ? 'Same as MFN' : 'Higher'
      const saveColor = r < mfn ? 'var(--teal)' : 'var(--muted-soft)'

      // ── Rate staging timeline visual ──────────────────────────
      let stagingHtml = ''
      const staging = row.rate_staging
      if (staging && typeof staging === 'object') {
        const currentYear = new Date().getFullYear()
        const nextYear    = currentYear + 1
        const curRate     = staging[String(currentYear)]
        const nxtRate     = staging[String(nextYear)]
        const cat         = row.staging_category ? `[${row.staging_category}] ` : ''

        if (curRate !== undefined || nxtRate !== undefined) {
          const parts = []
          if (curRate !== undefined)
            parts.push(`${currentYear}: <strong>${curRate}%</strong>`)
          if (nxtRate !== undefined) {
            const arrow = nxtRate < (curRate ?? r) ? ' ↓' : ''
            parts.push(
              `${nextYear}: <strong style="color:var(--teal)">${nxtRate}%${arrow}</strong>`
            )
          }
          if (row.final_year && row.final_rate === 0 && row.final_year > nextYear)
            parts.push(`→ 0% by ${row.final_year}`)

          const updatesNote = (nxtRate !== undefined && nxtRate < (curRate ?? r))
            ? '<span style="color:var(--teal);font-size:10px"> ← updates Jan 1</span>'
            : ''

          stagingHtml = `
            <div style="margin-top:4px;font-size:10.5px;color:var(--muted-soft);font-family:var(--mono);line-height:1.4">
              ${cat}${parts.join(' → ')}${updatesNote}
            </div>`
        }
      }

      return `
      <div class="rate-result-row fade-in">
        <span>
          <span style="font-family:var(--mono);font-weight:600;font-size:12px;color:${FTA_META[row.fta_name]?.color || 'var(--primary)'}">${row.fta_name}</span>
        </span>
        <span style="font-family:var(--mono);font-size:12px;color:var(--ink)">${row.hs_code}</span>
        <span style="font-size:12px;color:var(--muted)">${row.origin_country}</span>
        <span>
          <span style="font-family:var(--mono);font-size:13px;font-weight:600;color:${color}">${r}%</span>
          ${stagingHtml}
        </span>
        <span>
          <span style="font-size:11.5px;color:${saveColor};font-weight:500">${save}</span>
          ${r < mfn
            ? `<div style="margin-top:3px;height:5px;width:${Math.min(100,Math.round((1-r/mfn)*100))}%;background:var(--teal);border-radius:var(--r-pill);max-width:120px"></div>`
            : ''}
        </span>
      </div>`
    }).join(''))

    $('searchResults').scrollIntoView({ behavior: 'smooth', block: 'start' })
    showToast(`✓ ${rows.length} rates found for HS ${raw}`)
  } catch (e) {
    const isOffline = e.message.toLowerCase().includes('fetch') || e.message.includes('NetworkError')
    showToast(isOffline ? '⚠ Backend offline — restart uvicorn to load new routes' : 'Search failed: ' + e.message, true)
    setHtml('rateBody', `
      <div style="padding:24px;text-align:center;color:var(--muted-soft);font-size:12.5px">
        <i class="ti ti-plug-off" style="font-size:28px;display:block;margin-bottom:8px;color:var(--hairline)"></i>
        ${isOffline
          ? `<strong style="color:var(--ink)">Backend offline or new routes not loaded</strong><br>
             Restart the backend: <code style="font-size:11px">uvicorn main:app --reload</code><br>
             The <code>/api/fta-rates</code> route was added in this session.`
          : `Error: ${e.message}`}
      </div>`)
  }
}

function clearSearch() {
  const inp = $('hsInput')
  if (inp) inp.value = ''
  $('searchResults').style.display = 'none'
}

function prefillSearch(ftaKey) {
  // Scroll to search bar and focus
  const inp = $('hsInput')
  if (inp) { inp.focus(); inp.placeholder = `Search rates for ${ftaKey}…` }
  document.querySelector('.hs-search-wrap')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  showToast(`Enter an HS code to see ${ftaKey} rates`)
}
