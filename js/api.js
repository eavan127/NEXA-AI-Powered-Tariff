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
  const res  = await fetch(`${API}/api/shipments?status=${status}`)
  const json = await res.json()
  return json.data || []
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

/* ── Approve / Flag ───────────────────────────────────────────── */
async function approveShipment(shipmentId) {
  return apiFetch(`/api/shipments/${shipmentId}/approve`, 'POST')
}
async function flagShipment(shipmentId) {
  return apiFetch(`/api/shipments/${shipmentId}/flag`, 'POST')
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
  return res.json()
}
