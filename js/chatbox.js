/**
 * chatbox.js — NEXA AI Assistant floating chatbox (bottom-left).
 * Self-contained: injects its own DOM + styles, talks to
 * POST /api/chatbot/query (pandas/numpy savings & cost analytics on the backend).
 * Include on every page, after css/styles.css is loaded.
 */
;(function () {
  const API_BASE = (typeof API !== 'undefined' && API) ? API : 'http://localhost:8000'

  const QUICK_PROMPTS = [
    "What's our savings today?",
    'Show landed cost this month',
    'Predict next week’s savings',
  ]

  function getRole() {
    return localStorage.getItem('nexaRole') === 'manager' ? 'manager' : 'analyst'
  }
  function setRole(role) {
    localStorage.setItem('nexaRole', role)
  }

  function money(n) {
    return '$' + (+n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  function injectStyles() {
    const css = `
    #nexaChatBtn {
      position: fixed; bottom: 24px; left: 24px; z-index: 500;
      width: 64px; height: 64px; border-radius: 50%;
      background: var(--primary); color: #fff; border: none;
      display: flex; align-items: center; justify-content: center;
      font-size: 30px; cursor: pointer;
      box-shadow: 0 8px 24px rgba(0,43,73,.28), 0 2px 8px rgba(0,43,73,.18);
      transition: transform .15s, background .15s;
    }
    #nexaChatBtn:hover { background: var(--primary-active); transform: translateY(-2px); }
    #nexaChatBtn .nexa-badge {
      position: absolute; top: -4px; right: -4px;
      width: 14px; height: 14px; border-radius: 50%;
      background: var(--teal); border: 2px solid #fff;
    }
    #nexaChatPanel {
      position: fixed; bottom: 100px; left: 24px; z-index: 500;
      width: 380px; max-width: 92vw; height: 520px; max-height: 75vh;
      background: var(--canvas); border: 1px solid var(--hairline);
      border-radius: var(--r-xl); box-shadow: 0 20px 60px rgba(0,43,73,.22);
      display: none; flex-direction: column; overflow: hidden;
      font-family: var(--sans);
    }
    #nexaChatPanel.open { display: flex; }
    #nexaChatHead {
      background: var(--surface-dark); color: #fff;
      padding: 16px 18px; display: flex; align-items: center; gap: 10px;
    }
    #nexaChatHead .ti { font-size: 20px; color: var(--teal); }
    #nexaChatHead .nexa-title { flex: 1; }
    #nexaChatHead .nexa-title b { display: block; font-size: 15px; font-weight: 600; }
    #nexaChatHead .nexa-title span { display: block; font-size: 11.5px; color: var(--on-dark-soft); margin-top: 1px; }
    #nexaChatHead button { background: none; border: none; color: var(--on-dark-soft); font-size: 18px; cursor: pointer; }
    #nexaChatHead button:hover { color: #fff; }
    #nexaChatBody {
      flex: 1; overflow-y: auto; padding: 16px 16px 8px;
      display: flex; flex-direction: column; gap: 12px;
      background: var(--surface-soft);
    }
    .nexa-msg { max-width: 86%; font-size: 13.5px; line-height: 1.5; padding: 10px 13px; border-radius: var(--r-lg); }
    .nexa-msg.bot  { align-self: flex-start; background: var(--canvas); border: 1px solid var(--hairline); color: var(--body); }
    .nexa-msg.user { align-self: flex-end; background: var(--primary); color: #fff; }
    .nexa-stats { font-size: 11.5px; color: var(--muted); margin-top: 8px; display: flex; gap: 10px; flex-wrap: wrap; }
    .nexa-stats b { color: var(--ink); }
    .nexa-chip-row { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 12px; background: var(--surface-soft); }
    .nexa-chip {
      font-size: 11.5px; padding: 5px 10px; border-radius: var(--r-pill);
      border: 1px solid var(--hairline); background: var(--canvas); color: var(--primary);
      cursor: pointer; white-space: nowrap;
    }
    .nexa-chip:hover { background: var(--surface-card); }
    #nexaChatInputRow { display: flex; gap: 8px; padding: 12px; border-top: 1px solid var(--hairline); background: var(--canvas); }
    #nexaChatInput {
      flex: 1; height: 38px; padding: 0 12px; border: 1px solid var(--hairline);
      border-radius: var(--r-md); font-size: 13.5px; outline: none; color: var(--ink);
    }
    #nexaChatInput:focus { border-color: var(--primary); }
    #nexaChatSend {
      width: 38px; height: 38px; border-radius: var(--r-md); border: none;
      background: var(--primary); color: #fff; cursor: pointer; display: flex;
      align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0;
    }
    #nexaChatSend:hover { background: var(--primary-active); }
    #nexaChatSend:disabled { opacity: .5; cursor: default; }
    #nexaRoleToggle { display: flex; gap: 2px; background: rgba(255,255,255,.12); border-radius: var(--r-pill); padding: 2px; margin-right: 4px; }
    .nexa-role-btn { border: none; background: none; color: var(--on-dark-soft); font-size: 10.5px; font-weight: 600; padding: 4px 9px; border-radius: var(--r-pill); cursor: pointer; }
    .nexa-role-btn.active { background: var(--teal); color: #fff; }
    .nexa-citations { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--hairline); font-size: 10.5px; color: var(--muted); line-height: 1.6; }
    .nexa-citations b { color: var(--ink); display: block; margin-bottom: 2px; }
    .nexa-redirect-row { display: flex; gap: 8px; margin-top: 10px; }
    .nexa-redirect-btn {
      flex: 1; border: 1px solid var(--hairline); background: var(--canvas); color: var(--primary);
      font-size: 12px; font-weight: 600; padding: 8px 10px; border-radius: var(--r-md); cursor: pointer;
    }
    .nexa-redirect-btn:hover { background: var(--surface-card); }
    .nexa-redirect-btn.primary { background: var(--primary); color: #fff; border-color: var(--primary); }
    .nexa-redirect-btn.primary:hover { background: var(--primary-active); }
    .nexa-report-link {
      display: flex; align-items: center; gap: 6px; margin-top: 10px; padding: 8px 12px;
      background: var(--teal); color: #fff; border-radius: var(--r-md); text-decoration: none;
      font-size: 12.5px; font-weight: 600; width: fit-content;
    }

    `
    const tag = document.createElement('style')
    tag.textContent = css
    document.head.appendChild(tag)
  }

  function buildDom() {
    const btn = document.createElement('button')
    btn.id = 'nexaChatBtn'
    btn.title = 'Ask NEXA Assistant'
    btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="36" height="36" fill="white">
      <!-- antenna -->
      <line x1="50" y1="10" x2="50" y2="22" stroke="white" stroke-width="4" stroke-linecap="round"/>
      <circle cx="50" cy="7" r="5"/>
      <!-- head -->
      <rect x="22" y="22" width="56" height="42" rx="20" ry="20"/>
      <!-- eyes -->
      <circle cx="37" cy="40" r="6" fill="#003d6b"/>
      <circle cx="63" cy="40" r="6" fill="#003d6b"/>
      <!-- smile -->
      <path d="M38 52 Q50 62 62 52" stroke="#003d6b" stroke-width="3.5" fill="none" stroke-linecap="round"/>
      <!-- left ear/headphone -->
      <rect x="10" y="30" width="14" height="20" rx="7" ry="7"/>
      <!-- right ear/headphone -->
      <rect x="76" y="30" width="14" height="20" rx="7" ry="7"/>
      <!-- headband -->
      <path d="M17 35 Q17 14 50 14 Q83 14 83 35" stroke="white" stroke-width="5" fill="none" stroke-linecap="round"/>
      <!-- mic arm -->
      <path d="M24 50 Q14 60 18 72" stroke="white" stroke-width="3.5" fill="none" stroke-linecap="round"/>
      <circle cx="18" cy="75" r="5"/>
    </svg><span class="nexa-badge"></span>`

    const panel = document.createElement('div')
    panel.id = 'nexaChatPanel'
    panel.innerHTML = `
      <div id="nexaChatHead">
        <i class="ti ti-robot"></i>
        <div class="nexa-title"><b>NEXA Assistant</b><span>Savings &amp; landed cost analytics</span></div>
        <div id="nexaRoleToggle">
          <button class="nexa-role-btn" data-role="analyst">Analyst</button>
          <button class="nexa-role-btn" data-role="manager">Manager</button>
        </div>
        <button id="nexaChatClose" title="Close"><i class="ti ti-x"></i></button>
      </div>
      <div id="nexaChatBody"></div>
      <div class="nexa-chip-row">
        ${QUICK_PROMPTS.map(p => `<span class="nexa-chip" data-prompt="${p}">${p}</span>`).join('')}
      </div>
      <div id="nexaChatInputRow">
        <input id="nexaChatInput" type="text" placeholder="Ask about savings or cost…" autocomplete="off">
        <button id="nexaChatSend" title="Send"><i class="ti ti-send"></i></button>
      </div>
    `
    document.body.appendChild(btn)
    document.body.appendChild(panel)
    return { btn, panel }
  }

  function toast(msg, isError) {
    if (typeof showToast === 'function') { showToast(msg, isError); return }
    if (isError) console.error(msg); else console.log(msg)
  }

  function renderChart(chartImage) {
    if (!chartImage) return ''
    const filename = `nexa-chart-${Date.now()}.png`
    return `
      <a href="${chartImage}" download="${filename}" title="Click to download chart" style="display:block;margin-top:10px">
        <img src="${chartImage}" alt="Chart" style="display:block;width:100%;border-radius:var(--r-md);border:1px solid var(--hairline)">
      </a>
      <div style="font-size:10px;color:var(--muted-soft);margin-top:3px"><i class="ti ti-download"></i> Click chart to download PNG</div>`
  }

  function renderStats(stats) {
    if (!stats || !stats.count) return ''
    return `
      <div class="nexa-stats">
        <span>Mean <b>${money(stats.mean)}</b></span>
        <span>Median <b>${money(stats.median)}</b></span>
        <span>Mode <b>${stats.mode != null ? money(stats.mode) : 'n/a'}</b></span>
      </div>`
  }

  function appendMsg(body, sender, html) {
    const div = document.createElement('div')
    div.className = 'nexa-msg ' + sender
    div.innerHTML = html
    body.appendChild(div)
    body.scrollTop = body.scrollHeight
  }

  function renderCitations(citations, sourcesLabel) {
    if (!citations || !citations.length) return ''
    return `<div class="nexa-citations"><b>${sourcesLabel || 'Sources'}</b>${citations.map(c => `<div>• ${c}</div>`).join('')}</div>`
  }

  function renderReportLink(data) {
    if (!data.report_available) return ''
    const url = `${API_BASE}/api/reports/monthly-pdf?period=${encodeURIComponent(data.report_period || 'month')}`
    return `<a class="nexa-report-link" href="${url}" download="nexa-monthly-report.pdf"><i class="ti ti-file-download"></i> Download PDF Report</a>`
  }

  function renderAnswer(data) {
    return (data.reply || 'No response.').replace(/\n/g, '<br>') +
      renderChart(data.chart_image) + renderStats(data.stats) + renderCitations(data.citations, data.sources_label)
  }

  function appendChoice(body, data) {
    const div = document.createElement('div')
    div.className = 'nexa-msg bot'
    div.innerHTML = `
      <div>Got an answer ready — view it here, or open the full AI Assistant for a bigger view (charts render larger there)?</div>
      ${renderReportLink(data)}
      <div class="nexa-redirect-row">
        <button class="nexa-redirect-btn" data-choice="stay">Stay here</button>
        <button class="nexa-redirect-btn primary" data-choice="open">Open AI Assistant</button>
      </div>
    `
    body.appendChild(div)
    body.scrollTop = body.scrollHeight

    div.querySelector('[data-choice="stay"]').addEventListener('click', () => {
      div.remove()
      appendMsg(body, 'bot', renderAnswer(data))
    })
    div.querySelector('[data-choice="open"]').addEventListener('click', () => {
      window.location.href = 'chat.html'
    })
  }

  async function loadHistory(body, role) {
    body.innerHTML = ''
    try {
      const res = await fetch(`${API_BASE}/api/chatbot/history?role=${role}`)
      const data = await res.json()
      const history = data.history || []
      if (!history.length) {
        appendMsg(body, 'bot',
          "Hi, I'm the NEXA Assistant. Ask me about FTA duty savings, landed cost, or a savings " +
          "forecast — e.g. \"what's our savings today\" or \"predict next week's savings\". " +
          "Answers are framed for your selected role and cite their sources below.")
        return
      }
      history.forEach(m => appendMsg(body, m.role === 'human' ? 'user' : 'bot', m.content.replace(/\n/g, '<br>')))
    } catch {
      appendMsg(body, 'bot', "Hi, I'm the NEXA Assistant. Ask me about FTA duty savings, landed cost, or a forecast.")
    }
  }

  function init() {
    injectStyles()
    const { btn, panel } = buildDom()
    const body  = panel.querySelector('#nexaChatBody')
    const input = panel.querySelector('#nexaChatInput')
    const send  = panel.querySelector('#nexaChatSend')

    loadHistory(body, getRole())

    const roleBtns = panel.querySelectorAll('.nexa-role-btn')
    function refreshRoleUI() {
      const role = getRole()
      roleBtns.forEach(b => b.classList.toggle('active', b.dataset.role === role))
    }
    roleBtns.forEach(b => b.addEventListener('click', () => {
      setRole(b.dataset.role)
      refreshRoleUI()
      loadHistory(body, b.dataset.role)
    }))
    refreshRoleUI()

    btn.addEventListener('click', () => panel.classList.toggle('open'))
    panel.querySelector('#nexaChatClose').addEventListener('click', () => panel.classList.remove('open'))
    panel.querySelectorAll('.nexa-chip').forEach(chip =>
      chip.addEventListener('click', () => { input.value = chip.dataset.prompt; sendMessage() })
    )

    async function sendMessage() {
      const msg = input.value.trim()
      if (!msg) return
      appendMsg(body, 'user', msg)
      input.value = ''
      send.disabled = true

      try {
        const res = await fetch(`${API_BASE}/api/chatbot/query`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg, role: getRole() }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
        appendChoice(body, data)
      } catch (e) {
        appendMsg(body, 'bot', `<span style="color:var(--error)">Couldn't reach NEXA backend: ${e.message}</span>`)
      } finally {
        send.disabled = false
      }
    }

    send.addEventListener('click', sendMessage)
    input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage() })

  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
  } else {
    init()
  }
})()
