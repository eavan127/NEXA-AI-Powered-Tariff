import httpx
import json
from supabase import create_client
from config import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# ── 50 shipments — 4 origins, 5 HS families ─────────────────────
# Origins: Vietnam (ATIGA+RCEP), China (ACFTA+RCEP),
#          Taiwan (MFN/ITA only — no FTA with Malaysia),
#          South Korea (AKFTA+RCEP)
#
# HS codes (updated to match JKDM sub-codes):
#   8534.00 → 8534001000  single-sided PCB           (Vietnam)
#   7604.29 → 7604291000  aluminium extruded bars    (Vietnam)
#   8501.10 → 8501103000  spindle motors DC          (China)   ← was 8501.52
#   8542.31 → 8542319000  electronic ICs/memory      (Taiwan, MFN only)
#   9001.90 → 9001901000  optical lens camera/proj   (South Korea)
#
# Rate sources (real values from JKDM ezhs.customs.gov.my):
#   RCEP  8534.00 = 0.0%   | RCEP  7604.29 = 25.0%  | RCEP  8501.10 = 0.0%
#   RCEP  9001.90 = 0.0%   | ACFTA 8501.10 = 0.0%   | AKFTA 9001.90 = 0.0%
#   ATIGA 8534.00 = 0.0%   | ATIGA 7604.29 = 0.0%   ← hardcoded (MITI down)
#   PDK   7604.29 = 25.0%  | PDK   8534.00 = 0.0%   | PDK   8542.31 = 0.0%
#   MFN   8542.31 = 0.0%   (ITA — WTO Information Technology Agreement)

SAMPLE_SHIPMENTS = [

    # ── VIETNAM → MALAYSIA — PCB / 8534.00 (SHIP001–SHIP010) ─────
    {
        "sap_shipment_id":     "SHIP001",
        "product_description": "Single-Sided Printed Circuit Board — Standard",
        "shipment_value_usd":  15000,
        "freight_cost_usd":    200,
        "insurance_cost_usd":  50,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    62.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB",
             "quantity": 50, "unit_value_usd": 240.00, "weight_kg": 0.8},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP002",
        "product_description": "Single-Sided PCB — Power Distribution Board",
        "shipment_value_usd":  21000,
        "freight_cost_usd":    260,
        "insurance_cost_usd":  65,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    58.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB power",
             "quantity": 35, "unit_value_usd": 520.00, "weight_kg": 1.1},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP003",
        "product_description": "Single-Sided PCB — Sensor Interface Board",
        "shipment_value_usd":  9500,
        "freight_cost_usd":    140,
        "insurance_cost_usd":  30,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    45.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB sensor",
             "quantity": 80, "unit_value_usd": 110.00, "weight_kg": 0.4},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP004",
        "product_description": "Single-Sided PCB — RF Signal Board",
        "shipment_value_usd":  17500,
        "freight_cost_usd":    220,
        "insurance_cost_usd":  55,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    51.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB RF signal",
             "quantity": 25, "unit_value_usd": 660.00, "weight_kg": 0.6},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP005",
        "product_description": "Single-Sided PCB — LED Driver Board",
        "shipment_value_usd":  4200,
        "freight_cost_usd":    70,
        "insurance_cost_usd":  12,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    35.0,   # FAILS RVC (35 < 40)
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB LED driver",
             "quantity": 200, "unit_value_usd": 18.00, "weight_kg": 0.1},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP006",
        "product_description": "Single-Sided PCB — Motor Controller Board",
        "shipment_value_usd":  11200,
        "freight_cost_usd":    160,
        "insurance_cost_usd":  40,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    72.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB motor controller",
             "quantity": 60, "unit_value_usd": 170.00, "weight_kg": 0.9},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP007",
        "product_description": "Single-Sided PCB — Industrial Control Board",
        "shipment_value_usd":  8800,
        "freight_cost_usd":    130,
        "insurance_cost_usd":  25,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    48.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB industrial control",
             "quantity": 40, "unit_value_usd": 195.00, "weight_kg": 0.7},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP008",
        "product_description": "Single-Sided PCB — IoT Communication Board",
        "shipment_value_usd":  13600,
        "freight_cost_usd":    185,
        "insurance_cost_usd":  45,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    30.0,   # FAILS RVC (30 < 40)
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB IoT communication",
             "quantity": 45, "unit_value_usd": 280.00, "weight_kg": 0.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP009",
        "product_description": "Single-Sided PCB — Power Management Board",
        "shipment_value_usd":  6700,
        "freight_cost_usd":    100,
        "insurance_cost_usd":  20,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    55.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB power management",
             "quantity": 30, "unit_value_usd": 210.00, "weight_kg": 0.4},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP010",
        "product_description": "Single-Sided PCB — Automotive Grade Board",
        "shipment_value_usd":  28500,
        "freight_cost_usd":    350,
        "insurance_cost_usd":  90,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    65.0,
        "bom_items": [
            {"hs_code": "8534.00", "description": "single-sided printed circuit board PCB automotive grade",
             "quantity": 20, "unit_value_usd": 1350.00, "weight_kg": 1.5},
        ],
        "status": "pending"
    },

    # ── VIETNAM → MALAYSIA — Aluminium / 7604.29 (SHIP011–SHIP020) ─
    # NOTE: RCEP rate = 25% (real from JKDM), ATIGA = 0% (mature ASEAN FTA)
    # Module B will prefer ATIGA (0%) over RCEP (25%) for Vietnam shipments
    {
        "sap_shipment_id":     "SHIP011",
        "product_description": "Aluminium Alloy Extruded Bar — Heatsink Profile",
        "shipment_value_usd":  3200,
        "freight_cost_usd":    80,
        "insurance_cost_usd":  15,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    28.0,   # FAILS RVC (28 < 40); CTSH review needed
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile heatsink",
             "quantity": 100, "unit_value_usd": 28.00, "weight_kg": 0.8},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP012",
        "product_description": "Aluminium Alloy Extruded Profile — LED Heatsink",
        "shipment_value_usd":  2100,
        "freight_cost_usd":    55,
        "insurance_cost_usd":  10,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    32.0,   # FAILS
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile LED heatsink",
             "quantity": 150, "unit_value_usd": 12.50, "weight_kg": 0.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP013",
        "product_description": "Aluminium Alloy Extruded Profile — Structural Rail",
        "shipment_value_usd":  4800,
        "freight_cost_usd":    95,
        "insurance_cost_usd":  18,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    42.0,   # PASSES
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile structural rail",
             "quantity": 80, "unit_value_usd": 55.00, "weight_kg": 1.2},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP014",
        "product_description": "Aluminium Alloy Extruded Bar — Enclosure Profile",
        "shipment_value_usd":  5600,
        "freight_cost_usd":    110,
        "insurance_cost_usd":  22,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    25.0,   # FAILS
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile enclosure",
             "quantity": 200, "unit_value_usd": 26.00, "weight_kg": 0.7},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP015",
        "product_description": "Aluminium Alloy Extruded Bar — Fin Array Profile",
        "shipment_value_usd":  3900,
        "freight_cost_usd":    85,
        "insurance_cost_usd":  16,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    44.0,   # PASSES
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile fin array",
             "quantity": 120, "unit_value_usd": 30.00, "weight_kg": 0.9},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP016",
        "product_description": "Aluminium Alloy Extruded Bar — Bracket Profile",
        "shipment_value_usd":  2700,
        "freight_cost_usd":    65,
        "insurance_cost_usd":  12,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    38.0,   # FAILS (38 < 40)
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile bracket",
             "quantity": 90, "unit_value_usd": 28.00, "weight_kg": 0.6},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP017",
        "product_description": "Aluminium Alloy Extruded Profile — T-Slot Frame",
        "shipment_value_usd":  1800,
        "freight_cost_usd":    45,
        "insurance_cost_usd":  8,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    50.0,   # PASSES
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile T-slot frame",
             "quantity": 60, "unit_value_usd": 28.00, "weight_kg": 0.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP018",
        "product_description": "Aluminium Alloy Extruded Profile — Liquid Cooling Plate",
        "shipment_value_usd":  6200,
        "freight_cost_usd":    120,
        "insurance_cost_usd":  24,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    22.0,   # FAILS
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile cold plate liquid cooling",
             "quantity": 50, "unit_value_usd": 116.00, "weight_kg": 1.8},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP019",
        "product_description": "Aluminium Alloy Extruded Bar — DIN Rail Profile",
        "shipment_value_usd":  1500,
        "freight_cost_usd":    40,
        "insurance_cost_usd":  7,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    48.0,   # PASSES
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile DIN rail",
             "quantity": 300, "unit_value_usd": 4.80, "weight_kg": 0.3},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP020",
        "product_description": "Aluminium Alloy Extruded Bar — 6063-T5 Grade",
        "shipment_value_usd":  2400,
        "freight_cost_usd":    60,
        "insurance_cost_usd":  11,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    40.0,   # PASSES (exactly at threshold)
        "bom_items": [
            {"hs_code": "7604.29", "description": "aluminium alloy extruded bar rod profile 6063 grade",
             "quantity": 400, "unit_value_usd": 5.50, "weight_kg": 2.0},
        ],
        "status": "pending"
    },

    # ── CHINA → MALAYSIA — Spindle Motors / 8501.10 (SHIP021–SHIP030) ─
    # HS changed from 8501.52 to 8501.10 (spindle motors, 8501103000)
    # ACFTA = 0%, RCEP = 0% from JKDM real data
    {
        "sap_shipment_id":     "SHIP021",
        "product_description": "Spindle Motor — DC Electric 500W CNC",
        "shipment_value_usd":  8500,
        "freight_cost_usd":    150,
        "insurance_cost_usd":  30,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS — no RVC certificate provided
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor 500W CNC machine",
             "quantity": 5, "unit_value_usd": 1400.00, "weight_kg": 12.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP022",
        "product_description": "Spindle Motor — DC Electric 750W Milling",
        "shipment_value_usd":  6200,
        "freight_cost_usd":    120,
        "insurance_cost_usd":  25,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor 750W milling machine",
             "quantity": 4, "unit_value_usd": 1430.00, "weight_kg": 18.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP023",
        "product_description": "Spindle Motor — DC Electric 1kW High-Speed",
        "shipment_value_usd":  11400,
        "freight_cost_usd":    180,
        "insurance_cost_usd":  40,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    42.0,   # PASSES — has RVC certificate
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor 1kW high-speed machining",
             "quantity": 6, "unit_value_usd": 1750.00, "weight_kg": 9.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP024",
        "product_description": "Spindle Motor — DC Electric Precision Grinding",
        "shipment_value_usd":  4800,
        "freight_cost_usd":    90,
        "insurance_cost_usd":  18,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor precision grinding",
             "quantity": 8, "unit_value_usd": 560.00, "weight_kg": 3.2},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP025",
        "product_description": "Spindle Motor — DC Electric Conveyor Drive",
        "shipment_value_usd":  16800,
        "freight_cost_usd":    240,
        "insurance_cost_usd":  55,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor conveyor drive",
             "quantity": 3, "unit_value_usd": 5300.00, "weight_kg": 28.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP026",
        "product_description": "Spindle Motor — DC Electric Rotary Table Drive",
        "shipment_value_usd":  22000,
        "freight_cost_usd":    290,
        "insurance_cost_usd":  70,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    45.0,   # PASSES
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor rotary table drive",
             "quantity": 4, "unit_value_usd": 5200.00, "weight_kg": 35.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP027",
        "product_description": "Spindle Motor — DC Electric Pump Drive",
        "shipment_value_usd":  9100,
        "freight_cost_usd":    155,
        "insurance_cost_usd":  32,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor pump drive",
             "quantity": 3, "unit_value_usd": 2800.00, "weight_kg": 22.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP028",
        "product_description": "Spindle Motor — DC Electric Compact Frame",
        "shipment_value_usd":  5600,
        "freight_cost_usd":    100,
        "insurance_cost_usd":  20,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    38.0,   # FAILS (38 < 40)
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor compact frame",
             "quantity": 7, "unit_value_usd": 740.00, "weight_kg": 5.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP029",
        "product_description": "Spindle Motor — DC Electric Direct Drive Torque",
        "shipment_value_usd":  31000,
        "freight_cost_usd":    380,
        "insurance_cost_usd":  95,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    52.0,   # PASSES
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor direct drive torque",
             "quantity": 2, "unit_value_usd": 14800.00, "weight_kg": 65.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP030",
        "product_description": "Spindle Motor — DC Electric with Encoder Feedback",
        "shipment_value_usd":  12600,
        "freight_cost_usd":    190,
        "insurance_cost_usd":  42,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS — no certificate
        "bom_items": [
            {"hs_code": "8501.10", "description": "spindle motor electric DC motor encoder feedback",
             "quantity": 5, "unit_value_usd": 2360.00, "weight_kg": 14.0},
        ],
        "status": "pending"
    },

    # ── TAIWAN → MALAYSIA — Memory/IC / 8542.31 (SHIP031–SHIP040) ─
    # Taiwan has NO FTA with Malaysia — MFN rate applies
    # 8542.31 is covered by WTO ITA → MFN = 0%
    {
        "sap_shipment_id":     "SHIP031",
        "product_description": "Electronic Integrated Circuit — DDR5 Memory Module 16GB",
        "shipment_value_usd":  18000,
        "freight_cost_usd":    60,
        "insurance_cost_usd":  10,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    40.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit memory chip DDR5 DRAM processor",
             "quantity": 300, "unit_value_usd": 55.00, "weight_kg": 0.05},
        ],
        "status": "flagged"
    },
    {
        "sap_shipment_id":     "SHIP032",
        "product_description": "Electronic Integrated Circuit — LPDDR5 Mobile Memory 8GB",
        "shipment_value_usd":  24500,
        "freight_cost_usd":    75,
        "insurance_cost_usd":  14,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    55.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit memory chip LPDDR5 mobile processor",
             "quantity": 500, "unit_value_usd": 48.00, "weight_kg": 0.02},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP033",
        "product_description": "Electronic Integrated Circuit — NAND Flash Storage 256GB",
        "shipment_value_usd":  19200,
        "freight_cost_usd":    65,
        "insurance_cost_usd":  12,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    48.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit NAND flash storage memory chip",
             "quantity": 400, "unit_value_usd": 47.00, "weight_kg": 0.03},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP034",
        "product_description": "Electronic Integrated Circuit — FPGA Programmable Logic",
        "shipment_value_usd":  35000,
        "freight_cost_usd":    90,
        "insurance_cost_usd":  20,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    60.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit FPGA programmable logic controller processor",
             "quantity": 100, "unit_value_usd": 340.00, "weight_kg": 0.02},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP035",
        "product_description": "Electronic Integrated Circuit — SoC Application Processor",
        "shipment_value_usd":  42000,
        "freight_cost_usd":    100,
        "insurance_cost_usd":  25,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    65.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit SoC application processor ARM chip",
             "quantity": 200, "unit_value_usd": 200.00, "weight_kg": 0.01},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP036",
        "product_description": "Electronic Integrated Circuit — DDR4 Server Memory 32GB ECC",
        "shipment_value_usd":  28800,
        "freight_cost_usd":    80,
        "insurance_cost_usd":  18,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    50.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit DDR4 server memory ECC RDIMM chip",
             "quantity": 120, "unit_value_usd": 230.00, "weight_kg": 0.08},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP037",
        "product_description": "Electronic Integrated Circuit — MCU Microcontroller 32-bit",
        "shipment_value_usd":  8400,
        "freight_cost_usd":    40,
        "insurance_cost_usd":  8,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    42.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit microcontroller MCU 32-bit ARM processor chip",
             "quantity": 1000, "unit_value_usd": 8.20, "weight_kg": 0.005},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP038",
        "product_description": "Electronic Integrated Circuit — NOR Flash Memory 64Mb",
        "shipment_value_usd":  5600,
        "freight_cost_usd":    30,
        "insurance_cost_usd":  6,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    38.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit NOR flash memory SPI chip",
             "quantity": 2000, "unit_value_usd": 2.70, "weight_kg": 0.002},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP039",
        "product_description": "Electronic Integrated Circuit — DSP Signal Processor",
        "shipment_value_usd":  16500,
        "freight_cost_usd":    55,
        "insurance_cost_usd":  12,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    58.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit DSP digital signal processor chip",
             "quantity": 150, "unit_value_usd": 106.00, "weight_kg": 0.01},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP040",
        "product_description": "Electronic Integrated Circuit — PMIC Power Management",
        "shipment_value_usd":  7200,
        "freight_cost_usd":    35,
        "insurance_cost_usd":  7,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    44.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "electronic integrated circuit PMIC power management buck converter chip",
             "quantity": 1500, "unit_value_usd": 4.70, "weight_kg": 0.003},
        ],
        "status": "pending"
    },

    # ── SOUTH KOREA → MALAYSIA — Optical / 9001.90 (SHIP041–SHIP050) ─
    # Using sub-code 9001901000 (for photographic/cinematographic cameras/projectors)
    # AKFTA = 0%, RCEP = 0% from JKDM real data
    {
        "sap_shipment_id":     "SHIP041",
        "product_description": "Optical Lens — Camera Projector Machine Vision",
        "shipment_value_usd":  22000,
        "freight_cost_usd":    300,
        "insurance_cost_usd":  80,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    40.0,   # PASSES exactly at threshold
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens element camera projector cinematographic machine vision",
             "quantity": 40, "unit_value_usd": 520.00, "weight_kg": 0.15},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP042",
        "product_description": "Optical Lens — Telecentric Camera Lens 0.5x",
        "shipment_value_usd":  18500,
        "freight_cost_usd":    260,
        "insurance_cost_usd":  65,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    45.0,
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens element telecentric camera lens projector",
             "quantity": 25, "unit_value_usd": 700.00, "weight_kg": 0.3},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP043",
        "product_description": "Optical Lens — Aspherical Laser Camera Optic",
        "shipment_value_usd":  31000,
        "freight_cost_usd":    380,
        "insurance_cost_usd":  95,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    55.0,
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens element aspherical laser camera projector optic",
             "quantity": 20, "unit_value_usd": 1480.00, "weight_kg": 0.2},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP044",
        "product_description": "Optical Prism — Beam Splitter Camera Assembly",
        "shipment_value_usd":  14200,
        "freight_cost_usd":    200,
        "insurance_cost_usd":  50,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    35.0,   # FAILS
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens prism beam splitter camera projector element",
             "quantity": 30, "unit_value_usd": 450.00, "weight_kg": 0.25},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP045",
        "product_description": "Optical Lens — Collimating Fibre Camera Coupling",
        "shipment_value_usd":  9800,
        "freight_cost_usd":    145,
        "insurance_cost_usd":  35,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    42.0,
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens element collimating fibre camera projector coupling",
             "quantity": 50, "unit_value_usd": 185.00, "weight_kg": 0.1},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP046",
        "product_description": "Optical Lens — Achromatic Doublet Microscopy Camera",
        "shipment_value_usd":  26500,
        "freight_cost_usd":    330,
        "insurance_cost_usd":  85,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    60.0,
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens element achromatic doublet microscopy camera projector",
             "quantity": 15, "unit_value_usd": 1700.00, "weight_kg": 0.4},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP047",
        "product_description": "Optical Filter — Bandpass Camera Filter 532nm",
        "shipment_value_usd":  7600,
        "freight_cost_usd":    110,
        "insurance_cost_usd":  25,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    38.0,   # FAILS (38 < 40)
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens filter bandpass camera projector element 532nm",
             "quantity": 60, "unit_value_usd": 120.00, "weight_kg": 0.05},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP048",
        "product_description": "Optical Lens — GRIN Array Fibre Camera Collimator",
        "shipment_value_usd":  12400,
        "freight_cost_usd":    175,
        "insurance_cost_usd":  45,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    48.0,
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens GRIN array fibre camera collimator projector element",
             "quantity": 35, "unit_value_usd": 340.00, "weight_kg": 0.12},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP049",
        "product_description": "Optical Lens — Objective Camera Lens 10x Industrial",
        "shipment_value_usd":  19800,
        "freight_cost_usd":    270,
        "insurance_cost_usd":  68,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    52.0,
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens objective camera projector element 10x industrial",
             "quantity": 20, "unit_value_usd": 950.00, "weight_kg": 0.35},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP050",
        "product_description": "Optical Lens — Macro Camera Lens AOI Inspection",
        "shipment_value_usd":  38000,
        "freight_cost_usd":    450,
        "insurance_cost_usd":  110,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    65.0,
        "bom_items": [
            {"hs_code": "9001.90", "description": "optical lens macro camera projector element AOI inspection",
             "quantity": 10, "unit_value_usd": 3700.00, "weight_kg": 0.8},
        ],
        "status": "pending"
    },
]

# HS reference data — descriptions optimised for Ollama embedding + RAG retrieval
HS_REFERENCE_DATA = [
    {
        "hs_code": "8534.00",
        "description": "Printed circuits — single-sided printed circuit board PCB",
        "explanatory_notes": "Printed circuits consist of a base of insulating material with a conductive pattern of copper or other metal. Single-sided PCB has conductive layer on one side only. Used in electronic assemblies, power supplies, LED drivers, motor controllers, IoT devices.",
        "source": "WCO"
    },
    {
        "hs_code": "8501.10",
        "description": "Spindle motors — electric DC motor not exceeding 37.5W",
        "explanatory_notes": "Small DC electric motors used as spindle motors in CNC machines, milling machines, grinding machines, precision manufacturing equipment. Includes encoder-feedback motors for positioning control.",
        "source": "WCO"
    },
    {
        "hs_code": "7604.29",
        "description": "Aluminium alloy bars, rods and profiles — extruded bar rod profile",
        "explanatory_notes": "Extruded aluminium alloy profiles and bars used in heat dissipation heatsinks, structural T-slot frames, DIN rails, enclosure profiles, cold plates for liquid cooling. Alloy grades 6063, 6061 common.",
        "source": "WCO"
    },
    {
        "hs_code": "8542.31",
        "description": "Electronic integrated circuits — processors controllers memory chip IC",
        "explanatory_notes": "Electronic integrated circuits including microprocessors, microcontrollers, digital signal processors DSP, memory chips DRAM DDR4 DDR5 LPDDR5, NAND flash, NOR flash, FPGA, SoC, PMIC power management IC. Covered under WTO ITA agreement.",
        "source": "WCO"
    },
    {
        "hs_code": "9001.90",
        "description": "Optical elements — lens camera projector cinematographic optical fibre",
        "explanatory_notes": "Optical lenses, prisms, mirrors and other optical elements for cameras, projectors, cinematographic equipment, machine vision systems, microscopes, fibre optic coupling, laser optics. Includes aspherical, telecentric, achromatic, GRIN, collimating lenses.",
        "source": "WCO"
    },
    {
        "hs_code": "8541.10",
        "description": "Diodes — semiconductor diode Zener Schottky rectifier",
        "explanatory_notes": "Semiconductor diodes used in rectification, signal processing, protection circuits. Includes Zener diodes, Schottky diodes, rectifier diodes.",
        "source": "WCO"
    },
    {
        "hs_code": "8537.10",
        "description": "Switchboards control panels — electrical distribution board voltage under 1000V",
        "explanatory_notes": "Control panels, distribution boards, switchboards for electrical control and distribution. Used in industrial automation and motor control. Voltage not exceeding 1000V.",
        "source": "WCO"
    },
    {
        "hs_code": "8471.30",
        "description": "Laptop computer notebook portable automatic data processing machine",
        "explanatory_notes": "Portable computers weighing not more than 10kg. Includes laptops, notebooks, tablet computers with keyboard.",
        "source": "WCO"
    },
    {
        "hs_code": "9001.10",
        "description": "Optical fibres — optical fibre cable bundle telecommunications",
        "explanatory_notes": "Optical fibres and optical fibre bundles for telecommunications and other electrical uses. Single-mode and multi-mode fibres.",
        "source": "WCO"
    }
]


async def get_embedding(text: str) -> list:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["embedding"]


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
            print(f"[seed] ✓ HS {item['hs_code']} — {item['description'][:50]}")

        except Exception as e:
            print(f"[seed] ✗ HS {item['hs_code']} failed: {e}")

    return count


def _mock_cls(sap_id: str, hs: str, confidence: int, status: str,
              reasoning: str, e2open_hs: str = None):
    return {
        "sap_id":           sap_id,
        "e2open_hs_code":   e2open_hs or hs,
        "ai_hs_code":       hs,
        "confidence_score": confidence,
        "reasoning_text":   reasoning,
        "rag_sources":      [{"hs_code": hs, "similarity": round(confidence / 100, 2),
                              "description": "primary match"}],
        "final_hs_code":    hs,
        "module_a_status":  status,
    }


MOCK_CLASSIFICATIONS = (
    # Vietnam PCBs — SHIP001–SHIP010 — HS 8534.00
    [_mock_cls(f"SHIP{i:03d}", "8534.00", 94, "auto_passed",
               "Single-sided printed circuit board matches HS 8534.00.")
     for i in range(1, 11)] +
    # Vietnam Aluminium — SHIP011–SHIP020 — HS 7604.29
    [_mock_cls(f"SHIP{i:03d}", "7604.29", 96, "auto_passed",
               "Aluminium alloy extruded bar/rod/profile matches HS 7604.29.")
     for i in range(11, 21)] +
    # China Spindle Motors — SHIP021–SHIP030 — HS 8501.10 (changed from 8501.52)
    [_mock_cls(f"SHIP{i:03d}", "8501.10", 91, "auto_passed",
               "Spindle motor (DC electric, not exceeding 37.5W) matches HS 8501.10.")
     for i in range(21, 31)] +
    # Taiwan ICs/Memory — SHIP031–SHIP040 — HS 8542.31
    [_mock_cls(f"SHIP{i:03d}", "8542.31",
               82 if i == 31 else 88,
               "flagged_low_confidence" if i == 31 else "auto_passed",
               "Electronic integrated circuit / memory / processor matches HS 8542.31.",
               e2open_hs="8471.30" if i == 31 else None)
     for i in range(31, 41)] +
    # South Korea Optical — SHIP041–SHIP050 — HS 9001.90
    [_mock_cls(f"SHIP{i:03d}", "9001.90", 95, "auto_passed",
               "Optical lens/element for cameras/projectors matches HS 9001.90.")
     for i in range(41, 51)]
)


async def seed_mock_classifications() -> int:
    count = 0
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
            print(f"[seed] ✓ Classification {mock['sap_id']} "
                  f"→ HS {mock['ai_hs_code']} ({mock['confidence_score']}%) "
                  f"[{mock['module_a_status']}]")

        except Exception as e:
            print(f"[seed] ✗ Classification {mock['sap_id']} failed: {e}")

    return count


async def seed_config() -> int:
    CONFIG_DEFAULTS = [
        ("RMCD_FX_MYR_PER_USD",     "4.67"),
        ("is_lmw_facility",          "true"),
        ("sales_tax_rate_pct",       "10.0"),
        ("rmcd_declaration_fee_myr", "50.0"),
        ("base_clearance_fee_myr",   "300.0"),
        ("handling_fee_per_kg_myr",  "2.50"),
        ("terminal_handling_myr",    "120.0"),
        ("edi_fee_myr",              "15.0"),
    ]
    count = 0
    try:
        for key, value in CONFIG_DEFAULTS:
            supabase.table("config").upsert(
                {"key": key, "value": value}, on_conflict="key"
            ).execute()
            count += 1
        print(f"[seed] ✓ Config ({count} items) seeded")
        return count
    except Exception as e:
        print(f"[seed] Config seed failed: {e}")
        return 0



# FTA rates, MFN/tariff_rates, and RoO rules are NOT seeded here.
# They are populated automatically when the ingestion pipeline runs:
#   - JKDM scraper (fta_scraper.py) → fetches real rates from ezhs.customs.gov.my
#     selects each FTA from dropdown (RCEP/ACFTA/AKFTA/PDK), searches our 5 HS codes,
#     reads the exact sub-code row, stores in fta_rates
#   - ATIGA fallback (fta_scraper.py) → downloads MITI PDF when site is available
#   - WTO API (tariff_sync.py) → fetches MFN baseline into tariff_rates
#   - RoO rules → extracted from MITI RoO chapter PDFs by the scraper
# To trigger: POST /api/admin/run-ingestion/all


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
        print("[seed] FTA coverage seeded")
    except Exception as e:
        print(f"[seed] FTA seed failed: {e}")

    config_count = await seed_config()

    mock_cls_count = await seed_mock_classifications()
    print(f"[seed] Mock classifications: {mock_cls_count} seeded")

    print("[seed] Database seed complete!\n")

    return {
        "shipments":            shipments_count,
        "hs_reference":         hs_count,
        "tariff_rates":         "seeded",
        "fta_data":             "seeded",
        "mock_classifications": mock_cls_count,
        "config":               config_count,
    }
