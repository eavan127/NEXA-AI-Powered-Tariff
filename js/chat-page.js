/**
 * chat-page.js — full-page "AI Assistant" tab (chat.html). Same backend
 * contract as the floating popup (js/chatbox.js) — POST /api/chatbot/query,
 * GET /api/chatbot/history — but renders into the page's own #chatStream
 * instead of injecting a floating panel. No stay/redirect prompt here:
 * this *is* the destination the popup redirects to, and it shares the
 * same chat_history record (keyed by role) so reopening either surface
 * shows the same conversation.
 */
;(function () {
  const API_BASE = (typeof API !== 'undefined' && API) ? API : 'http://localhost:8000'

  const QUICK_PROMPTS = [
    "What's our savings today?",
    'Show landed cost this month',
    'Predict next week’s savings',
    'Generate this month’s report',
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

  function renderChart(chartImage) {
    if (!chartImage) return ''
    const filename = `nexa-chart-${Date.now()}.png`
    return `
      <a href="${chartImage}" download="${filename}" title="Click to download chart" style="display:block;margin-top:12px;max-width:640px">
        <img src="${chartImage}" alt="Chart" style="display:block;width:100%;border-radius:var(--r-md);border:1px solid var(--hairline)">
      </a>
      <div style="font-size:11px;color:var(--muted-soft);margin-top:4px"><i class="ti ti-download"></i> Click chart to download PNG</div>`
  }

  function renderStats(stats) {
    if (!stats || stats.count == null) return ''
    return `
      <div class="chat-stats">
        <span>Mean <b>${money(stats.mean)}</b></span>
        <span>Median <b>${money(stats.median)}</b></span>
        <span>Mode <b>${stats.mode != null ? money(stats.mode) : 'n/a'}</b></span>
      </div>`
  }

  function renderCitations(citations, sourcesLabel) {
    if (!citations || !citations.length) return ''
    return `<div class="chat-citations"><b>${sourcesLabel || 'Sources'}</b>${citations.map(c => `<div>• ${c}</div>`).join('')}</div>`
  }

  function renderReportLink(data) {
    if (!data.report_available) return ''
    const url = `${API_BASE}/api/reports/monthly-pdf?period=${encodeURIComponent(data.report_period || 'month')}`
    return `<a class="chat-report-link" href="${url}" download="nexa-monthly-report.pdf"><i class="ti ti-file-download"></i> Download PDF Report</a>`
  }

  // A floating "open chat" button would be redundant on the page that
  // *is* the chat, so this slot is repurposed as system status / the
  // incident-simulator (same backend endpoints chatbox.js's demo controls
  // use on every other page) — robot icon instead of the chat-bubble icon
  // used elsewhere, so it reads as a different control, not a duplicate.

  function appendMsg(stream, sender, html) {
    const div = document.createElement('div')
    div.className = 'chat-msg ' + sender
    div.innerHTML = html
    stream.appendChild(div)
    stream.scrollTop = stream.scrollHeight
  }

  async function loadHistory(stream, role) {
    stream.innerHTML = ''
    try {
      const res = await fetch(`${API_BASE}/api/chatbot/history?role=${role}`)
      const data = await res.json()
      const history = data.history || []
      if (!history.length) {
        appendMsg(stream, 'bot',
          "Hi, I'm the NEXA Assistant. Ask me about FTA duty savings, landed cost, a savings forecast, " +
          "or say \"generate monthly report\" for a downloadable PDF. Answers are framed for your selected " +
          "role and cite their sources below.")
        return
      }
      history.forEach(m => appendMsg(stream, m.role === 'human' ? 'user' : 'bot', m.content.replace(/\n/g, '<br>')))
    } catch {
      appendMsg(stream, 'bot', "Hi, I'm the NEXA Assistant. Ask me about FTA duty savings, landed cost, or a forecast.")
    }
  }

  function init() {
    const stream = document.getElementById('chatStream')
    const quick  = document.getElementById('chatQuick')
    const form   = document.getElementById('chatForm')
    const input  = document.getElementById('chatInput')
    const send   = document.getElementById('chatSend')
    const roleEl = document.getElementById('chatRole')
    if (!stream || !form) return

    quick.innerHTML = QUICK_PROMPTS.map(p => `<span class="chat-chip" data-prompt="${p}">${p}</span>`).join('')
    quick.querySelectorAll('.chat-chip').forEach(chip =>
      chip.addEventListener('click', () => { input.value = chip.dataset.prompt; form.requestSubmit() })
    )

    const roleBtns = roleEl ? roleEl.querySelectorAll('.chat-role-btn') : []
    function refreshRoleUI() {
      const role = getRole()
      roleBtns.forEach(b => b.classList.toggle('active', b.dataset.role === role))
    }
    roleBtns.forEach(b => b.addEventListener('click', () => {
      setRole(b.dataset.role)
      refreshRoleUI()
      loadHistory(stream, b.dataset.role)
    }))
    refreshRoleUI()

    loadHistory(stream, getRole())

    form.addEventListener('submit', async (e) => {
      e.preventDefault()
      const msg = input.value.trim()
      if (!msg) return
      appendMsg(stream, 'user', msg)
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
        appendMsg(stream, 'bot',
          (data.reply || 'No response.').replace(/\n/g, '<br>') +
          renderChart(data.chart_image) + renderStats(data.stats) +
          renderReportLink(data) + renderCitations(data.citations, data.sources_label))
      } catch (err) {
        appendMsg(stream, 'bot', `<span style="color:var(--error)">Couldn't reach NEXA backend: ${err.message}</span>`)
      } finally {
        send.disabled = false
      }
    })
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
  } else {
    init()
  }
})()
