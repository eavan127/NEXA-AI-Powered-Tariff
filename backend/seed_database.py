import httpx
import json 
from supabase import create_client 
from config import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# mock data

SAMPLE_SHIPMENTS = [
    {
        # SCENARIO 1 — Multiple FTAs qualify (ATIGA + RCEP both apply)
        # Origin: Vietnam → member of both ATIGA and RCEP
        # RVC: 62% → passes both thresholds (40%)
        # Expected result: ATIGA or RCEP chosen (both 0%), MFN=5%, saving=5%×CIF
        "sap_shipment_id":     "SHIP001",
        "product_description": "Printed Circuit Board Assembly",
        "shipment_value_usd":  15000,
        "freight_cost_usd":    200,
        "insurance_cost_usd":  50,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    62.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "PCB"},
            {"hs_code": "8541.10", "description": "Diode"}
        ],
        "status": "pending"
    },
    {
        # SCENARIO 2 — RVC too low, FTA fails, fallback to MFN
        # Origin: China → member of ACFTA and RCEP
        # RVC: 28% → FAILS both thresholds (40% required)
        # Expected result: No FTA qualifies → MFN rate applied
        "sap_shipment_id":     "SHIP002",
        "product_description": "Industrial Servo Motor",
        "shipment_value_usd":  8500,
        "freight_cost_usd":    150,
        "insurance_cost_usd":  30,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    28.0,
        "bom_items": [
            {"hs_code": "8501.52", "description": "Motor"},
            {"hs_code": "8537.10", "description": "Controller"}
        ],
        "status": "pending"
    },
    {
        # SCENARIO 3 — Tariff shift rule (not RVC), always qualifies
        # Origin: Vietnam → RCEP member, HS 7604.29 uses tariff_shift rule
        # Tariff shift: no RVC check needed, rule is met by default in POC
        # Expected result: RCEP applies, saving calculated
        "sap_shipment_id":     "SHIP003",
        "product_description": "Aluminium Heatsink Extrusion",
        "shipment_value_usd":  3200,
        "freight_cost_usd":    80,
        "insurance_cost_usd":  15,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    0.0,
        "bom_items": [
            {"hs_code": "7604.29", "description": "Aluminium profile"}
        ],
        "status": "pending"
    },
    {
        # SCENARIO 4 — No FTA at all (origin country not in any FTA with Malaysia)
        # Origin: Taiwan → NOT a member of any Malaysian FTA
        # Expected result: Straight MFN rate, no FTA saving, flagged for analyst
        "sap_shipment_id":     "SHIP004",
        "product_description": "DRAM Memory Module DDR5",
        "shipment_value_usd":  18000,
        "freight_cost_usd":    60,
        "insurance_cost_usd":  10,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    0.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "Integrated circuit"}
        ],
        "status": "flagged"
    },
    {
        # SCENARIO 5 — RVC borderline: exactly at threshold (edge case)
        # Origin: South Korea → AKFTA member, threshold = 40%
        # RVC: 40.0% → exactly meets threshold → PASSES (>=)
        # Expected result: AKFTA qualifies, preferential rate applied
        "sap_shipment_id":     "SHIP005",
        "product_description": "Optical Lens Assembly",
        "shipment_value_usd":  22000,
        "freight_cost_usd":    300,
        "insurance_cost_usd":  80,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    40.0,
        "bom_items": [
            {"hs_code": "9001.90", "description": "Optical element"}
        ],
        "status": "pending"
    }
]

# HS reference data (WCO descriptions)
HS_REFERENCE_DATA = [
    {
        "hs_code": "8534.00",
        "description": "Printed circuits",
        "explanatory_notes": "Printed circuits consist of a base of insulating material with a conductive pattern of copper, aluminium or other metal deposited or printed on one or both surfaces. Used in electronic assemblies, computers, telecommunications equipment.",
        "source": "WCO"
    },
    {
        "hs_code": "8501.52",
        "description": "AC motors, multi-phase, of an output exceeding 750W but not exceeding 75kW",
        "explanatory_notes": "Multi-phase AC motors used in industrial machinery, servo drives, conveyor systems. Includes synchronous and asynchronous motors with electronic speed control.",
        "source": "WCO"
    },
    {
        "hs_code": "7408.11",
        "description": "Copper wire, refined copper, with maximum cross-sectional dimension exceeding 6mm",
        "explanatory_notes": "Refined copper wire used in electrical wiring, cable assemblies, motor windings. High conductivity electrolytic copper.",
        "source": "WCO"
    },
    {
        "hs_code": "7604.29",
        "description": "Aluminium alloy bars, rods and profiles",
        "explanatory_notes": "Extruded aluminium alloy profiles used in heat dissipation, structural components, enclosures. Includes heatsinks and thermal management components.",
        "source": "WCO"
    },
    {
        "hs_code": "9001.90",
        "description": "Optical fibres, optical fibre bundles, other optical elements",
        "explanatory_notes": "Optical lenses, prisms, mirrors and other optical elements of any material, unmounted. Used in cameras, microscopes, scientific instruments.",
        "source": "WCO"
    },
    {
        "hs_code": "8541.10",
        "description": "Diodes, other than photosensitive or light-emitting diodes",
        "explanatory_notes": "Semiconductor diodes used in rectification, signal processing, protection circuits. Includes Zener diodes, Schottky diodes.",
        "source": "WCO"
    },
    {
        "hs_code": "8537.10",
        "description": "Boards, panels, for voltage not exceeding 1000V",
        "explanatory_notes": "Control panels, distribution boards, switchboards for electrical control and distribution. Used in industrial automation and motor control.",
        "source": "WCO"
    },
    {
        "hs_code": "8542.31",
        "description": "Processors and controllers, electronic integrated circuits",
        "explanatory_notes": "Microprocessors, microcontrollers, digital signal processors. Core components of computing and control systems.",
        "source": "WCO"
    },
    {
        "hs_code": "8471.30",
        "description": "Portable automatic data processing machines, laptops and notebooks",
        "explanatory_notes": "Portable computers weighing not more than 10kg. Includes laptops, notebooks, tablet computers with keyboard.",
        "source": "WCO"
    },
    {
        "hs_code": "8525.80",
        "description": "Television cameras, digital cameras, video camera recorders",
        "explanatory_notes": "Image capture devices including CMOS and CCD sensors. Used in surveillance, machine vision, consumer electronics.",
        "source": "WCO"
    }
]

# generate embedding using ollama 
async def get_embedding(text:str) -> list:
    async with httpx.AsyncClient() as client:
        reponse = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=30
        )
        reponse.raise_for_status()
        return reponse.json()["embedding"]

# seed shipments 
async def seed_shipments() -> int:
    count = 0
    for shipment in SAMPLE_SHIPMENTS:
        try:
            supabase.table("shipments").upsert(
                shipment,
                on_conflict="sap_shipment_id"
            ).execute()
            count += 1
            print(f"[seed] ✓ Shipment {shipment['sap_shipment_id']}")
        except Exception as e:
            print(f"[seed] ✗ Shipment {shipment['sap_shipment_id']} failed: {e}")
    return count

# seed HS reference with embeddings
async def seed_hs_reference() -> int:
    count = 0
    for item in HS_REFERENCE_DATA:
        try:
            existing = supabase.table("hs_reference").select("id").eq(
                "hs_code", item["hs_code"]
            ).execute()

            if existing.data:
                print(f"[seed] HS {item['hs_code']} already exists, skipping")
                continue

            text_to_embed = f"{item['hs_code']} {item['description']} {item['explanatory_notes']}"
            embedding = await get_embedding(text_to_embed)

            supabase.table("hs_reference").insert({
                "hs_code":           item["hs_code"],
                "description":       item["description"],
                "explanatory_notes": item["explanatory_notes"],
                "source":            item["source"],
                "embedding":         embedding
            }).execute()

            count += 1
            print(f"[seed] ✓ HS {item['hs_code']} — {item['description'][:40]}")

        except Exception as e:
            print(f"[seed] ✗ HS {item['hs_code']} failed: {e}")

    return count

# ── Mock Module A output ─────────────────────────────────────────
# Allows Module B to be built and tested without waiting for
# Module A to be complete. When Module A is done, it overwrites these.
async def seed_mock_classifications() -> int:
    count = 0

    MOCK_CLASSIFICATIONS = [
        {
            # SHIP001 — PCB, Vietnam, high confidence, e2open agrees with AI
            "sap_id":          "SHIP001",
            "e2open_hs_code":  "8534.00",
            "ai_hs_code":      "8534.00",
            "confidence_score": 94,
            "reasoning_text":  "Description 'Printed Circuit Board Assembly' matches HS 8534.00 "
                               "(Printed circuits) with RAG similarity 0.97. HS 8542.31 rejected — "
                               "no processor component described. HS 8471.30 rejected — not a computer.",
            "rag_sources":     [
                {"hs_code": "8534.00", "similarity": 0.97, "description": "Printed circuits"},
                {"hs_code": "8542.31", "similarity": 0.71, "description": "Processors and controllers"},
                {"hs_code": "8471.30", "similarity": 0.43, "description": "Laptops and notebooks"}
            ],
            "final_hs_code":   "8534.00",
            "module_a_status": "auto_passed"
        },
        {
            # SHIP002 — Motor, China, acceptable confidence, e2open agrees
            "sap_id":          "SHIP002",
            "e2open_hs_code":  "8501.52",
            "ai_hs_code":      "8501.52",
            "confidence_score": 89,
            "reasoning_text":  "Description 'Industrial Servo Motor' matches HS 8501.52 "
                               "(AC motors, multi-phase, >750W). Confidence 89% — above 85% threshold.",
            "rag_sources":     [
                {"hs_code": "8501.52", "similarity": 0.91, "description": "AC motors multi-phase"},
                {"hs_code": "8537.10", "similarity": 0.65, "description": "Control panels"},
                {"hs_code": "8479.89", "similarity": 0.41, "description": "Industrial machines"}
            ],
            "final_hs_code":   "8501.52",
            "module_a_status": "auto_passed"
        },
        {
            # SHIP003 — Aluminium, Vietnam, high confidence
            "sap_id":          "SHIP003",
            "e2open_hs_code":  "7604.29",
            "ai_hs_code":      "7604.29",
            "confidence_score": 96,
            "reasoning_text":  "Description 'Aluminium Heatsink Extrusion' matches HS 7604.29 "
                               "(Aluminium alloy bars, rods and profiles). Heatsink extrusion is "
                               "an extruded aluminium profile — clear match.",
            "rag_sources":     [
                {"hs_code": "7604.29", "similarity": 0.96, "description": "Aluminium alloy profiles"},
                {"hs_code": "7606.12", "similarity": 0.55, "description": "Aluminium plates"},
                {"hs_code": "7608.20", "similarity": 0.38, "description": "Aluminium tubes"}
            ],
            "final_hs_code":   "7604.29",
            "module_a_status": "auto_passed"
        },
        {
            # SHIP004 — DRAM, Taiwan, e2open WRONG, AI corrects, low confidence → flagged
            "sap_id":          "SHIP004",
            "e2open_hs_code":  "8471.30",   # e2open misclassified as laptops
            "ai_hs_code":      "8542.31",   # AI corrects to ICs/memory
            "confidence_score": 82,          # below 85% → flagged for analyst
            "reasoning_text":  "e2open preliminary code 8471.30 (portable computers) REJECTED — "
                               "product is a DDR5 memory module, not a portable computer. "
                               "AI suggests 8542.31 (Electronic integrated circuits). "
                               "Confidence 82% — flagged: ambiguity between 8542.31 and 8473.30.",
            "rag_sources":     [
                {"hs_code": "8542.31", "similarity": 0.84, "description": "Processors and controllers"},
                {"hs_code": "8473.30", "similarity": 0.79, "description": "Parts for computers"},
                {"hs_code": "8471.30", "similarity": 0.61, "description": "Laptops — REJECTED"}
            ],
            "final_hs_code":   "8542.31",
            "module_a_status": "flagged_low_confidence"
        },
        {
            # SHIP005 — Optical lens, South Korea, high confidence
            "sap_id":          "SHIP005",
            "e2open_hs_code":  "9001.90",
            "ai_hs_code":      "9001.90",
            "confidence_score": 95,
            "reasoning_text":  "Description 'Optical Lens Assembly' matches HS 9001.90 "
                               "(Optical fibres, other optical elements). Strong semantic match "
                               "on optical + lens + assembly combination.",
            "rag_sources":     [
                {"hs_code": "9001.90", "similarity": 0.95, "description": "Optical elements"},
                {"hs_code": "9002.11", "similarity": 0.72, "description": "Objective lenses"},
                {"hs_code": "8525.80", "similarity": 0.44, "description": "Camera modules"}
            ],
            "final_hs_code":   "9001.90",
            "module_a_status": "auto_passed"
        }
    ]

    for mock in MOCK_CLASSIFICATIONS:
        try:
            ship = supabase.table("shipments").select("id").eq(
                "sap_shipment_id", mock["sap_id"]
            ).execute()

            if not ship.data:
                print(f"[seed] Shipment {mock['sap_id']} not found, skipping")
                continue

            shipment_id = ship.data[0]["id"]

            existing = supabase.table("hs_classifications").select("id").eq(
                "shipment_id", shipment_id
            ).execute()

            if existing.data:
                print(f"[seed] Classification for {mock['sap_id']} already exists, skipping")
                continue

            supabase.table("hs_classifications").insert({
                "shipment_id":      shipment_id,
                "e2open_hs_code":   mock["e2open_hs_code"],
                "ai_hs_code":       mock["ai_hs_code"],
                "confidence_score": mock["confidence_score"],
                "reasoning_text":   mock["reasoning_text"],
                "rag_sources":      mock["rag_sources"],
                "final_hs_code":    mock["final_hs_code"],
                "module_a_status":  mock["module_a_status"]
            }).execute()

            count += 1
            print(f"[seed] ✓ Mock classification {mock['sap_id']} "
                  f"→ HS {mock['ai_hs_code']} ({mock['confidence_score']}%) "
                  f"[{mock['module_a_status']}]")

        except Exception as e:
            print(f"[seed] ✗ Mock classification {mock['sap_id']} failed: {e}")

    return count


# ── Additional FTA rates + RoO rules for all 5 test scenarios ────
async def seed_additional_fta_data() -> None:

    additional_rates = [
        # SHIP001 — Vietnam, HS 8534.00 — ATIGA + RCEP both apply
        {"fta_name": "ATIGA", "hs_code": "8534.00", "preferential_rate_pct": 0.0, "origin_country": "Vietnam",      "effective_date": "2024-01-01"},
        {"fta_name": "RCEP",  "hs_code": "8534.00", "preferential_rate_pct": 0.0, "origin_country": "Vietnam",      "effective_date": "2024-01-01"},
        # SHIP002 — China, HS 8501.52 — ACFTA + RCEP, but RVC too low (28%)
        {"fta_name": "ACFTA", "hs_code": "8501.52", "preferential_rate_pct": 0.0, "origin_country": "China",        "effective_date": "2024-01-01"},
        {"fta_name": "RCEP",  "hs_code": "8501.52", "preferential_rate_pct": 5.0, "origin_country": "China",        "effective_date": "2024-01-01"},
        {"fta_name": "PDK",   "hs_code": "8501.52", "preferential_rate_pct": 5.0, "origin_country": "MFN",          "effective_date": "2024-01-01"},
        # SHIP003 — Vietnam, HS 7604.29 — ATIGA + RCEP tariff shift
        {"fta_name": "ATIGA", "hs_code": "7604.29", "preferential_rate_pct": 0.0, "origin_country": "Vietnam",      "effective_date": "2024-01-01"},
        {"fta_name": "RCEP",  "hs_code": "7604.29", "preferential_rate_pct": 0.0, "origin_country": "Vietnam",      "effective_date": "2024-01-01"},
        # SHIP004 — Taiwan, HS 8542.31 — no FTA, MFN only
        {"fta_name": "PDK",   "hs_code": "8542.31", "preferential_rate_pct": 5.0, "origin_country": "MFN",          "effective_date": "2024-01-01"},
        # SHIP005 — South Korea, HS 9001.90 — AKFTA (0%) + RCEP (3%)
        {"fta_name": "RCEP",  "hs_code": "9001.90", "preferential_rate_pct": 3.0, "origin_country": "South Korea",  "effective_date": "2024-01-01"},
        {"fta_name": "PDK",   "hs_code": "9001.90", "preferential_rate_pct": 5.0, "origin_country": "MFN",          "effective_date": "2024-01-01"},
    ]

    additional_roo = [
        # SHIP001 — ATIGA + RCEP RVC rules for 8534.00
        {"fta_name": "ATIGA", "hs_code": "8534.00", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
        {"fta_name": "RCEP",  "hs_code": "8534.00", "roo_type": "RVC",          "rvc_threshold_pct": 35.0},
        # SHIP002 — ACFTA + RCEP RVC rules for 8501.52
        {"fta_name": "ACFTA", "hs_code": "8501.52", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
        {"fta_name": "RCEP",  "hs_code": "8501.52", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
        # SHIP003 — ATIGA tariff shift for 7604.29
        {"fta_name": "ATIGA", "hs_code": "7604.29", "roo_type": "tariff_shift", "tariff_shift_description": "CTH — Change in Tariff Heading from Chapter 76 raw inputs"},
        # SHIP005 — RCEP RVC for 9001.90
        {"fta_name": "RCEP",  "hs_code": "9001.90", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
        # AKFTA for 9001.90 already in fta_scraper seed
        {"fta_name": "AKFTA", "hs_code": "9001.90", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
    ]

    try:
        for rate in additional_rates:
            supabase.table("fta_rates").upsert(
                rate, on_conflict="fta_name,hs_code,origin_country"
            ).execute()
        print("[seed] ✓ Additional FTA rates seeded")
    except Exception as e:
        print(f"[seed] Additional FTA rates failed: {e}")

    try:
        for rule in additional_roo:
            supabase.table("roo_rules").upsert(
                rule, on_conflict="fta_name,hs_code"
            ).execute()
        print("[seed] ✓ Additional RoO rules seeded")
    except Exception as e:
        print(f"[seed] Additional RoO rules failed: {e}")


# main seed function
async def run_seed() -> dict:
    print("\n[seed] Starting database seed...")

    shipments_count = await seed_shipments()
    print(f"[seed] Shipments: {shipments_count} seeded")

    hs_count = await seed_hs_reference()
    print(f"[seed] HS reference: {hs_count} seeded with embeddings")

    try:
        from ingestion.tariff_sync import seed_tariff_data
        await seed_tariff_data()
        print("[seed] Tariff rates seeded")
    except Exception as e:
        print(f"[seed] Tariff seed failed: {e}")

    try:
        from ingestion.fta_scraper import seed_fta_data
        await seed_fta_data()
        print("[seed] FTA data seeded")
    except Exception as e:
        print(f"[seed] FTA seed failed: {e}")

    await seed_additional_fta_data()

    print("[seed] Database seed complete!\n")

    return {
        "shipments":    shipments_count,
        "hs_reference": hs_count,
        "tariff_rates": "seeded",
        "fta_data":     "seeded"
    }

