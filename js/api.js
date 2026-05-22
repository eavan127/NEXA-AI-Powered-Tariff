const API = 'http://localhost:8000';

// GET /api/shipments
async function fetchShipments(status = 'all') {
  const res = await fetch(`${API}/api/shipments?status=${status}`);
  const json = await res.json();
  return json.data || [];
}

// GET /api/reports/summary
async function fetchSummary() {
  const res = await fetch(`${API}/api/reports/summary`);
  return await res.json();
}

// POST /api/match-fta/:id
async function runFTA(shipmentId) {
  const res = await fetch(`${API}/api/match-fta/${shipmentId}`, {
    method: 'POST'
  });
  return await res.json();
}

// POST /api/upload-shipment-pdf
async function uploadShipmentPDF(file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API}/api/upload-shipment-pdf`, {
    method: 'POST',
    body: form
  });
  return await res.json();
}

// POST /api/seed
async function runSeed() {
  const res = await fetch(`${API}/api/seed`, { method: 'POST' });
  return await res.json();
}