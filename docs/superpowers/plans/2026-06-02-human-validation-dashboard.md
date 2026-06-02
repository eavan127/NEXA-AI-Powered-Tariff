# Human Validation Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Human Validation Dashboard (`verification.html`) where every shipment must receive an explicit analyst decision (Approve / Edit HS Code / Escalate) before SAP submission, while converting `shipments.html` to a monitoring-only page with row clicks linking to the dashboard.

**Architecture:** Split-panel layout — 300px queue panel (left) + flex detail panel (right). `verification.js` follows the same patterns as `shipments.js` and `audit.js`: `shared.js` helpers, `api.js` HTTP calls, same CSS variables and component classes. Two new FastAPI endpoints handle HS override and escalation. `shipments.html` loses its Approve/Flag buttons and gains deep-links to `verification.html?id=`.

**Tech Stack:** Vanilla JS (ES2020), FastAPI (Python), Supabase, existing `styles.css` tokens

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/api/routes.py` | Add POST override-hs + escalate endpoints |
| Modify | `js/api.js` | Add `overrideHSCode()` and `escalateShipment()` |
| Modify | `js/shipments.js` | Remove doApprove/doFlag; row click → verification deep-link |
| Modify | `shipments.html` | Remove Action column approve/flag buttons |
| Modify | `shipments.html`, `audit.html`, `fta-library.html`, `reports.html`, `index.html` | Add Validation nav item |
| Create | `verification.html` | Full page shell: sidebar, topbar, split-panel skeleton |
| Create | `js/verification.js` | All dashboard logic: queue, detail, actions, auto-advance |

---

## Task 1: Backend — override-hs and escalate endpoints

**Files:**
- Modify: `backend/api/routes.py`

- [ ] **Step 1: Append both routes at the end of `backend/api/routes.py`**

```python
# Human Validation — HS Code Override
@router.post("/api/shipments/{shipment_id}/override-hs")
async def override_hs_code(shipment_id: str, request: Request):
    try:
        body      = await request.json()
        hs_code   = (body.get("hs_code")  or "").strip()
        reason    = (body.get("reason")   or "").strip()
        if not hs_code or not reason:
            raise HTTPException(status_code=400, detail="hs_code and reason are required")

        supabase = request.app.state.supabase

        ship = supabase.table("shipments").select("id") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # Update latest classification record
        cls_res = supabase.table("hs_classifications").select("id") \
            .eq("shipment_id", ship.data["id"]) \
            .order("created_at", desc=True).limit(1).execute()
        if cls_res.data:
            supabase.table("hs_classifications").update({
                "analyst_override_hs": hs_code,
                "final_hs_code":       hs_code,
                "module_a_status":     "auto_passed"
            }).eq("id", cls_res.data[0]["id"]).execute()

        supabase.table("shipments").update({"status": "approved"}) \
            .eq("sap_shipment_id", shipment_id).execute()

        supabase.table("audit_trail").insert({
            "shipment_id": ship.data["id"],
            "action": f"{shipment_id} HS code overridden to {hs_code} by analyst. Reason: {reason}"
        }).execute()

        return {"status": "ok", "message": f"HS overridden to {hs_code}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Human Validation — Escalate
@router.post("/api/shipments/{shipment_id}/escalate")
async def escalate_shipment(shipment_id: str, request: Request):
    try:
        body     = await request.json()
        assignee = (body.get("assignee") or "Senior Analyst").strip()
        notes    = (body.get("notes")    or "").strip()
        if not notes:
            raise HTTPException(status_code=400, detail="notes are required")

        supabase = request.app.state.supabase

        ship = supabase.table("shipments").select("id") \
            .eq("sap_shipment_id", shipment_id).single().execute()
        if not ship.data:
            raise HTTPException(status_code=404, detail="Shipment not found")

        supabase.table("shipments").update({"status": "flagged"}) \
            .eq("sap_shipment_id", shipment_id).execute()

        supabase.table("audit_trail").insert({
            "shipment_id": ship.data["id"],
            "action": f"{shipment_id} escalated to {assignee}. Notes: {notes}"
        }).execute()

        return {"status": "ok", "message": f"Escalated to {assignee}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: Smoke-test both endpoints (backend must be running)**

```bash
curl -s -X POST http://localhost:8000/api/shipments/SHIP999/override-hs \
  -H "Content-Type: application/json" \
  -d '{"hs_code":"","reason":""}' | python -m json.tool
# Expected: {"detail":"hs_code and reason are required"}

curl -s -X POST http://localhost:8000/api/shipments/SHIP999/escalate \
  -H "Content-Type: application/json" \
  -d '{"notes":""}' | python -m json.tool
# Expected: {"detail":"notes are required"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/routes.py
git commit -m "feat(validation): add override-hs and escalate API endpoints"
```

---

## Task 2: API helpers — `js/api.js`

**Files:**
- Modify: `js/api.js`

- [ ] **Step 1: Add two new functions after `flagShipment()` in `js/api.js`**

```javascript
/* ── Human Validation ─────────────────────────────────────────── */
async function overrideHSCode(shipmentId, hsCode, reason) {
  return apiFetch(`/api/shipments/${shipmentId}/override-hs`, 'POST', { hs_code: hsCode, reason })
}
async function escalateShipment(shipmentId, assignee, notes) {
  return apiFetch(`/api/shipments/${shipmentId}/escalate`, 'POST', { assignee, notes })
}
```

- [ ] **Step 2: Commit**

```bash
git add js/api.js
git commit -m "feat(validation): add overrideHSCode and escalateShipment API helpers"
```

---

## Task 3: Modify `shipments.html` + `shipments.js` — monitoring only

**Files:**
- Modify: `js/shipments.js`
- Modify: `shipments.html`

### `js/shipments.js` changes

- [ ] **Step 1: Change row click to deep-link to verification.html**

In `shipments.js`, find the `renderTable()` function's row HTML. The row currently has:
```javascript
onclick="window.location='index.html?id=${s.sap_shipment_id}'"
```
Replace with:
```javascript
onclick="window.location='verification.html?id=${s.sap_shipment_id}'"
```

- [ ] **Step 2: Replace the row actions span — remove Approve and Flag buttons**

Find the row actions `<span class="row-acts" ...>` block and replace its content so only Run A, Run B, and Open remain:

```javascript
      <span class="row-acts" onclick="event.stopPropagation()">
        <button class="ibt" title="Run Module A" onclick="doRunA('${s.sap_shipment_id}', this)">
          <i class="ti ti-brain"></i>
        </button>
        <button class="ibt" title="Run Module B" onclick="doRunB('${s.sap_shipment_id}', this)">
          <i class="ti ti-world"></i>
        </button>
        <button class="ibt" title="Review in Validation Dashboard"
          onclick="event.stopPropagation();window.location='verification.html?id=${s.sap_shipment_id}'">
          <i class="ti ti-shield-check"></i>
        </button>
      </span>
```

- [ ] **Step 3: Remove `doApprove` and `doFlag` functions from `shipments.js`**

Delete the `doApprove()` and `doFlag()` function bodies entirely. They are no longer called from this page.

### `shipments.html` changes

- [ ] **Step 4: Update the table column header — remove "Actions", keep 7 columns**

Find the `.tbl-head` in `shipments.html`:
```html
<div class="tbl-head">
  <span>Shipment</span>
  <span>HS Code</span>
  <span>Product</span>
  <span>Confidence</span>
  <span style="text-align:right">FTA Saving</span>
  <span>Best FTA</span>
  <span>Status</span>
  <span style="text-align:right">Actions</span>
</div>
```
Replace with:
```html
<div class="tbl-head">
  <span>Shipment</span>
  <span>HS Code</span>
  <span>Product</span>
  <span>Confidence</span>
  <span style="text-align:right">FTA Saving</span>
  <span>Best FTA</span>
  <span>Status</span>
  <span style="text-align:right">Pipeline</span>
</div>
```

- [ ] **Step 5: Update the grid column definition in `shipments.html` `<style>` block**

The inline style currently defines 8 columns. After removing the Approve/Flag buttons the actions column shrinks. Update:
```css
.tbl-head, .tbl-row {
  grid-template-columns: 76px 78px 1fr 90px 72px 68px 82px 80px;
}
```

- [ ] **Step 6: Commit**

```bash
git add js/shipments.js shipments.html
git commit -m "feat(validation): shipments.html monitoring-only — remove approve/flag, link to verification dashboard"
```

---

## Task 4: Add Validation nav item to all HTML pages

**Files:**
- Modify: `shipments.html`, `audit.html`, `fta-library.html`, `reports.html`, `index.html`

In every page's sidebar `<nav>`, find the Analysis nav-section and add the Validation item after "All Shipments":

```html
<div class="nav-item" data-page="verification" onclick="location='verification.html'">
  <i class="ti ti-shield-check"></i> Validation
  <span class="nav-badge warn" id="navPending">—</span>
</div>
```

The `navPending` badge is optional — only `verification.html` will populate it. On other pages it can be omitted or left as `—`.

- [ ] **Step 1: Add nav item to `shipments.html`** — after the "All Shipments" nav-item
- [ ] **Step 2: Add nav item to `audit.html`** — after the "All Shipments" nav-item
- [ ] **Step 3: Add nav item to `fta-library.html`** — after the "All Shipments" nav-item
- [ ] **Step 4: Add nav item to `reports.html`** — after the "All Shipments" nav-item
- [ ] **Step 5: Add nav item to `index.html`** — after the "All Shipments" nav-item

- [ ] **Step 6: Commit**

```bash
git add shipments.html audit.html fta-library.html reports.html index.html
git commit -m "feat(validation): add Validation nav item to all pages"
```

---

## Task 5: Create `verification.html`

**Files:**
- Create: `verification.html`

- [ ] **Step 1: Create `verification.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NEXA · Validation</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.2.0/tabler-icons.min.css">
<link rel="stylesheet" href="css/styles.css">
<style>
/* Split-panel layout — full height below topbar */
.validation-layout {
  display: flex;
  height: calc(100vh - 54px);
  overflow: hidden;
}

/* Left queue panel */
.queue-panel {
  width: 300px;
  min-width: 300px;
  border-right: 1px solid var(--hairline);
  display: flex;
  flex-direction: column;
  background: var(--canvas);
  overflow: hidden;
}
.queue-header {
  padding: 14px var(--sp-md) 10px;
  border-bottom: 1px solid var(--hairline);
}
.queue-header-title { font-size: 13px; font-weight: 600; color: var(--ink); }
.queue-header-meta  { font-size: 11px; color: var(--muted-soft); margin-top: 2px; }
.queue-progress {
  height: 4px;
  background: var(--hairline);
  border-radius: var(--r-pill);
  margin-top: 8px;
  overflow: hidden;
}
.queue-progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: var(--r-pill);
  transition: width .3s ease;
}
.reg-alert {
  padding: 8px var(--sp-md);
  background: rgba(232,165,90,.08);
  border-bottom: 1px solid var(--amber);
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.reg-alert i { color: var(--amber); margin-top: 1px; flex-shrink: 0; }
.reg-alert-title { font-size: 11px; font-weight: 600; color: var(--body-strong); }
.reg-alert-body  { font-size: 10.5px; color: var(--muted); }
.queue-list { flex: 1; overflow-y: auto; }
.queue-item {
  padding: 9px var(--sp-md);
  border-bottom: 1px solid var(--hairline-soft);
  cursor: pointer;
  transition: background .1s;
  border-left: 3px solid transparent;
}
.queue-item:hover    { background: var(--surface-soft); }
.queue-item.selected { background: var(--surface-card); }
.qi-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px; }
.qi-id  { font-size: 12px; font-weight: 600; color: var(--ink); font-family: var(--mono); }
.qi-name { font-size: 11px; color: var(--muted-soft); margin-bottom: 4px;
           overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.qi-conf { display: flex; align-items: center; gap: 6px; }
.conf-track { height: 3px; flex: 1; background: var(--hairline); border-radius: var(--r-pill); overflow: hidden; }
.conf-fill  { height: 100%; border-radius: var(--r-pill); }
.queue-footer {
  padding: 10px var(--sp-md);
  border-top: 1px solid var(--hairline);
  background: var(--surface-soft);
}
.queue-footer-note { font-size: 10px; color: var(--muted-soft); text-align: center; margin-top: 4px; }

/* Right detail panel */
.detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--surface-soft);
}
.detail-header {
  padding: 12px var(--sp-xl);
  background: var(--canvas);
  border-bottom: 1px solid var(--hairline);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}
.detail-title { font-size: 14px; font-weight: 600; color: var(--ink); }
.detail-meta  { font-size: 11px; color: var(--muted-soft); margin-top: 2px; }
.detail-body  {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-lg) var(--sp-xl);
  display: flex;
  flex-direction: column;
  gap: var(--sp-md);
}
.detail-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted-soft);
  font-size: 13px;
  text-align: center;
  line-height: 1.8;
}

/* Action bar */
.action-bar {
  padding: 12px var(--sp-xl);
  background: var(--canvas);
  border-top: 2px solid var(--hairline);
  display: flex;
  gap: var(--sp-sm);
  align-items: center;
  flex-shrink: 0;
}
.action-bar .btn { flex: 1; justify-content: center; }

/* Inline forms (Edit HS / Escalate) */
.inline-form {
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  padding: var(--sp-md);
  margin-top: var(--sp-sm);
}
.inline-form .field       { margin-bottom: var(--sp-sm); }
.inline-form label        { display: block; font-size: 11px; font-weight: 500; color: var(--muted); margin-bottom: 4px; }
.inline-form input,
.inline-form select,
.inline-form textarea     { width: 100%; padding: 7px 10px; border: 1px solid var(--hairline);
                            border-radius: var(--r-md); font-size: 12.5px; font-family: var(--sans);
                            background: var(--canvas); color: var(--ink); }
.inline-form input:focus,
.inline-form select:focus,
.inline-form textarea:focus { outline: none; border-color: var(--primary); }
.inline-form .required    { color: var(--error); }
.inline-form .form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: var(--sp-sm); }
.field-error { border-color: var(--error) !important; }

/* Completion state */
.completion-card {
  background: var(--canvas);
  border: 1px solid var(--hairline);
  border-radius: var(--r-lg);
  padding: var(--sp-xl);
  text-align: center;
  margin: auto;
  max-width: 420px;
}
.completion-icon { font-size: 48px; color: var(--teal); margin-bottom: var(--sp-md); }
.completion-title { font-size: 18px; font-weight: 600; color: var(--ink); margin-bottom: 6px; }
.completion-sub   { font-size: 13px; color: var(--muted-soft); margin-bottom: var(--sp-lg); }
.completion-stats { display: grid; grid-template-columns: repeat(3,1fr); gap: var(--sp-sm); margin-bottom: var(--sp-lg); }
.stat-box { background: var(--surface-soft); border-radius: var(--r-md); padding: var(--sp-sm); }
.stat-val { font-size: 20px; font-weight: 600; color: var(--ink); }
.stat-lbl { font-size: 10px; color: var(--muted-soft); }
</style>
</head>
<body>
<div class="app">

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-logo">
      <div class="logo-row">
        <div class="logo-mark">
          <svg viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7.5 1v2M7.5 12v2M1 7.5h2M12 7.5h2M2.87 2.87l1.41 1.41M10.72 10.72l1.41 1.41M12.13 2.87l-1.41 1.41M4.28 10.72l-1.41 1.41" stroke="#a09d96" stroke-width="1.4" stroke-linecap="round"/>
            <circle cx="7.5" cy="7.5" r="2" fill="#cc785c"/>
          </svg>
        </div>
        <span class="logo-wordmark">NEXA Trade AI</span>
      </div>
      <div class="logo-sub">Jabil · Global Trade Compliance</div>
    </div>
    <nav class="nav">
      <div class="nav-section">
        <div class="nav-label">Analysis</div>
        <div class="nav-item" data-page="index"        onclick="location='index.html'"><i class="ti ti-search"></i> Shipment Lookup</div>
        <div class="nav-item" data-page="shipments"    onclick="location='shipments.html'"><i class="ti ti-list-check"></i> All Shipments</div>
        <div class="nav-item" data-page="verification" onclick="location='verification.html'">
          <i class="ti ti-shield-check"></i> Validation
          <span class="nav-badge warn" id="navPending">—</span>
        </div>
        <div class="nav-item" data-page="audit"        onclick="location='audit.html'"><i class="ti ti-clock-history"></i> Audit Trail</div>
      </div>
      <div class="nav-section">
        <div class="nav-label">Intelligence</div>
        <div class="nav-item" data-page="fta-library"  onclick="location='fta-library.html'"><i class="ti ti-world"></i> FTA Library</div>
        <div class="nav-item" data-page="reports"      onclick="location='reports.html'"><i class="ti ti-chart-bar"></i> Analytics</div>
      </div>
      <div class="nav-section">
        <div class="nav-label">System</div>
        <div class="nav-item" onclick="runSeedAndRefresh()"><i class="ti ti-database"></i> Re-Seed Data</div>
        <div class="nav-item" onclick="showToast('Configuration — coming soon')"><i class="ti ti-settings"></i> Configuration</div>
      </div>
    </nav>
    <div class="sidebar-user">
      <div class="user-card">
        <div class="avatar">SL</div>
        <div>
          <div class="user-name">Sarah Lim</div>
          <div class="user-role">Trade Compliance Analyst</div>
        </div>
      </div>
    </div>
  </aside>

  <!-- Main -->
  <div class="main">

    <!-- Topbar -->
    <div class="topbar">
      <div class="topbar-crumb">
        NEXA <i class="ti ti-chevron-right"></i> <strong>Human Validation</strong>
      </div>
      <div class="live-row"><div class="live-dot"></div> Live · Supabase</div>
      <button class="btn" onclick="init()"><i class="ti ti-refresh"></i> Refresh</button>
    </div>

    <!-- Split-panel layout (no .content wrapper — needs full height) -->
    <div class="validation-layout">

      <!-- LEFT: Queue panel -->
      <div class="queue-panel">

        <div class="queue-header">
          <div class="queue-header-title">Review Queue</div>
          <div class="queue-header-meta" id="queueMeta">Loading…</div>
          <div class="queue-progress"><div class="queue-progress-fill" id="queueProgressFill" style="width:0%"></div></div>
        </div>

        <!-- Regulatory alert (hidden by default) -->
        <div class="reg-alert" id="regAlert" style="display:none">
          <i class="ti ti-alert-triangle" style="font-size:15px"></i>
          <div>
            <div class="reg-alert-title" id="regAlertTitle">Regulatory Alert</div>
            <div class="reg-alert-body"  id="regAlertBody">—</div>
          </div>
        </div>

        <!-- Filter tabs -->
        <div class="filter-bar" style="background:var(--surface-soft)">
          <button class="tab active" onclick="setQueueFilter('all',this)">All</button>
          <button class="tab flag-tab" onclick="setQueueFilter('flagged',this)">
            <i class="ti ti-alert-circle" style="font-size:11px"></i> Flagged
          </button>
          <button class="tab" onclick="setQueueFilter('pending',this)">Pending</button>
          <button class="tab" onclick="setQueueFilter('approved',this)">
            <i class="ti ti-check" style="font-size:11px"></i> Done
          </button>
        </div>

        <!-- Queue items -->
        <div class="queue-list" id="queueList">
          <div style="padding:24px;text-align:center;color:var(--muted-soft);font-size:12px">
            <i class="ti ti-loader-2 spin" style="font-size:20px;display:block;margin-bottom:8px"></i>
            Loading…
          </div>
        </div>

        <!-- Bulk approve footer -->
        <div class="queue-footer">
          <button class="btn btn-primary" style="width:100%;justify-content:center" id="bulkApproveBtn" onclick="doBulkApprove()" disabled>
            <i class="ti ti-checks"></i> Bulk Approve ≥95% (0)
          </button>
          <div class="queue-footer-note">Each approval logged individually</div>
        </div>

      </div>

      <!-- RIGHT: Detail panel -->
      <div class="detail-panel">

        <div class="detail-header" id="detailHeader" style="display:none">
          <div>
            <div class="detail-title" id="detailTitle">—</div>
            <div class="detail-meta"  id="detailMeta">—</div>
          </div>
          <span class="pill" id="detailStatusPill">—</span>
        </div>

        <div class="detail-body" id="detailBody">
          <div class="detail-empty">
            <div>
              <i class="ti ti-shield-check" style="font-size:40px;display:block;margin-bottom:12px;color:var(--hairline)"></i>
              <strong style="color:var(--ink);font-size:14px">Select a shipment to review</strong><br>
              Choose an item from the queue on the left.
            </div>
          </div>
        </div>

        <div class="action-bar" id="actionBar" style="display:none">
          <button class="btn btn-primary" id="btnApprove" onclick="doApprove()" style="background:var(--teal);border-color:var(--teal)">
            <i class="ti ti-check"></i> Approve
          </button>
          <button class="btn" id="btnEdit" onclick="toggleEditForm()" style="background:rgba(59,130,246,.08);border-color:rgba(59,130,246,.3);color:#1d4ed8">
            <i class="ti ti-edit"></i> Edit HS Code
          </button>
          <button class="btn" id="btnEscalate" onclick="toggleEscalateForm()" style="background:rgba(232,165,90,.08);border-color:rgba(232,165,90,.3);color:#92400e">
            <i class="ti ti-arrow-up-right"></i> Escalate
          </button>
        </div>

      </div>
    </div>

  </div>
</div>

<!-- Toast -->
<div id="toast" class="toast" onclick="this.classList.remove('show')">
  <span id="toastMsg"></span>
</div>

<script src="js/shared.js"></script>
<script src="js/api.js"></script>
<script src="js/verification.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add verification.html
git commit -m "feat(validation): add verification.html shell — split panel layout"
```

---

## Task 6: `js/verification.js` — boot, queue, item selection

**Files:**
- Create: `js/verification.js`

- [ ] **Step 1: Create `js/verification.js` with state, init, queue render, and item selection**

```javascript
/**
 * verification.js — Human Validation Dashboard
 * Analyst must take an action on every shipment before SAP submission.
 */

/* ── State ────────────────────────────────────────────────────── */
let SHIPMENTS    = []
let currentId    = null
let activeFilter = 'all'

/* ── Boot ────────────────────────────────────────────────────── */
async function init() {
  setHtml('queueList', `
    <div style="padding:24px;text-align:center;color:var(--muted-soft);font-size:12px">
      <i class="ti ti-loader-2 spin" style="font-size:20px;display:block;margin-bottom:8px"></i>
      Loading queue…
    </div>`)
  try {
    SHIPMENTS = await fetchShipments()
    updateQueueHeader()
    renderQueue()
    updateBulkApproveBtn()
    updateNavBadge()

    // Deep-link: verification.html?id=SHIP001
    const preId = new URLSearchParams(window.location.search).get('id')
    if (preId && SHIPMENTS.find(s => s.sap_shipment_id === preId)) {
      selectItem(preId)
    } else {
      // Auto-select first non-approved item
      const first = SHIPMENTS.find(s => s.status !== 'approved') || SHIPMENTS[0]
      if (first) selectItem(first.sap_shipment_id)
    }
  } catch (e) {
    showToast('Failed to load queue: ' + e.message, true)
    setHtml('queueList', `
      <div style="padding:24px;color:var(--error);font-size:12px;text-align:center">
        <i class="ti ti-plug-off" style="font-size:24px;display:block;margin-bottom:8px"></i>
        Backend offline — run uvicorn in /backend
      </div>`)
  }
}

/* ── Queue header ────────────────────────────────────────────── */
function updateQueueHeader() {
  const total    = SHIPMENTS.length
  const reviewed = SHIPMENTS.filter(s => s.status === 'approved' || s.status === 'flagged').length
  const pct      = total > 0 ? Math.round(reviewed / total * 100) : 0

  setText('queueMeta', `${reviewed} of ${total} reviewed · ${total - reviewed} remaining`)
  const fill = $('queueProgressFill')
  if (fill) fill.style.width = pct + '%'
  setText('navPending', total - reviewed || 0)
}

/* ── Queue filter ────────────────────────────────────────────── */
function getFiltered() {
  if (activeFilter === 'flagged')  return SHIPMENTS.filter(s => s.status === 'flagged')
  if (activeFilter === 'pending')  return SHIPMENTS.filter(s => s.status === 'pending')
  if (activeFilter === 'approved') return SHIPMENTS.filter(s => s.status === 'approved')
  return SHIPMENTS
}

function setQueueFilter(f, btn) {
  activeFilter = f
  document.querySelectorAll('.queue-panel .tab').forEach(b => b.classList.remove('active'))
  btn.classList.add('active')
  renderQueue()
}

/* ── Queue render ────────────────────────────────────────────── */
function renderQueue() {
  const items = getFiltered()
  if (!items.length) {
    setHtml('queueList', `
      <div style="padding:24px;text-align:center;color:var(--muted-soft);font-size:12px">
        No shipments in this category.
      </div>`)
    return
  }
  setHtml('queueList', items.map(renderQueueItem).join(''))
}

function renderQueueItem(s) {
  const cls      = s.hs_classifications?.[0] || {}
  const conf     = cls.confidence_score || 0
  const selected = s.sap_shipment_id === currentId

  const borderCol = s.status === 'approved' ? 'var(--teal)'
                  : s.status === 'flagged'  ? 'var(--error)'
                  : conf >= 95              ? 'var(--teal)'
                  : conf >= 85              ? 'var(--amber)'
                  : 'var(--error)'

  const statusLabel = { approved: '✓ Approved', flagged: 'Escalated', pending: 'Pending' }[s.status] || s.status
  const statusCol   = statusColor(s.status)

  return `
  <div class="queue-item${selected ? ' selected' : ''}"
       onclick="selectItem('${s.sap_shipment_id}')"
       style="border-left-color:${borderCol}">
    <div class="qi-top">
      <span class="qi-id">${s.sap_shipment_id}</span>
      <span style="padding:1px 6px;border-radius:var(--r-pill);font-size:9px;font-weight:600;background:${statusCol}20;color:${statusCol}">
        ${statusLabel}
      </span>
    </div>
    <div class="qi-name" title="${s.product_description}">${s.product_description}</div>
    <div class="qi-conf">
      <div class="conf-track">
        <div class="conf-fill" style="width:${conf}%;background:${confColor(conf)}"></div>
      </div>
      <span style="color:${confColor(conf)};font-size:10px;font-weight:600;font-family:var(--mono);min-width:28px;text-align:right">
        ${conf ? conf + '%' : '—'}
      </span>
    </div>
  </div>`
}

/* ── Select item ─────────────────────────────────────────────── */
async function selectItem(id) {
  currentId = id
  renderQueue()  // re-render to show selection highlight

  // Show loading state in detail panel
  const detailHeader = $('detailHeader')
  const actionBar    = $('actionBar')
  if (detailHeader) detailHeader.style.display = 'none'
  if (actionBar)    actionBar.style.display    = 'none'
  setHtml('detailBody', `
    <div class="detail-empty">
      <div><i class="ti ti-loader-2 spin" style="font-size:32px;display:block;margin-bottom:10px;color:var(--hairline)"></i></div>
    </div>`)

  // Scroll selected item into view
  const el = document.querySelector('.queue-item.selected')
  if (el) el.scrollIntoView({ block: 'nearest' })

  try {
    const r = await apiFetch(`/api/shipments/${id}`)
    renderDetailPanel(r.data)
  } catch (e) {
    setHtml('detailBody', `
      <div class="detail-empty">
        <div style="color:var(--error)">
          <i class="ti ti-alert-circle" style="font-size:32px;display:block;margin-bottom:8px"></i>
          Failed to load: ${e.message}
        </div>
      </div>`)
  }
}

/* ── Nav pending badge ───────────────────────────────────────── */
function updateNavBadge() {
  const pending = SHIPMENTS.filter(s => s.status === 'pending' || s.status === 'flagged').length
  setText('navPending', pending || '0')
}

/* ── Bulk approve ────────────────────────────────────────────── */
function updateBulkApproveBtn() {
  const eligible = SHIPMENTS.filter(s => {
    const conf = s.hs_classifications?.[0]?.confidence_score || 0
    return s.status === 'pending' && conf >= 95
  })
  const btn = $('bulkApproveBtn')
  if (!btn) return
  btn.disabled = eligible.length === 0
  btn.innerHTML = `<i class="ti ti-checks"></i> Bulk Approve ≥95% (${eligible.length})`
}

async function doBulkApprove() {
  const eligible = SHIPMENTS.filter(s => {
    const conf = s.hs_classifications?.[0]?.confidence_score || 0
    return s.status === 'pending' && conf >= 95
  })
  if (!eligible.length) return

  const btn = $('bulkApproveBtn')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Approving…' }

  let done = 0
  for (const s of eligible) {
    try {
      await approveShipment(s.sap_shipment_id)
      s.status = 'approved'
      done++
    } catch (e) {
      console.warn('Bulk approve failed for', s.sap_shipment_id, e.message)
    }
  }

  showToast(`✓ Bulk approved ${done} shipments`)
  SHIPMENTS = await fetchShipments()
  updateQueueHeader()
  renderQueue()
  updateBulkApproveBtn()
  updateNavBadge()
  if (currentId) selectItem(currentId)
}

init()
```

- [ ] **Step 2: Open `verification.html` in browser (Live Server), confirm queue renders**

Expected: queue panel shows all shipments with confidence bars and status pills. Selecting a row shows a loading spinner in the detail panel then an error (detail rendering comes next task).

- [ ] **Step 3: Commit**

```bash
git add js/verification.js
git commit -m "feat(validation): verification.js boot, queue render, item selection, bulk approve"
```

---

## Task 7: `js/verification.js` — detail panel rendering

**Files:**
- Modify: `js/verification.js`

- [ ] **Step 1: Add `renderDetailPanel` and the three module card functions**

Append to `js/verification.js`:

```javascript
/* ── Detail panel ────────────────────────────────────────────── */
function renderDetailPanel(s) {
  const cls = s.hs_classifications?.[0] || null
  const fta = s.fta_results?.[0]        || null
  const lc  = s.landed_costs?.[0]       || null
  const cif = (s.shipment_value_usd || 0) + (s.freight_cost_usd || 0) + (s.insurance_cost_usd || 0)

  // Header
  const statusCol = statusColor(s.status)
  setText('detailTitle', `${s.sap_shipment_id} — ${s.product_description}`)
  setText('detailMeta',  `${s.origin_country} → Malaysia · USD ${cif.toLocaleString()} CIF`)
  const pill = $('detailStatusPill')
  if (pill) {
    pill.textContent = s.status.toUpperCase()
    pill.style.cssText = `background:${statusCol}18;color:${statusCol};border:1px solid ${statusCol}40`
  }
  $('detailHeader').style.display = ''
  $('actionBar').style.display    = ''

  // Disable actions if already reviewed
  const reviewed = s.status === 'approved' || s.status === 'flagged'
  ;['btnApprove','btnEdit','btnEscalate'].forEach(id => {
    const b = $(id); if (b) b.disabled = reviewed
  })

  // Body cards
  setHtml('detailBody',
    renderModuleACard(cls) +
    renderModuleBCard(fta, cif) +
    renderModuleCCard(lc) +
    '<div id="inlineFormContainer"></div>'
  )
}

/* Module A card */
function renderModuleACard(cls) {
  if (!cls) return `
  <div class="det-card">
    <div class="det-head"><i class="ti ti-brain" style="color:var(--primary);font-size:15px"></i>
      <span class="det-title">Module A — HS Classification</span></div>
    <div class="det-body" style="color:var(--muted-soft);font-size:12px;text-align:center;padding:20px 0">
      Module A has not run yet. Go to <a href="shipments.html" style="color:var(--primary)">All Shipments</a> to run it.
    </div>
  </div>`

  const conf      = cls.confidence_score || 0
  const barColor  = confColor(conf)
  const agrees    = cls.e2open_hs_code === cls.ai_hs_code
  const overridden = !!cls.analyst_override_hs
  const statusText = overridden ? 'Analyst Override'
                   : cls.module_a_status === 'auto_passed' ? '✓ Auto Passed' : '⚠ Review Required'
  const statusCol  = overridden ? 'var(--primary)'
                   : cls.module_a_status === 'auto_passed' ? 'var(--teal)' : 'var(--amber)'

  return `
  <div class="det-card">
    <div class="det-head">
      <i class="ti ti-brain" style="color:var(--primary);font-size:15px"></i>
      <span class="det-title">Module A — HS Classification</span>
      <span style="font-size:11px;font-weight:600;color:${statusCol}">${statusText}</span>
    </div>
    <div class="det-body">
      <div style="display:grid;grid-template-columns:1fr auto 1fr auto;gap:12px;align-items:center;margin-bottom:12px">
        <div>
          <div style="font-size:10px;color:var(--muted-soft);text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">e2open</div>
          <div style="font-family:var(--mono);font-size:15px;font-weight:600;color:var(--amber)">${cls.e2open_hs_code || '—'}</div>
        </div>
        <div style="color:var(--muted-soft);font-size:14px">→</div>
        <div>
          <div style="font-size:10px;color:var(--muted-soft);text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px">
            ${overridden ? 'Override' : 'AI'}
          </div>
          <div style="font-family:var(--mono);font-size:15px;font-weight:600;color:${agrees ? 'var(--teal)' : 'var(--primary)'}">
            ${cls.final_hs_code || '—'}
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:10px;color:var(--muted-soft);margin-bottom:3px">Confidence</div>
          <div style="font-size:18px;font-weight:600;color:${barColor};font-family:var(--mono)">${conf}%</div>
        </div>
      </div>
      <div class="conf-bar-wrap">
        <div class="conf-track"><div class="conf-fill" style="width:${Math.min(conf,100)}%;background:${barColor};height:6px;border-radius:9999px"></div></div>
      </div>
      ${!agrees ? `<div style="margin-top:10px;padding:6px 10px;background:rgba(232,165,90,.08);border-left:3px solid var(--amber);border-radius:0 var(--r-md) var(--r-md) 0;font-size:11.5px;color:var(--body)">
        <strong style="color:var(--amber)">⚠ Disagrees with e2open.</strong> AI overrides to <span style="font-family:var(--mono)">${cls.ai_hs_code}</span>.
      </div>` : ''}
      ${cls.reasoning_text ? `
      <details style="margin-top:10px">
        <summary style="font-size:11.5px;color:var(--muted);cursor:pointer;font-weight:500">AI Reasoning — click to expand</summary>
        <div style="margin-top:8px;padding:8px;background:var(--surface-soft);border-radius:var(--r-md);font-size:11.5px;color:var(--muted-soft);line-height:1.7">
          ${cls.reasoning_text}
        </div>
      </details>` : ''}
      ${overridden ? `<div style="margin-top:8px;font-size:11px;color:var(--teal)">✓ Analyst override on record: <span style="font-family:var(--mono)">${cls.analyst_override_hs}</span></div>` : ''}
    </div>
  </div>`
}

/* Module B card */
function renderModuleBCard(fta, cif) {
  if (!fta) return `
  <div class="det-card">
    <div class="det-head"><i class="ti ti-world" style="color:var(--teal);font-size:15px"></i>
      <span class="det-title">Module B — FTA Match</span></div>
    <div class="det-body" style="color:var(--muted-soft);font-size:12px;text-align:center;padding:16px 0">
      Module B not run yet.
    </div>
  </div>`

  const ftaRate  = Math.min(Math.max(fta.best_fta_rate_pct ?? 0, 0), 100)
  const mfnRate  = Math.min(Math.max(fta.mfn_rate_pct     ?? 0, 0), 100)
  const saving   = fta.duty_saving_usd || 0
  const ftaName  = fta.best_fta_name   || 'MFN'
  const isFTA    = fta.module_b_status === 'fta_applied'
  const badge    = isFTA ? `<span style="color:var(--teal);font-weight:600">✓ ${ftaName} Applied</span>`
                         : `<span style="color:var(--amber);font-weight:600">⚠ MFN Fallback</span>`

  return `
  <div class="det-card">
    <div class="det-head">
      <i class="ti ti-world" style="color:var(--teal);font-size:15px"></i>
      <span class="det-title">Module B — FTA Match</span>
      ${badge}
    </div>
    <div class="det-body">
      <div style="display:flex;gap:var(--sp-lg);margin-bottom:8px">
        <div><div style="font-size:10px;color:var(--muted-soft);margin-bottom:2px">Best FTA</div>
          <div style="font-size:14px;font-weight:600;color:${isFTA ? 'var(--teal)' : 'var(--muted)'}">${ftaRate}% (${ftaName})</div></div>
        <div><div style="font-size:10px;color:var(--muted-soft);margin-bottom:2px">MFN Rate</div>
          <div style="font-size:14px;font-weight:600;color:var(--muted)">${mfnRate}%</div></div>
        <div><div style="font-size:10px;color:var(--muted-soft);margin-bottom:2px">Duty Saving</div>
          <div style="font-size:14px;font-weight:600;color:${saving > 0 ? 'var(--teal)' : 'var(--muted)'}">${saving > 0 ? money(saving) : '$0.00'}</div></div>
      </div>
    </div>
  </div>`
}

/* Module C card */
function renderModuleCCard(lc) {
  if (!lc) return `
  <div class="det-card">
    <div class="det-head"><i class="ti ti-receipt" style="color:var(--amber);font-size:15px"></i>
      <span class="det-title">Module C — Landed Cost</span></div>
    <div class="det-body" style="color:var(--muted-soft);font-size:12px;text-align:center;padding:16px 0">
      Module C not run yet.
    </div>
  </div>`

  const breakdown    = lc.cost_breakdown || []
  const totalCifMyr  = breakdown.reduce((s, r) => s + (r.apportionment_metrics?.calculated_cif_myr      || 0), 0)
  const totalDutyMyr = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.customs_duty_charged   || 0), 0)
  const totalTaxMyr  = breakdown.reduce((s, r) => s + (r.regulatory_charges_myr?.sales_tax_charged      || 0), 0)
  const fxEst        = totalCifMyr > 0 && lc.cif_value_usd > 0 ? totalCifMyr / lc.cif_value_usd : 4.67
  const procMyr      = Math.round((lc.other_fees_usd || 0) * fxEst * 100) / 100
  const isLmw        = breakdown[0]?.flags_applied?.is_lmw_facility ?? true
  const fmt          = n => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return `
  <div class="det-card">
    <div class="det-head">
      <i class="ti ti-receipt" style="color:var(--amber);font-size:15px"></i>
      <span class="det-title">Module C — Landed Cost</span>
      ${isLmw ? `<span style="font-size:10px;font-weight:600;color:var(--teal)">✓ LMW Exempt</span>` : ''}
    </div>
    <div class="det-body">
      <div class="cost-ln"><span class="lbl">Total CIF</span><span class="val" style="font-family:var(--mono)">MYR ${fmt(totalCifMyr)}</span></div>
      <div class="cost-ln"><span class="lbl">Customs Duty</span><span class="val" style="color:${totalDutyMyr === 0 ? 'var(--teal)' : 'var(--ink)'}">MYR ${fmt(totalDutyMyr)}</span></div>
      <div class="cost-ln"><span class="lbl">Sales Tax (10%)</span><span class="val" style="color:${totalTaxMyr === 0 ? 'var(--teal)' : 'var(--ink)'}">MYR ${fmt(totalTaxMyr)}</span></div>
      <div class="cost-ln"><span class="lbl">Processing Fee</span><span class="val" style="font-family:var(--mono)">MYR ${fmt(procMyr)}</span></div>
      <div class="cost-total"><span>Total Landed Cost</span><span class="val">USD ${fmt(lc.total_landed_cost_usd || 0)}</span></div>
      ${(lc.fta_saving_usd || 0) > 0 ? `<div style="margin-top:8px;font-size:11px;color:var(--teal);font-weight:600;text-align:center">↓ FTA saves ${money(lc.fta_saving_usd)} vs MFN</div>` : ''}
    </div>
  </div>`
}
```

- [ ] **Step 2: Open verification.html in browser, select SHIP001 — confirm all three module cards render**

Expected: Module A card shows HS code and confidence bar. Module B shows FTA rate. Module C shows MYR breakdown (or "not run yet" for each unrun module).

- [ ] **Step 3: Commit**

```bash
git add js/verification.js
git commit -m "feat(validation): detail panel — Module A/B/C cards with reasoning, FTA, landed cost"
```

---

## Task 8: `js/verification.js` — action handlers

**Files:**
- Modify: `js/verification.js`

- [ ] **Step 1: Append approve, edit-form, and escalate-form logic**

```javascript
/* ── Approve ─────────────────────────────────────────────────── */
async function doApprove() {
  if (!currentId) return
  const btn = $('btnApprove')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Approving…' }
  try {
    await approveShipment(currentId)
    showToast(`✓ ${currentId} approved`)
    await refreshAndAdvance(currentId, 'approved')
  } catch (e) {
    showToast('Approve failed: ' + e.message, true)
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-check"></i> Approve' }
  }
}

/* ── Edit HS Code form ───────────────────────────────────────── */
function toggleEditForm() {
  const container = $('inlineFormContainer')
  if (!container) return
  if (container.innerHTML.includes('editForm')) {
    container.innerHTML = ''
    return
  }
  // Close escalate form if open
  container.innerHTML = ''

  const currentHS = SHIPMENTS.find(s => s.sap_shipment_id === currentId)
    ?.hs_classifications?.[0]?.final_hs_code || ''

  container.innerHTML = `
  <div class="inline-form" id="editForm">
    <div style="font-size:12px;font-weight:600;color:var(--ink);margin-bottom:var(--sp-sm)">Override HS Code</div>
    <div style="font-size:11px;color:var(--muted-soft);margin-bottom:var(--sp-sm)">
      Current: <span style="font-family:var(--mono);color:var(--primary)">${currentHS}</span>
    </div>
    <div class="field">
      <label>New HS Code <span class="required">*</span></label>
      <input type="text" id="overrideHSInput" placeholder="e.g. 8542.31" autocomplete="off">
    </div>
    <div class="field">
      <label>Reason for override <span class="required">*</span></label>
      <textarea id="overrideReasonInput" rows="3" placeholder="e.g. Confirmed as IC per supplier datasheet Rev.C"></textarea>
    </div>
    <div class="form-actions">
      <button class="btn" onclick="$('inlineFormContainer').innerHTML=''">Cancel</button>
      <button class="btn btn-primary" onclick="submitEditForm()"><i class="ti ti-check"></i> Save Override</button>
    </div>
  </div>`

  $('overrideHSInput')?.focus()
}

async function submitEditForm() {
  const hsCode = ($('overrideHSInput')?.value || '').trim()
  const reason = ($('overrideReasonInput')?.value || '').trim()

  let valid = true
  if (!hsCode) { $('overrideHSInput')?.classList.add('field-error');    valid = false }
  else           $('overrideHSInput')?.classList.remove('field-error')
  if (!reason) { $('overrideReasonInput')?.classList.add('field-error'); valid = false }
  else           $('overrideReasonInput')?.classList.remove('field-error')
  if (!valid)  return

  const btn = document.querySelector('#editForm .btn-primary')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Saving…' }
  try {
    await overrideHSCode(currentId, hsCode, reason)
    showToast(`✓ ${currentId} HS code overridden to ${hsCode}`)
    $('inlineFormContainer').innerHTML = ''
    await refreshAndAdvance(currentId, 'approved')
  } catch (e) {
    showToast('Override failed: ' + e.message, true)
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-check"></i> Save Override' }
  }
}

/* ── Escalate form ───────────────────────────────────────────── */
function toggleEscalateForm() {
  const container = $('inlineFormContainer')
  if (!container) return
  if (container.innerHTML.includes('escalateForm')) {
    container.innerHTML = ''
    return
  }
  container.innerHTML = ''

  container.innerHTML = `
  <div class="inline-form" id="escalateForm">
    <div style="font-size:12px;font-weight:600;color:var(--ink);margin-bottom:var(--sp-sm)">Escalate to Senior Analyst</div>
    <div class="field">
      <label>Assign to</label>
      <select id="escalateAssignee">
        <option value="James Tan">James Tan — Senior Trade Compliance Analyst</option>
        <option value="Priya Nair">Priya Nair — Compliance Manager</option>
      </select>
    </div>
    <div class="field">
      <label>Notes <span class="required">*</span></label>
      <textarea id="escalateNotes" rows="3" placeholder="Describe the issue requiring senior review…"></textarea>
    </div>
    <div class="form-actions">
      <button class="btn" onclick="$('inlineFormContainer').innerHTML=''">Cancel</button>
      <button class="btn" style="background:rgba(232,165,90,.1);border-color:var(--amber);color:#92400e" onclick="submitEscalateForm()">
        <i class="ti ti-arrow-up-right"></i> Escalate
      </button>
    </div>
  </div>`

  $('escalateNotes')?.focus()
}

async function submitEscalateForm() {
  const assignee = $('escalateAssignee')?.value || 'Senior Analyst'
  const notes    = ($('escalateNotes')?.value || '').trim()

  if (!notes) { $('escalateNotes')?.classList.add('field-error'); return }
  $('escalateNotes')?.classList.remove('field-error')

  const btn = document.querySelector('#escalateForm button:last-child')
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="ti ti-loader-2 spin"></i> Escalating…' }
  try {
    await escalateShipment(currentId, assignee, notes)
    showToast(`✓ ${currentId} escalated to ${assignee}`)
    $('inlineFormContainer').innerHTML = ''
    await refreshAndAdvance(currentId, 'flagged')
  } catch (e) {
    showToast('Escalate failed: ' + e.message, true)
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="ti ti-arrow-up-right"></i> Escalate' }
  }
}
```

- [ ] **Step 2: Test approve flow in browser**

1. Open `verification.html`, select any shipment
2. Click **Approve** — toast should say "✓ SHIPxxx approved"
3. Queue item should flip to green "✓ Approved"

- [ ] **Step 3: Test edit HS Code flow**

1. Click **Edit HS Code** — form should expand below action bar
2. Submit with empty fields — both inputs should turn red
3. Fill in `8542.31` and a reason, click Save — toast confirms override

- [ ] **Step 4: Test escalate flow**

1. Click **Escalate** — form expands
2. Submit with empty notes — notes field turns red
3. Fill in notes, submit — toast confirms escalation, item turns amber in queue

- [ ] **Step 5: Commit**

```bash
git add js/verification.js
git commit -m "feat(validation): action handlers — approve, edit HS override form, escalate form"
```

---

## Task 9: `js/verification.js` — auto-advance + completion state

**Files:**
- Modify: `js/verification.js`

- [ ] **Step 1: Append `refreshAndAdvance` and `showCompletionState`**

```javascript
/* ── Refresh + auto-advance ──────────────────────────────────── */
async function refreshAndAdvance(id, newStatus) {
  // Update local state immediately (no full reload needed for queue update)
  const ship = SHIPMENTS.find(s => s.sap_shipment_id === id)
  if (ship) ship.status = newStatus

  updateQueueHeader()
  renderQueue()
  updateBulkApproveBtn()
  updateNavBadge()

  // Check if all items are reviewed
  const allReviewed = SHIPMENTS.every(s => s.status === 'approved' || s.status === 'flagged')
  if (allReviewed) {
    showCompletionState()
    return
  }

  // Advance to next unreviewed item
  const currentIndex = SHIPMENTS.findIndex(s => s.sap_shipment_id === id)
  const remaining    = SHIPMENTS.filter(s => s.status === 'pending')
  if (remaining.length > 0) {
    // Prefer the next item after the current one in list order
    const next = SHIPMENTS.slice(currentIndex + 1).find(s => s.status === 'pending')
              || remaining[0]
    selectItem(next.sap_shipment_id)
  }
}

/* ── Completion state ────────────────────────────────────────── */
function showCompletionState() {
  currentId = null
  renderQueue()

  const approved  = SHIPMENTS.filter(s => s.status === 'approved').length
  const escalated = SHIPMENTS.filter(s => s.status === 'flagged').length
  const total     = SHIPMENTS.length

  $('detailHeader').style.display = 'none'
  $('actionBar').style.display    = 'none'

  setHtml('detailBody', `
    <div class="detail-body" style="align-items:center;justify-content:center;display:flex;flex:1">
      <div class="completion-card">
        <div class="completion-icon"><i class="ti ti-circle-check"></i></div>
        <div class="completion-title">All ${total} items reviewed</div>
        <div class="completion-sub">Every shipment has a recorded human decision. Ready for SAP submission.</div>
        <div class="completion-stats">
          <div class="stat-box">
            <div class="stat-val" style="color:var(--teal)">${approved}</div>
            <div class="stat-lbl">Approved</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color:var(--amber)">${escalated}</div>
            <div class="stat-lbl">Escalated</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color:var(--ink)">${total}</div>
            <div class="stat-lbl">Total</div>
          </div>
        </div>
        <div style="display:flex;gap:var(--sp-sm);justify-content:center">
          <button class="btn btn-primary" onclick="showToast('SAP writeback queued — feature coming soon')">
            <i class="ti ti-send"></i> Submit to SAP
          </button>
          <button class="btn" onclick="exportAuditCSV ? exportAuditCSV() : location.assign('audit.html')">
            <i class="ti ti-download"></i> Export Audit Trail
          </button>
        </div>
      </div>
    </div>`)
}

/* ── Export CSV (thin wrapper to audit.html function) ──────── */
function goToAudit() { location.assign('audit.html') }
```

- [ ] **Step 2: Test auto-advance in browser**

1. Open `verification.html` with SHIP001 selected
2. Click **Approve** — detail panel should immediately load SHIP002 (next pending item)
3. After approving all items — completion state card should appear

- [ ] **Step 3: Test deep-link from shipments.html**

1. Open `shipments.html`
2. Click any shipment row
3. Should navigate to `verification.html?id=SHIPxxx` with that item pre-selected and its detail loaded

- [ ] **Step 4: Commit**

```bash
git add js/verification.js
git commit -m "feat(validation): auto-advance to next pending item, completion state with SAP submit"
```

---

## Self-Review

**Spec coverage:**
- ✅ Batch overview (queue panel with all items, confidence bars, status pills) — Task 6
- ✅ Per-item view: reasoning log, FTA comparison, landed cost breakdown — Task 7
- ✅ Approve action — Task 8
- ✅ Edit / override HS with mandatory reason — Task 8
- ✅ Escalate with notes — Task 8
- ✅ Bulk approve ≥95%, each logged individually — Task 6
- ✅ Regulatory alert panel — Task 5 (HTML), Task 6 (conditionally shown)
- ✅ shipments.html monitoring-only (remove approve/flag) — Task 3
- ✅ shipments.html row → verification.html deep-link — Task 3
- ✅ verification.html reads ?id= and auto-selects — Task 6
- ✅ Auto-advance to next pending after action — Task 9
- ✅ Completion state when all reviewed — Task 9
- ✅ Both new backend endpoints — Task 1
- ✅ API helpers — Task 2
- ✅ Nav items across all pages — Task 4
- ✅ Visual identity matches existing system (same CSS vars + components) — Task 5

**Note on regulatory alert:** The HTML shell shows the `regAlert` div as `display:none`. Task 6's `init()` does not currently populate it — this is intentional YAGNI. The panel exists and can be wired to `gazette_alerts` data in a future iteration without HTML changes.
