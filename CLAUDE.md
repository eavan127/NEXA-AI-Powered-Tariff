# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NEXA is an AI-powered tariff calculation dashboard built for trade compliance teams. It implements a **3-module human-in-the-loop pipeline**: HS code classification → FTA qualification → landed cost calculation, with an immutable audit trail.

## Commands

### Frontend (no build step)
```bash
# Serve locally (avoids CORS issues with API calls)
python -m http.server 8080
# Then open http://localhost:8080
```

### Backend
```bash
cd backend

# First-time setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Start Ollama (separate terminal, required for Module A)
ollama serve
ollama pull nomic-embed-text

# Run FastAPI dev server
uvicorn main:app --reload      # http://localhost:8000

# Seed the database with sample data
curl -X POST http://localhost:8000/api/seed

# Health check
curl http://localhost:8000/api/health
```

### Tests
```bash
cd backend
pytest tests/test_landed_cost.py          # Unit tests for Module C
python scripts/reset_and_run_pipeline.py  # End-to-end pipeline test
python scripts/embed_hs_reference.py      # Rebuild pgvector embeddings
```

## Architecture

### 3-Module Pipeline

Each shipment flows through three sequential modules, all results stored in Supabase:

**Module A — HS Classification** (`backend/classifier/hs_classifier.py`)
- Uses Ollama (nomic-embed-text model) to embed product descriptions
- Performs pgvector semantic search against the `hs_reference` table
- Outputs: `final_hs_code`, `confidence_score` (0–1), `reasoning_text`

**Module B — FTA Matching** (`backend/calculator/fta_matcher.py`)
- Takes Module A's HS code + origin country
- Applies RVC (Regional Value Content) and tariff-shift rules per FTA agreement
- Compares MFN rate vs. preferential FTA rates to find maximum saving
- Outputs: `best_fta_name`, `best_fta_rate_pct`, `mfn_rate_pct`, `roo_passed`

**Module C — Landed Cost** (`backend/calculator/landed_cost.py`)
- Calculates duty from CIF value × duty rate
- Applies LMW (Licensed Manufacturing Warehouse) exemptions for eligible shipments
- Adds anti-dumping duties (origin-specific), sales tax (10%), and handling fees
- Outputs `cost_breakdown` as JSONB (formula annotations per line item), `fta_saving_usd`

### Data Flow
```
SAP S/4HANA (OData) → FastAPI → Module A → Module B → Module C → Supabase
                                                                       ↓
                                              Analyst reviews in verification.html
                                                                       ↓
                                              Approved → SAP writeback via sap_submitter.py
```

### Frontend Architecture
Five HTML pages, all served statically with no build tooling:
- `index.html` / `js/app.js` — Shipment lookup, Module A/B/C drill-down viewer
- `verification.html` / `js/verification.js` — Analyst queue, approve/edit/escalate actions
- `shipments.html` / `js/shipments.js` — Read-only batch monitoring
- `audit.html` / `js/audit.js` — Immutable compliance audit log
- `reports.html` / `js/reports.js` — KPI dashboards

`js/api.js` is the shared HTTP client for all backend calls. `js/shared.js` contains formatters (money, percentage, confidence colors). `js/data.js` holds 50-item sample data for offline use.

### Backend Structure
```
backend/
├── main.py          # FastAPI app init + Supabase client
├── config.py        # Pydantic Settings (reads .env)
├── scheduler.py     # APScheduler cron jobs
├── api/
│   ├── routes.py    # All /api/* endpoints
│   └── schemas.py   # Pydantic request/response models
├── classifier/      # Module A
├── calculator/      # Modules B, C, and SAP writeback
└── ingestion/       # Background data sync (tariffs, FTA rates, gazette)
```

### Database Schema (Supabase/PostgreSQL)
Eight tables. Key relationships:
- `shipments` (1) → `hs_classifications` (1) → `fta_results` (1) → `landed_costs` (1)
- `audit_trail` (many) ← `shipments` — every analyst action appended, never updated
- `hs_reference` has a `vector` column (pgvector) used by Module A semantic search
- `cost_breakdown` in `landed_costs` is JSONB with per-line-item formula objects

## Key Configuration

**Environment variables** (`.env` at repo root — not committed):
| Variable | Purpose |
|---|---|
| `SUPABASE_URL` / `SUPABASE_KEY` | Database connection |
| `OLLAMA_BASE_URL` | Local LLM (default: `http://localhost:11434`) |
| `SAP_MOCK=True` | Skip real SAP calls (use mock responses) |
| `E2OPEN_MOCK=True` | Skip real E2open calls |

When `SAP_MOCK=True` and `E2OPEN_MOCK=True`, the backend runs fully without external integrations.

## Design System

CSS variables defined in `css/styles.css`:
- `--coral: #cc785c` — primary CTA, selected state
- `--teal: #5db8a6` — success / approved
- `--amber: #e8a55a` — warning / mid-confidence
- `--error: #c64545` — flags / low-confidence
- `--canvas: #faf9f5` — warm cream background
- Fonts: Cormorant Garamond (display headings), Inter (body), JetBrains Mono (HS codes/values)

Confidence thresholds used across both frontend and backend: ≥0.85 = high (teal), 0.65–0.84 = medium (amber), <0.65 = low (error/coral).

## API Endpoints Reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/shipments` | List all with nested A/B/C results |
| GET | `/api/shipments/{id}` | Detail + audit trail |
| POST | `/api/classify/{id}` | Run Module A |
| POST | `/api/match-fta/{id}` | Run Module B |
| POST | `/api/calculate-landed-cost/{id}` | Run Module C |
| POST | `/api/approve` | Approve + write audit entry |
| POST | `/api/override-hs` | Analyst HS code correction |
| POST | `/api/escalate` | Flag for escalation |
| POST | `/api/submit-batch` | Batch SAP writeback |
| GET | `/api/reports/summary` | KPI aggregations |
| POST | `/api/seed` | Load sample data |
