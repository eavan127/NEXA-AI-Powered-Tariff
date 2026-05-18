# NEXA — AI-Powered Tariff Calculation Engine

> **Jabil IT ECP Bootcamp 3.0 · Use Case 2**  
> Data & AI Innovation — "How Can We Tango with AI?"

A proof-of-concept (POC) frontend for Jabil's AI-powered tariff calculation system, designed for the Global Trade Compliance department. This dashboard replaces an 8-step manual workflow with an AI-assisted, human-validated process — reducing batch processing time by 98% while maintaining mandatory analyst sign-off.

---

## Project Structure

```
NEXA-AI-Powered-Tariff/
├── index.html          ← Main dashboard entry point
├── css/
│   └── styles.css      ← Design system & component styles
├── js/
│   ├── data.js         ← Shipment items dataset (15 sample items)
│   └── app.js          ← UI logic: rendering, filtering, modals
├── assets/             ← (reserved for future images/icons)
└── README.md
```

---

## Features

| Feature | Description |
|---|---|
| **Batch Processing Table** | 50-item shipment list with HS code, confidence score, duty amount, and FTA match |
| **AI Confidence Dots** | Visual indicator (green/amber/red) showing AI classification certainty |
| **FTA Match Analysis** | Compares CPTPP, ATIGA, and MFN rates — highlights best available preferential duty |
| **Landed Cost Breakdown** | Import duty + SST + customs fee + freight + insurance |
| **AI Reasoning Log** | Explains why each HS code was chosen — with flagged ambiguities |
| **Approve / Edit / Escalate** | Analyst actions before any figure is written to SAP |
| **Bulk Approve** | One-click approval for all items ≥95% confidence |
| **Immutable Audit Trail** | Timestamped, analyst-tagged log of every action |
| **Live Regulatory Feed** | CPTPP Year 8, USTR Section 301, JKDM, MITI alerts |
| **Submit Batch Modal** | Confirmation screen before SAP S/4HANA writeback |

---

## Use Case Summary

**Problem:** Trade Compliance Analysts at Jabil perform an 8-step manual process per shipment item — costing 12.5 hours per 50-item batch, with $2,500 financial error exposure.

**Solution:** AI Tariff Calculation Engine as middleware between SAP S/4HANA and e2open GTM:
1. **Ingest** — pulls shipment data from SAP via OData API
2. **Classify** — NLP model validates HS codes (confidence scored)
3. **Match** — evaluates all 17 Malaysian FTAs for best preferential rate
4. **Calculate** — computes full landed cost
5. **Review** — analyst validates via dashboard (mandatory human sign-off)
6. **Submit** — approved figures written back to SAP with audit trail

**Result:**
- 98% reduction in processing time (12.5 h → ~15 min analyst review)
- 75% fewer manual steps (8 steps → ≤2 per item)
- $2,000 saved per batch in error exposure reduction

---

## Design System

Built following the Anthropic/Claude design language (`DESIGN.md`):

- **Canvas:** Warm cream `#faf9f5` — not pure white
- **Primary CTA:** Coral `#cc785c` — used sparingly (buttons, selected states)
- **Display type:** Cormorant Garamond (serif, 400 weight, negative tracking)
- **Body/UI type:** Inter (sans-serif)
- **Monospace:** JetBrains Mono (HS codes, duty values, timestamps)
- **Accent colors:** Teal (success/FTA), Amber (warning/escalate), Error red (flagged)

---

## How to Run

No build step required — plain HTML/CSS/JS.

```bash
# Option 1: Open directly
open index.html

# Option 2: Local dev server (recommended to avoid CORS on file://)
npx serve .
# or
python -m http.server 8080
```

Then visit `http://localhost:8080` in your browser.

---

## Judges' Note

This POC demonstrates:
- **Human-in-the-loop** design — no duty figure reaches SAP without analyst approval
- **Explainability** — every AI decision includes a reasoning log
- **Governance** — immutable audit trail for FCA compliance defence
- **Tango Principle** — AI leads the calculation, analyst leads the decision

---

## Team

**NEXA** · Jabil IT ECP Bootcamp 3.0  
Use Case 2 — Tariff Calculation Automation  
Day 1 Pitch: 24 June 2026 · Day 2 Final: 2 July 2026 @ Amari Hotel
