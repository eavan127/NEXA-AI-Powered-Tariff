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
    'Average savings per shipment',
  ]

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

    /* ── Demo / incident-simulation controls ──────────────────── */
    #nexaDemoBtn {
      position: fixed; bottom: 24px; left: 96px; z-index: 500;
      width: 48px; height: 48px; border-radius: 50%;
      background: var(--surface-dark); color: var(--amber); border: 2px solid var(--amber);
      display: flex; align-items: center; justify-content: center;
      font-size: 20px; cursor: pointer;
      box-shadow: 0 8px 24px rgba(0,43,73,.22);
      transition: transform .15s;
    }
    #nexaDemoBtn:hover { transform: translateY(-2px); }
    #nexaDemoBtn.degraded { color: #fff; background: var(--error); border-color: var(--error); animation: nexaPulse 1.4s ease-in-out infinite; }
    @keyframes nexaPulse { 0%,100% { box-shadow: 0 0 0 0 rgba(198,69,69,.45); } 50% { box-shadow: 0 0 0 8px rgba(198,69,69,0); } }
    #nexaDemoPanel {
      position: fixed; bottom: 84px; left: 96px; z-index: 500;
      width: 300px; background: var(--canvas); border: 1px solid var(--hairline);
      border-radius: var(--r-lg); box-shadow: 0 16px 48px rgba(0,43,73,.2);
      display: none; overflow: hidden; font-family: var(--sans);
    }
    #nexaDemoPanel.open { display: block; }
    #nexaDemoPanel .nexa-demo-head {
      padding: 12px 14px; background: var(--surface-dark); color: #fff;
      font-size: 12.5px; font-weight: 600; display: flex; align-items: center; gap: 6px;
    }
    #nexaDemoPanel .nexa-demo-body { padding: 12px; display: flex; flex-direction: column; gap: 8px; }
    .nexa-demo-btn {
      display: flex; align-items: center; gap: 8px; width: 100%;
      padding: 9px 11px; border-radius: var(--r-md); border: 1px solid var(--hairline);
      background: var(--surface-soft); color: var(--ink); font-size: 12.5px; font-weight: 500;
      cursor: pointer; text-align: left;
    }
    .nexa-demo-btn:hover { background: var(--surface-card); }
    .nexa-demo-btn.danger { color: var(--error); }
    .nexa-demo-btn.resolve { color: var(--teal); border-color: rgba(0,145,107,.3); }
    .nexa-demo-status { font-size: 11px; color: var(--muted); padding: 0 2px; line-height: 1.5; }
    `
    const tag = document.createElement('style')
    tag.textContent = css
    document.head.appendChild(tag)
  }

  function buildDom() {
    const btn = document.createElement('button')
    btn.id = 'nexaChatBtn'
    btn.title = 'Ask NEXA Assistant'
    btn.innerHTML = '<i class="ti ti-message-chatbot"></i><span class="nexa-badge"></span>'

    const panel = document.createElement('div')
    panel.id = 'nexaChatPanel'
    panel.innerHTML = `
      <div id="nexaChatHead">
        <i class="ti ti-robot"></i>
        <div class="nexa-title"><b>NEXA Assistant</b><span>Savings &amp; landed cost analytics</span></div>
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

  function buildDemoDom() {
    const btn = document.createElement('button')
    btn.id = 'nexaDemoBtn'
    btn.title = 'Incident simulation (demo)'
    btn.innerHTML = '<i class="ti ti-alert-triangle"></i>'

    const panel = document.createElement('div')
    panel.id = 'nexaDemoPanel'
    panel.innerHTML = `
      <div class="nexa-demo-head"><i class="ti ti-flask"></i> Incident Simulator (Demo)</div>
      <div class="nexa-demo-body">
        <div class="nexa-demo-status" id="nexaDemoStatus">Checking system status…</div>
        <button class="nexa-demo-btn danger" data-action="feed-down">
          <i class="ti ti-wifi-off"></i> Simulate Regulatory Feed Outage
        </button>
        <button class="nexa-demo-btn danger" data-action="prompt-injection">
          <i class="ti ti-shield-x"></i> Simulate Prompt Injection
        </button>
        <button class="nexa-demo-btn resolve" data-action="resolve">
          <i class="ti ti-check"></i> Resolve Incident
        </button>
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

  function initDemoControls() {
    const { btn, panel } = buildDemoDom()
    const statusEl = panel.querySelector('#nexaDemoStatus')

    async function refreshStatus() {
      try {
        const res = await fetch(`${API_BASE}/api/admin/system-status`)
        const data = await res.json()
        btn.classList.toggle('degraded', !!data.degraded)
        statusEl.innerHTML = data.degraded
          ? `<strong style="color:var(--error)">⚠ Degraded mode active</strong> — ${data.active_alerts?.length || 0} alert(s), SAP write-back frozen.`
          : '<span style="color:var(--teal)">✓ All systems nominal</span>'
      } catch {
        statusEl.textContent = "Can't reach backend."
      }
    }

    btn.addEventListener('click', () => { panel.classList.toggle('open'); if (panel.classList.contains('open')) refreshStatus() })

    panel.querySelectorAll('.nexa-demo-btn').forEach(b => {
      b.addEventListener('click', async () => {
        const action = b.dataset.action
        const url = action === 'resolve'
          ? `${API_BASE}/api/admin/resolve-incident`
          : `${API_BASE}/api/admin/simulate-incident/${action}`
        const opts = action === 'resolve'
          ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resolved_by: 'Compliance Manager', note: 'Resolved via demo control' }) }
          : { method: 'POST' }
        try {
          const res = await fetch(url, opts)
          const data = await res.json()
          if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
          toast(data.message || 'Done')
          refreshStatus()
        } catch (e) {
          toast(`Incident simulator failed: ${e.message}`, true)
        }
      })
    })

    refreshStatus()
    setInterval(refreshStatus, 15000)
  }

  function renderChart(chart) {
    if (!chart || !chart.labels || !chart.labels.length) return ''
    const max = Math.max(...chart.values, 1)
    const rows = chart.labels.map((lbl, i) => {
      const v = chart.values[i] || 0
      const w = Math.max(Math.round(v / max * 100), v > 0 ? 4 : 0)
      return `
      <div class="bar-chart-row" style="margin-bottom:6px">
        <span class="bar-lbl" style="width:54px;font-size:11px">${lbl}</span>
        <div class="bar-track" style="height:14px">
          <div class="bar-fill" style="width:${w}%;background:var(--primary)"></div>
        </div>
        <span class="bar-val" style="font-size:11px;min-width:60px">${money(v)}</span>
      </div>`
    }).join('')
    return `<div style="margin-top:10px">${rows}</div>`
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

  function appendMsg(body, role, html) {
    const div = document.createElement('div')
    div.className = 'nexa-msg ' + role
    div.innerHTML = html
    body.appendChild(div)
    body.scrollTop = body.scrollHeight
  }

  function init() {
    injectStyles()
    const { btn, panel } = buildDom()
    const body  = panel.querySelector('#nexaChatBody')
    const input = panel.querySelector('#nexaChatInput')
    const send  = panel.querySelector('#nexaChatSend')

    appendMsg(body, 'bot',
      "Hi, I'm the NEXA Assistant. Ask me about FTA duty savings or landed cost — " +
      "e.g. \"what's our savings today\" or \"show cost this month\".")

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
          body: JSON.stringify({ message: msg }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
        appendMsg(body, 'bot', (data.reply || 'No response.') + renderChart(data.chart) + renderStats(data.stats))
      } catch (e) {
        appendMsg(body, 'bot', `<span style="color:var(--error)">Couldn't reach NEXA backend: ${e.message}</span>`)
      } finally {
        send.disabled = false
      }
    }

    send.addEventListener('click', sendMessage)
    input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage() })

    initDemoControls()
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
  } else {
    init()
  }
})()
