import httpx
import json 
from supabase import create_client 
from config import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# mock data

SAMPLE_SHIPMENTS = [
    {
        "sap_shipment_id":    "SHIP001",
        "product_description": "Printed Circuit Board Assembly",
        "shipment_value_usd":  15000,
        "freight_cost_usd":    200,
        "insurance_cost_usd":  50,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "bom_items": [
            {"hs_code": "8534.00", "description": "PCB"},
            {"hs_code": "8541.10", "description": "Diode"}
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":    "SHIP002",
        "product_description": "Industrial Servo Motor",
        "shipment_value_usd":  8500,
        "freight_cost_usd":    150,
        "insurance_cost_usd":  30,
        "destination_country": "Malaysia",
        "origin_country":      "Japan",
        "bom_items": [
            {"hs_code": "8501.52", "description": "Motor"},
            {"hs_code": "8537.10", "description": "Controller"}
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":    "SHIP003",
        "product_description": "Copper Wire Harness",
        "shipment_value_usd":  3200,
        "freight_cost_usd":    80,
        "insurance_cost_usd":  15,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "bom_items": [
            {"hs_code": "7408.11", "description": "Copper wire"}
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":    "SHIP004",
        "product_description": "Aluminium Heatsink Extrusion",
        "shipment_value_usd":  1800,
        "freight_cost_usd":    60,
        "insurance_cost_usd":  10,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "bom_items": [
            {"hs_code": "7604.29", "description": "Aluminium profile"}
        ],
        "status": "flagged"
    },
    {
        "sap_shipment_id":    "SHIP005",
        "product_description": "Optical Lens Assembly",
        "shipment_value_usd":  22000,
        "freight_cost_usd":    300,
        "insurance_cost_usd":  80,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
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
            json={"model": "nomic-embed-text", "input": text},
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

    print("[seed] Database seed complete!\n")

    return {
        "shipments": shipments_count,
        "hs_reference": hs_count,
        "tariff_rates": "seeded",
        "fta_data": "seeded"
    }

