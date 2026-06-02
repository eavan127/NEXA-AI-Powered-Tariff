# NEXA — Human Validation Dashboard — Design Spec

**Date:** 2026-06-02
**Branch:** feature/layer3-human-verification
**Status:** Approved — ready for implementation

---

## 1. Overview

The Human Validation Dashboard is the analyst's single interface for reviewing, approving, editing, or escalating AI-generated tariff recommendations for a shipment batch. Every item in the batch must receive an explicit human decision before any duty figure is submitted to SAP. No item can be bypassed.

**Pipeline position:**
```
Module A (HS Classification)
  └─► Module B (FTA Matching)
        └─► Module C (Landed Cost)
              └─► Human Validation Dashboard  ← this spec
                    └─► SAP writeback (audit-logged)
```

**New files:**
- `verification.html` — new page (same shell as `shipments.html`, `audit.html`)
- `js/verification.js` — page logic

**Existing files modified:**
- `js/api.js` — add `overrideHSCode()`, `escalateShipment()` API helpers
- `shipments.html` + `js/shipments.js` — remove Approve/Flag buttons; row click links to `verification.html?id={id}` instead of `index.html?id={id}`
- All HTML pages — add "Validation" link in sidebar nav
- `backend/api/routes.py` — add override-hs and escalate endpoints
- `backend/database/schema.sql` — document `analyst_override_hs` usage (already exists)

**`shipments.html` becomes monitoring-only:** Run Module A/B buttons remain (pipeline operations). Approve and Flag buttons are removed. The only way to approve a shipment is through `verification.html`. This enforces the "no bypass" rule.

---

## 2. Layout — Split Panel

```
┌─────────────────┬──────────────────────────────────────┐
│  QUEUE PANEL    │  DETAIL PANEL                         │
│  (300px fixed)  │  (flex: 1)                            │
│                 │                                        │
│  Progress bar   │  Item header (ID, product, status)    │
│  Reg. alert     │  ─────────────────────────────────    │
│  Filter tabs    │  Module A card (HS dispute, reasoning) │
│                 │  Module B card (FTA match)             │
│  [Item list]    │  Module C card (landed cost)           │
│   ├ SHIP001 ✓   │                                        │
│   ├ SHIP002 ⚠   │  ─────────────────────────────────    │
│   ├ SHIP004 ✗   │  [Approve] [Edit HS] [Escalate]       │
│   └ ...         │  (sticky action bar)                   │
│                 │                                        │
│  [Bulk Approve] │                                        │
└─────────────────┴──────────────────────────────────────┘
```

**Visual identity:** identical to existing app — CSS variables from `styles.css`, `.panel`, `.det-card`, `.btn`, `.btn-primary` component classes, sidebar, topbar from the shared shell pattern.

---

## 3. Queue Panel (Left, 300px)

### Header
- Title: "Review Queue"
- Sub-line: "X of N reviewed · Y remaining"
- Progress bar: `--primary` fill, `--hairline` track

### Regulatory Alert Banner
- Shown only when `gazette_alerts` has unread items affecting the current batch's HS codes
- Amber background (`rgba(232,165,90,.12)`), amber left border
- Text: alert title + "N items affected"
- Dismissable per session (localStorage flag)

### Filter Tabs
- All (N) | Flagged (N) | Pending (N) | Done (N)
- Same `.tab` / `.filter-bar` classes as existing pages

### Item List
Each item row shows:
- Left colour bar: red (flagged / <85%), amber (pending 85–94%), teal (pending ≥95%), green (approved/escalated)
- Shipment ID (bold) + product description (muted, truncated)
- Status pill (`.pill` class)
- Confidence bar + percentage (coloured by threshold)
- Selected item gets `--surface-card` background

### Bulk Approve Button
- Label: "Bulk Approve ≥95% (N items)"
- Only enabled when N ≥ 1 unreviewed items with confidence ≥ 95
- Uses `.btn.btn-primary` style
- On click: modal confirmation → calls `approveShipment()` for each item in sequence, each logged individually in `audit_trail`
- Sub-label: "Each approval logged individually" (muted, 11px)

---

## 4. Detail Panel (Right)

### Item Header
- Shipment ID + product description (`.page-title` / `.page-eyebrow` pattern)
- Origin → destination, CIF value
- Status pill (`.pill`)

### Module A Card (`.det-card`)
- Header: "HS Classification · Module A"
- Content:
  - Two-column comparison: **e2open original** vs **AI recommendation**
  - Each shows: HS code (`.mono`), description
  - Conflict indicator: amber "⚠ Disagrees" or teal "✓ Agrees"
  - Confidence bar (same `.conf-bar-wrap` pattern as `app.js`)
  - Expandable AI reasoning block (`.expand-toggle` / `.expand-body`)
  - RAG sources list (same pattern as `renderModuleACard` in `app.js`)

### Module B Card (`.det-card`)
- Header: "FTA Match · Module B"
- Shows: best FTA name + rate, MFN rate, duty saving
- If no FTA: "No FTA available for this origin" in muted text
- Reuses `.savings-badge`, `.rate-compare` classes

### Module C Card (`.det-card`)
- Header: "Landed Cost · Module C"
- Shows: CIF MYR, customs duty, sales tax, processing fee, total USD
- LMW chip if applicable
- Reuses `.formula-row`, `.formula-total` classes from Module C implementation

### Sticky Action Bar
Fixed to bottom of detail panel. Three actions:

| Button | Style | Behaviour |
|--------|-------|-----------|
| ✓ Approve | `.btn-primary` (teal override) | POST `/api/shipments/{id}/approve` + audit log |
| ✎ Edit HS Code | `.btn` (blue tint) | Expands inline edit form (see §5) |
| ↑ Escalate | `.btn` (amber tint) | Expands inline escalation form (see §5) |

After any action: item in queue updates status, auto-advances to next unreviewed item.

---

## 5. Inline Action Forms

Both forms expand within the action bar area (push content up, no modal).

### Edit HS Code Form
```
┌────────────────────────────────────────┐
│ Override HS Code                       │
│ Current (AI): [8542.31]               │
│ New HS Code:  [___________]  ← input  │
│ Reason *:     [_________________________│
│               ______________] ← textarea│
│ [Cancel]  [Save Override]              │
└────────────────────────────────────────┘
```
- Reason is mandatory (form validates before submit)
- On submit: POST `/api/shipments/{id}/override-hs` with `{hs_code, reason}`
- Writes `analyst_override_hs` to `hs_classifications` table
- Writes audit entry: `"Analyst overrode HS to {code}: {reason}"`

### Escalate Form
```
┌────────────────────────────────────────┐
│ Escalate to Senior Analyst             │
│ Assign to: [James Tan ▼]              │
│ Notes *:   [_________________________  │
│             _______________] ← textarea│
│ [Cancel]  [Escalate]                  │
└────────────────────────────────────────┘
```
- Notes mandatory
- On submit: POST `/api/shipments/{id}/flag` + audit entry with notes
- Status → "flagged", badge updates in queue

---

## 6. API Endpoints (new)

All in `backend/api/routes.py`:

```
POST /api/shipments/{shipment_id}/override-hs
Body: { "hs_code": "8542.31", "reason": "Confirmed by supplier datasheet" }
→ Updates hs_classifications.analyst_override_hs
→ Inserts audit_trail row

POST /api/shipments/{shipment_id}/escalate
Body: { "assignee": "James Tan", "notes": "..." }
→ Sets shipment.status = "flagged"
→ Inserts audit_trail row
```

`/api/shipments/{id}/approve` already exists — reuse it.

---

## 7. Navigation Integration

Add "Validation" nav item to the sidebar in `index.html`, `shipments.html`, `audit.html`, `fta-library.html`, `reports.html`:
```html
<a class="nav-item" href="verification.html">
  <i class="ti ti-shield-check"></i> Validation
  <span class="nav-badge warn" id="pendingCount">—</span>
</a>
```
Badge shows count of unreviewed items (loaded via `fetchShipments` on page load).

---

## 8. Data Flow

```
verification.html loads
  → fetchShipments() → GET /api/shipments
  → builds queue from s.hs_classifications[0].module_a_status + s.status
  → renders left panel
  → if ?id= query param present: auto-select that item and scroll it into view

Analyst selects item
  → fetchShipmentDetail(id) → GET /api/shipments/{id}
  → renderDetailPanel(data)

Analyst takes action
  → approveShipment(id) / overrideHS(id, data) / escalateShipment(id, data)
  → on success: update queue item status, advance to next pending item
  → reload summary counts
```

### Deep-link from `shipments.html`

Row click in `shipments.html` navigates to `verification.html?id=SHIP001`.
On load, `verification.js` reads `new URLSearchParams(window.location.search).get('id')`,
finds that item in the queue, auto-selects it, and loads its detail in the right panel.
This is the same deep-link pattern used in `app.js` (`index.html?id=SHIP001`).

---

## 9. Auto-Advance Logic

After any action (approve / edit / escalate):
1. Mark item in local state as reviewed
2. Find next item in queue with status "pending"
3. Auto-select it (scroll into view)
4. If no more pending: show completion state — "All items reviewed. Ready for SAP submission."

---

## 10. Completion State

When all items are reviewed:
- Right panel shows a summary card:
  - Total approved / overridden / escalated counts
  - "Submit to SAP" primary button (calls existing batch submit flow)
  - Export audit trail CSV link

---

## 11. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Backend offline | Show `.error` toast, queue shows skeleton placeholders |
| Module A/B/C not yet run for an item | Queue item shows "Pipeline incomplete" badge; detail panel shows "Run modules first" instead of data |
| Override HS with empty reason | Form validation blocks submit, field highlighted in red |
| Escalation without notes | Same validation |
| Approve all via bulk with 0 eligible items | Bulk button disabled |
