/**
 * api.js — all HTTP calls for NEXA AI Tariff Intelligence
 * Loaded on every page. Depends on nothing.
 */
const API = 'http://localhost:8000'

/* ── Base fetch helper ────────────────────────────────────────── */
async function apiFetch(path, method = 'GET', body = null) {
  const opts = { method }
  if (body) {
    opts.headers = { 'Content-Type': 'application/json' }
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(API + path, opts)
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(e.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/* ── Shipments ────────────────────────────────────────────────── */
async function fetchShipments(status = 'all') {
  const res = await apiFetch(`/api/shipments?status=${status}`)
  return res.data || []
}
async function fetchShipmentDetail(sapId) {
  return apiFetch(`/api/shipments/${sapId}`)
}

/* ── Summary (KPIs) ───────────────────────────────────────────── */
async function fetchSummary() {
  const res = await fetch(`${API}/api/reports/summary`)
  return res.json()
}

/* ── Module A — HS Classification ────────────────────────────── */
async function runModuleA(shipmentId) {
  return apiFetch(`/api/classify/${shipmentId}`, 'POST')
}

/* ── Module B — FTA Matching ──────────────────────────────────── */
async function runModuleB(shipmentId) {
  return apiFetch(`/api/match-fta/${shipmentId}`, 'POST')
}

/* ── Module C — Landed Cost ───────────────────────────────────── */
async function runModuleC(shipmentId) {
  return apiFetch(`/api/calculate-landed-cost/${shipmentId}`, 'POST')
}

 /* ── Module D — SAP Writeback ──────────────────────────────── */
  async function submitShipmentToSAP(shipmentId) {
    return apiFetch(`/api/shipments/${shipmentId}/submit-sap`, 'POST')
  }
  async function submitBatchToSAP(shipmentIds = []) {
    return apiFetch('/api/submit-batch', 'POST', { shipment_ids: shipmentIds })
  }

/* ── Approve / Flag ───────────────────────────────────────────── */
async function approveShipment(shipmentId) {
  return apiFetch(`/api/shipments/${shipmentId}/approve`, 'POST')
}
async function flagShipment(shipmentId) {
  return apiFetch(`/api/shipments/${shipmentId}/flag`, 'POST')
}

/* ── Human Validation ─────────────────────────────────────────── */
async function overrideHSCode(shipmentId, hsCode, reason) {
  return apiFetch(`/api/shipments/${shipmentId}/override-hs`, 'POST', { hs_code: hsCode, reason })
}
async function escalateShipment(shipmentId, assignee, notes) {
  return apiFetch(`/api/shipments/${shipmentId}/escalate`, 'POST', { assignee, notes })
}

/* ── FTA Library ──────────────────────────────────────────────── */
async function fetchFTACoverage() {
  return apiFetch('/api/fta-coverage')
}
async function fetchFTARates(hsCode = null, ftaName = null) {
  const p = new URLSearchParams()
  if (hsCode)  p.set('hs_code',  hsCode)
  if (ftaName) p.set('fta_name', ftaName)
  const qs = p.toString() ? '?' + p.toString() : ''
  return apiFetch('/api/fta-rates' + qs)
}

/* ── Audit Trail ──────────────────────────────────────────────── */
async function fetchAuditTrail() {
  return apiFetch('/api/audit-trail')
}

/* ── PDF Upload ───────────────────────────────────────────────── */
async function uploadShipmentPDF(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API}/api/upload-shipment-pdf`, { method: 'POST', body: form })
  return res.json()
}

/* ── Seed ─────────────────────────────────────────────────────── */
async function runSeed() {
  const res = await fetch(`${API}/api/seed`, { method: 'POST' })
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(e.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

/* ── SAP Submission ───────────────────────────────────────────── */
async function submitBatchToSAP(shipmentIds = []) {
  return apiFetch('/api/submit-batch', 'POST', { shipment_ids: shipmentIds })
}

