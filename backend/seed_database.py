import httpx
import json
from supabase import create_client
from config import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# ── 50 shipments — 4 origins, 5 HS families ─────────────────────
# Origins: Vietnam (ATIGA+RCEP), China (ACFTA+RCEP),
#          Taiwan (MFN/ITA only), South Korea (AKFTA+RCEP)
# FTA data only stored for these 4 countries — no other RCEP members.

SAMPLE_SHIPMENTS = [

    # ── VIETNAM → MALAYSIA — PCB / 8534.00 (SHIP001–SHIP010) ─────
    {
        "sap_shipment_id":     "SHIP001",
        "product_description": "Printed Circuit Board Assembly — 4-layer",
        "shipment_value_usd":  15000,
        "freight_cost_usd":    200,
        "insurance_cost_usd":  50,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    62.0,   # PASSES ATIGA+RCEP (>=40%)
        "bom_items": [
            {"hs_code": "8534.00", "description": "PCB Assembly 4-layer",
             "quantity": 50, "unit_value_usd": 240.00, "weight_kg": 0.8},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP002",
        "product_description": "Printed Circuit Board Assembly — 6-layer HDI",
        "shipment_value_usd":  21000,
        "freight_cost_usd":    260,
        "insurance_cost_usd":  65,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    58.0,   # PASSES
        "bom_items": [
            {"hs_code": "8534.00", "description": "PCB Assembly 6-layer HDI",
             "quantity": 35, "unit_value_usd": 520.00, "weight_kg": 1.1},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP003",
        "product_description": "Rigid-Flex PCB Assembly",
        "shipment_value_usd":  9500,
        "freight_cost_usd":    140,
        "insurance_cost_usd":  30,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    45.0,   # PASSES
        "bom_items": [
            {"hs_code": "8534.00", "description": "Rigid-Flex PCB",
             "quantity": 80, "unit_value_usd": 110.00, "weight_kg": 0.4},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP004",
        "product_description": "High-Frequency RF PCB Assembly",
        "shipment_value_usd":  17500,
        "freight_cost_usd":    220,
        "insurance_cost_usd":  55,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    51.0,   # PASSES
        "bom_items": [
            {"hs_code": "8534.00", "description": "RF PCB Assembly",
             "quantity": 25, "unit_value_usd": 660.00, "weight_kg": 0.6},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP005",
        "product_description": "Single-Sided PCB Assembly — LED Driver",
        "shipment_value_usd":  4200,
        "freight_cost_usd":    70,
        "insurance_cost_usd":  12,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    35.0,   # FAILS (35 < 40)
        "bom_items": [
            {"hs_code": "8534.00", "description": "Single-Sided PCB LED Driver",
             "quantity": 200, "unit_value_usd": 18.00, "weight_kg": 0.1},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP006",
        "product_description": "Multilayer PCB Assembly — Power Supply",
        "shipment_value_usd":  11200,
        "freight_cost_usd":    160,
        "insurance_cost_usd":  40,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    72.0,   # PASSES
        "bom_items": [
            {"hs_code": "8534.00", "description": "PCB Power Supply",
             "quantity": 60, "unit_value_usd": 170.00, "weight_kg": 0.9},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP007",
        "product_description": "PCB Assembly — Motor Control Board",
        "shipment_value_usd":  8800,
        "freight_cost_usd":    130,
        "insurance_cost_usd":  25,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    48.0,   # PASSES
        "bom_items": [
            {"hs_code": "8534.00", "description": "Motor Control PCB",
             "quantity": 40, "unit_value_usd": 195.00, "weight_kg": 0.7},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP008",
        "product_description": "PCB Assembly — IoT Gateway Board",
        "shipment_value_usd":  13600,
        "freight_cost_usd":    185,
        "insurance_cost_usd":  45,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    30.0,   # FAILS
        "bom_items": [
            {"hs_code": "8534.00", "description": "IoT Gateway PCB",
             "quantity": 45, "unit_value_usd": 280.00, "weight_kg": 0.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP009",
        "product_description": "PCB Assembly — Industrial Sensor Interface",
        "shipment_value_usd":  6700,
        "freight_cost_usd":    100,
        "insurance_cost_usd":  20,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    55.0,   # PASSES
        "bom_items": [
            {"hs_code": "8534.00", "description": "Sensor Interface PCB",
             "quantity": 30, "unit_value_usd": 210.00, "weight_kg": 0.4},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP010",
        "product_description": "PCB Assembly — Automotive Grade",
        "shipment_value_usd":  28500,
        "freight_cost_usd":    350,
        "insurance_cost_usd":  90,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    65.0,   # PASSES
        "bom_items": [
            {"hs_code": "8534.00", "description": "Automotive PCB Assembly",
             "quantity": 20, "unit_value_usd": 1350.00, "weight_kg": 1.5},
        ],
        "status": "pending"
    },

    # ── VIETNAM → MALAYSIA — Aluminium / 7604.29 (SHIP011–SHIP020) ─
    {
        "sap_shipment_id":     "SHIP011",
        "product_description": "Aluminium Heatsink Extrusion — Standard",
        "shipment_value_usd":  3200,
        "freight_cost_usd":    80,
        "insurance_cost_usd":  15,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    28.0,   # FAILS RVC, CTSH review needed
        "bom_items": [
            {"hs_code": "7604.29", "description": "Aluminium Heatsink Extrusion",
             "quantity": 100, "unit_value_usd": 28.00, "weight_kg": 0.8},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP012",
        "product_description": "Aluminium Heatsink — High-Power LED",
        "shipment_value_usd":  2100,
        "freight_cost_usd":    55,
        "insurance_cost_usd":  10,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    32.0,   # FAILS
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al Heatsink LED High-Power",
             "quantity": 150, "unit_value_usd": 12.50, "weight_kg": 0.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP013",
        "product_description": "Aluminium Profile — Server Rack Rail",
        "shipment_value_usd":  4800,
        "freight_cost_usd":    95,
        "insurance_cost_usd":  18,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    42.0,   # PASSES
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al Profile Server Rack",
             "quantity": 80, "unit_value_usd": 55.00, "weight_kg": 1.2},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP014",
        "product_description": "Extruded Aluminium Enclosure Profile",
        "shipment_value_usd":  5600,
        "freight_cost_usd":    110,
        "insurance_cost_usd":  22,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    25.0,   # FAILS
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al Enclosure Profile",
             "quantity": 200, "unit_value_usd": 26.00, "weight_kg": 0.7},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP015",
        "product_description": "Aluminium Fin Array Heatsink",
        "shipment_value_usd":  3900,
        "freight_cost_usd":    85,
        "insurance_cost_usd":  16,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    44.0,   # PASSES
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al Fin Array Heatsink",
             "quantity": 120, "unit_value_usd": 30.00, "weight_kg": 0.9},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP016",
        "product_description": "Aluminium Structural Bracket Profile",
        "shipment_value_usd":  2700,
        "freight_cost_usd":    65,
        "insurance_cost_usd":  12,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    38.0,   # FAILS (38 < 40)
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al Structural Bracket",
             "quantity": 90, "unit_value_usd": 28.00, "weight_kg": 0.6},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP017",
        "product_description": "Aluminium T-Slot Extrusion Profile",
        "shipment_value_usd":  1800,
        "freight_cost_usd":    45,
        "insurance_cost_usd":  8,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    50.0,   # PASSES
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al T-Slot Extrusion",
             "quantity": 60, "unit_value_usd": 28.00, "weight_kg": 0.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP018",
        "product_description": "Aluminium Cold Plate — Liquid Cooling",
        "shipment_value_usd":  6200,
        "freight_cost_usd":    120,
        "insurance_cost_usd":  24,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    22.0,   # FAILS
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al Cold Plate Liquid Cooling",
             "quantity": 50, "unit_value_usd": 116.00, "weight_kg": 1.8},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP019",
        "product_description": "Aluminium DIN Rail Profile",
        "shipment_value_usd":  1500,
        "freight_cost_usd":    40,
        "insurance_cost_usd":  7,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    48.0,   # PASSES
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al DIN Rail Profile",
             "quantity": 300, "unit_value_usd": 4.80, "weight_kg": 0.3},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP020",
        "product_description": "Aluminium Alloy Bar — 6063-T5",
        "shipment_value_usd":  2400,
        "freight_cost_usd":    60,
        "insurance_cost_usd":  11,
        "destination_country": "Malaysia",
        "origin_country":      "Vietnam",
        "supplier_rvc_pct":    40.0,   # PASSES (exactly at threshold)
        "bom_items": [
            {"hs_code": "7604.29", "description": "Al Alloy Bar 6063-T5",
             "quantity": 400, "unit_value_usd": 5.50, "weight_kg": 2.0},
        ],
        "status": "pending"
    },

    # ── CHINA → MALAYSIA — Motors / 8501.52 (SHIP021–SHIP030) ─────
    {
        "sap_shipment_id":     "SHIP021",
        "product_description": "Industrial Servo Motor — 1kW",
        "shipment_value_usd":  8500,
        "freight_cost_usd":    150,
        "insurance_cost_usd":  30,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS — no RVC cert
        "bom_items": [
            {"hs_code": "8501.52", "description": "Servo Motor 1kW",
             "quantity": 5, "unit_value_usd": 1400.00, "weight_kg": 12.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP022",
        "product_description": "AC Induction Motor — 2.2kW",
        "shipment_value_usd":  6200,
        "freight_cost_usd":    120,
        "insurance_cost_usd":  25,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS
        "bom_items": [
            {"hs_code": "8501.52", "description": "AC Induction Motor 2.2kW",
             "quantity": 4, "unit_value_usd": 1430.00, "weight_kg": 18.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP023",
        "product_description": "BLDC Motor — 1.5kW Spindle Drive",
        "shipment_value_usd":  11400,
        "freight_cost_usd":    180,
        "insurance_cost_usd":  40,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    42.0,   # PASSES — has RVC cert
        "bom_items": [
            {"hs_code": "8501.52", "description": "BLDC Spindle Motor 1.5kW",
             "quantity": 6, "unit_value_usd": 1750.00, "weight_kg": 9.5},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP024",
        "product_description": "Stepper Motor — NEMA 34 High-Torque",
        "shipment_value_usd":  4800,
        "freight_cost_usd":    90,
        "insurance_cost_usd":  18,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS
        "bom_items": [
            {"hs_code": "8501.52", "description": "Stepper Motor NEMA34",
             "quantity": 8, "unit_value_usd": 560.00, "weight_kg": 3.2},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP025",
        "product_description": "Linear AC Motor — Conveyor Drive",
        "shipment_value_usd":  16800,
        "freight_cost_usd":    240,
        "insurance_cost_usd":  55,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS
        "bom_items": [
            {"hs_code": "8501.52", "description": "Linear AC Motor Conveyor",
             "quantity": 3, "unit_value_usd": 5300.00, "weight_kg": 28.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP026",
        "product_description": "Servo Motor — 5kW Rotary Table",
        "shipment_value_usd":  22000,
        "freight_cost_usd":    290,
        "insurance_cost_usd":  70,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    45.0,   # PASSES
        "bom_items": [
            {"hs_code": "8501.52", "description": "Servo Motor 5kW Rotary",
             "quantity": 4, "unit_value_usd": 5200.00, "weight_kg": 35.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP027",
        "product_description": "Multi-Phase AC Motor — Pump Drive 3kW",
        "shipment_value_usd":  9100,
        "freight_cost_usd":    155,
        "insurance_cost_usd":  32,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS
        "bom_items": [
            {"hs_code": "8501.52", "description": "AC Motor Pump Drive 3kW",
             "quantity": 3, "unit_value_usd": 2800.00, "weight_kg": 22.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP028",
        "product_description": "Servo Motor — 750W Compact Frame",
        "shipment_value_usd":  5600,
        "freight_cost_usd":    100,
        "insurance_cost_usd":  20,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    38.0,   # FAILS (38 < 40)
        "bom_items": [
            {"hs_code": "8501.52", "description": "Servo Motor 750W Compact",
             "quantity": 7, "unit_value_usd": 740.00, "weight_kg": 5.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP029",
        "product_description": "Torque Motor — Direct Drive 10kW",
        "shipment_value_usd":  31000,
        "freight_cost_usd":    380,
        "insurance_cost_usd":  95,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    52.0,   # PASSES
        "bom_items": [
            {"hs_code": "8501.52", "description": "Torque Motor Direct Drive 10kW",
             "quantity": 2, "unit_value_usd": 14800.00, "weight_kg": 65.0},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP030",
        "product_description": "AC Servo Motor — 2kW with Encoder",
        "shipment_value_usd":  12600,
        "freight_cost_usd":    190,
        "insurance_cost_usd":  42,
        "destination_country": "Malaysia",
        "origin_country":      "China",
        "supplier_rvc_pct":    0.0,    # FAILS — no cert
        "bom_items": [
            {"hs_code": "8501.52", "description": "AC Servo Motor 2kW Encoder",
             "quantity": 5, "unit_value_usd": 2360.00, "weight_kg": 14.0},
        ],
        "status": "pending"
    },

    # ── TAIWAN → MALAYSIA — Memory/IC / 8542.31 (SHIP031–SHIP040) ─
    {
        "sap_shipment_id":     "SHIP031",
        "product_description": "DRAM Memory Module DDR5 — 16GB",
        "shipment_value_usd":  18000,
        "freight_cost_usd":    60,
        "insurance_cost_usd":  10,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    40.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "DRAM Module DDR5 16GB",
             "quantity": 300, "unit_value_usd": 55.00, "weight_kg": 0.05},
        ],
        "status": "flagged"
    },
    {
        "sap_shipment_id":     "SHIP032",
        "product_description": "LPDDR5 Mobile Memory — 8GB",
        "shipment_value_usd":  24500,
        "freight_cost_usd":    75,
        "insurance_cost_usd":  14,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    55.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "LPDDR5 Mobile Memory 8GB",
             "quantity": 500, "unit_value_usd": 48.00, "weight_kg": 0.02},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP033",
        "product_description": "NAND Flash Storage — 256GB eMMC",
        "shipment_value_usd":  19200,
        "freight_cost_usd":    65,
        "insurance_cost_usd":  12,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    48.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "NAND Flash 256GB eMMC",
             "quantity": 400, "unit_value_usd": 47.00, "weight_kg": 0.03},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP034",
        "product_description": "FPGA — Xilinx Artix-7 Series",
        "shipment_value_usd":  35000,
        "freight_cost_usd":    90,
        "insurance_cost_usd":  20,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    60.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "FPGA Artix-7",
             "quantity": 100, "unit_value_usd": 340.00, "weight_kg": 0.02},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP035",
        "product_description": "SoC — Application Processor ARM Cortex-A55",
        "shipment_value_usd":  42000,
        "freight_cost_usd":    100,
        "insurance_cost_usd":  25,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    65.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "SoC ARM Cortex-A55",
             "quantity": 200, "unit_value_usd": 200.00, "weight_kg": 0.01},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP036",
        "product_description": "DDR4 Server RDIMM — 32GB ECC",
        "shipment_value_usd":  28800,
        "freight_cost_usd":    80,
        "insurance_cost_usd":  18,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    50.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "DDR4 Server RDIMM 32GB ECC",
             "quantity": 120, "unit_value_usd": 230.00, "weight_kg": 0.08},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP037",
        "product_description": "MCU — 32-bit ARM Cortex-M4 Microcontroller",
        "shipment_value_usd":  8400,
        "freight_cost_usd":    40,
        "insurance_cost_usd":  8,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    42.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "MCU Cortex-M4 32-bit",
             "quantity": 1000, "unit_value_usd": 8.20, "weight_kg": 0.005},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP038",
        "product_description": "NOR Flash — 64Mb SPI Interface",
        "shipment_value_usd":  5600,
        "freight_cost_usd":    30,
        "insurance_cost_usd":  6,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    38.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "NOR Flash 64Mb SPI",
             "quantity": 2000, "unit_value_usd": 2.70, "weight_kg": 0.002},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP039",
        "product_description": "DSP Chip — Signal Processing IC",
        "shipment_value_usd":  16500,
        "freight_cost_usd":    55,
        "insurance_cost_usd":  12,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    58.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "DSP Signal Processing IC",
             "quantity": 150, "unit_value_usd": 106.00, "weight_kg": 0.01},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP040",
        "product_description": "Power Management IC — Buck Converter",
        "shipment_value_usd":  7200,
        "freight_cost_usd":    35,
        "insurance_cost_usd":  7,
        "destination_country": "Malaysia",
        "origin_country":      "Taiwan",
        "supplier_rvc_pct":    44.0,
        "bom_items": [
            {"hs_code": "8542.31", "description": "PMIC Buck Converter",
             "quantity": 1500, "unit_value_usd": 4.70, "weight_kg": 0.003},
        ],
        "status": "pending"
    },

    # ── SOUTH KOREA → MALAYSIA — Optical / 9001.90 (SHIP041–SHIP050) ─
    {
        "sap_shipment_id":     "SHIP041",
        "product_description": "Optical Lens Assembly — Machine Vision",
        "shipment_value_usd":  22000,
        "freight_cost_usd":    300,
        "insurance_cost_usd":  80,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    40.0,   # PASSES exactly at threshold
        "bom_items": [
            {"hs_code": "9001.90", "description": "Optical Lens Machine Vision",
             "quantity": 40, "unit_value_usd": 520.00, "weight_kg": 0.15},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP042",
        "product_description": "Telecentric Lens Assembly — 0.5x",
        "shipment_value_usd":  18500,
        "freight_cost_usd":    260,
        "insurance_cost_usd":  65,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    45.0,   # PASSES
        "bom_items": [
            {"hs_code": "9001.90", "description": "Telecentric Lens 0.5x",
             "quantity": 25, "unit_value_usd": 700.00, "weight_kg": 0.3},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP043",
        "product_description": "Aspherical Lens Element — Laser Optics",
        "shipment_value_usd":  31000,
        "freight_cost_usd":    380,
        "insurance_cost_usd":  95,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    55.0,   # PASSES
        "bom_items": [
            {"hs_code": "9001.90", "description": "Aspherical Lens Laser",
             "quantity": 20, "unit_value_usd": 1480.00, "weight_kg": 0.2},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP044",
        "product_description": "Optical Prism Assembly — Beam Splitter",
        "shipment_value_usd":  14200,
        "freight_cost_usd":    200,
        "insurance_cost_usd":  50,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    35.0,   # FAILS
        "bom_items": [
            {"hs_code": "9001.90", "description": "Optical Prism Beam Splitter",
             "quantity": 30, "unit_value_usd": 450.00, "weight_kg": 0.25},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP045",
        "product_description": "Collimating Lens — Fibre Optic Coupling",
        "shipment_value_usd":  9800,
        "freight_cost_usd":    145,
        "insurance_cost_usd":  35,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    42.0,   # PASSES
        "bom_items": [
            {"hs_code": "9001.90", "description": "Collimating Lens Fibre Coupling",
             "quantity": 50, "unit_value_usd": 185.00, "weight_kg": 0.1},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP046",
        "product_description": "Doublet Achromatic Lens — Microscopy",
        "shipment_value_usd":  26500,
        "freight_cost_usd":    330,
        "insurance_cost_usd":  85,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    60.0,   # PASSES
        "bom_items": [
            {"hs_code": "9001.90", "description": "Doublet Achromatic Lens",
             "quantity": 15, "unit_value_usd": 1700.00, "weight_kg": 0.4},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP047",
        "product_description": "Optical Filter Assembly — Bandpass 532nm",
        "shipment_value_usd":  7600,
        "freight_cost_usd":    110,
        "insurance_cost_usd":  25,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    38.0,   # FAILS (38 < 40)
        "bom_items": [
            {"hs_code": "9001.90", "description": "Optical Bandpass Filter 532nm",
             "quantity": 60, "unit_value_usd": 120.00, "weight_kg": 0.05},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP048",
        "product_description": "GRIN Lens Array — Fibre Collimator",
        "shipment_value_usd":  12400,
        "freight_cost_usd":    175,
        "insurance_cost_usd":  45,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    48.0,   # PASSES
        "bom_items": [
            {"hs_code": "9001.90", "description": "GRIN Lens Array Fibre",
             "quantity": 35, "unit_value_usd": 340.00, "weight_kg": 0.12},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP049",
        "product_description": "Objective Lens Assembly — 10x Industrial",
        "shipment_value_usd":  19800,
        "freight_cost_usd":    270,
        "insurance_cost_usd":  68,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    52.0,   # PASSES
        "bom_items": [
            {"hs_code": "9001.90", "description": "Objective Lens 10x Industrial",
             "quantity": 20, "unit_value_usd": 950.00, "weight_kg": 0.35},
        ],
        "status": "pending"
    },
    {
        "sap_shipment_id":     "SHIP050",
        "product_description": "Macro Lens Assembly — AOI Inspection System",
        "shipment_value_usd":  38000,
        "freight_cost_usd":    450,
        "insurance_cost_usd":  110,
        "destination_country": "Malaysia",
        "origin_country":      "South Korea",
        "supplier_rvc_pct":    65.0,   # PASSES
        "bom_items": [
            {"hs_code": "9001.90", "description": "Macro Lens AOI Inspection",
             "quantity": 10, "unit_value_usd": 3700.00, "weight_kg": 0.8},
        ],
        "status": "pending"
    },
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
        "hs_code": "7604.29",
        "description": "Aluminium alloy bars, rods and profiles",
        "explanatory_notes": "Extruded aluminium alloy profiles used in heat dissipation, structural components, enclosures. Includes heatsinks and thermal management components.",
        "source": "WCO"
    },
    {
        "hs_code": "8542.31",
        "description": "Processors and controllers, electronic integrated circuits",
        "explanatory_notes": "Microprocessors, microcontrollers, digital signal processors. Core components of computing and control systems.",
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
# One classification entry per shipment — SHIP001–SHIP050.
# All share the same HS logic (same 5 HS codes, 4 origins).
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
    # Vietnam PCBs — SHIP001–SHIP010
    [_mock_cls(f"SHIP{i:03d}", "8534.00", 94, "auto_passed",
               f"PCB variant matches HS 8534.00 with high confidence.")
     for i in range(1, 11)] +
    # Vietnam Aluminium — SHIP011–SHIP020
    [_mock_cls(f"SHIP{i:03d}", "7604.29", 96, "auto_passed",
               f"Aluminium extrusion/profile matches HS 7604.29.")
     for i in range(11, 21)] +
    # China Motors — SHIP021–SHIP030
    [_mock_cls(f"SHIP{i:03d}", "8501.52", 89, "auto_passed",
               f"AC/servo motor matches HS 8501.52 (>750W multi-phase).")
     for i in range(21, 31)] +
    # Taiwan ICs — SHIP031–SHIP040
    [_mock_cls(f"SHIP{i:03d}", "8542.31", 82 if i == 31 else 88,
               "flagged_low_confidence" if i == 31 else "auto_passed",
               f"Memory/IC matches HS 8542.31 (electronic integrated circuits).",
               e2open_hs="8471.30" if i == 31 else None)
     for i in range(31, 41)] +
    # South Korea Optical — SHIP041–SHIP050
    [_mock_cls(f"SHIP{i:03d}", "9001.90", 95, "auto_passed",
               f"Optical lens/element matches HS 9001.90.")
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
            print(f"[seed] ✓ Mock classification {mock['sap_id']} "
                  f"→ HS {mock['ai_hs_code']} ({mock['confidence_score']}%) "
                  f"[{mock['module_a_status']}]")

        except Exception as e:
            print(f"[seed] ✗ Mock classification {mock['sap_id']} failed: {e}")

    return count


# ── Config defaults for Module C ────────────────────────────────
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


# ── FTA rates — ONLY for our 4 origin countries ──────────────────
# Vietnam  → ATIGA + RCEP
# China    → ACFTA + RCEP
# Taiwan   → MFN/ITA only (no FTA with Malaysia)
# S. Korea → AKFTA + RCEP
# No rates for Japan, Australia, Indonesia, Thailand, etc.
async def seed_additional_fta_data() -> None:

    additional_rates = [
        # Vietnam — HS 8534.00
        {"fta_name": "ATIGA", "hs_code": "8534.00", "preferential_rate_pct": 0.0,
         "origin_country": "Vietnam", "effective_date": "2010-01-01"},
        {"fta_name": "RCEP",  "hs_code": "8534.00", "preferential_rate_pct": 0.0,
         "origin_country": "Vietnam", "effective_date": "2022-01-01"},

        # Vietnam — HS 7604.29
        {"fta_name": "ATIGA", "hs_code": "7604.29", "preferential_rate_pct": 0.0,
         "origin_country": "Vietnam", "effective_date": "2010-01-01"},
        {"fta_name": "RCEP",  "hs_code": "7604.29", "preferential_rate_pct": 0.0,
         "origin_country": "Vietnam", "effective_date": "2022-01-01"},

        # China — HS 8501.52
        {"fta_name": "ACFTA", "hs_code": "8501.52", "preferential_rate_pct": 0.0,
         "origin_country": "China", "effective_date": "2005-07-20"},
        {"fta_name": "RCEP",  "hs_code": "8501.52", "preferential_rate_pct": 0.0,
         "origin_country": "China", "effective_date": "2022-01-01"},

        # South Korea — HS 9001.90
        {"fta_name": "AKFTA", "hs_code": "9001.90", "preferential_rate_pct": 0.0,
         "origin_country": "South Korea", "effective_date": "2007-06-01"},
        {"fta_name": "RCEP",  "hs_code": "9001.90", "preferential_rate_pct": 0.0,
         "origin_country": "South Korea", "effective_date": "2022-01-01"},

        # Taiwan — MFN/ITA (no FTA; ITA gives 0% on electronics/optical)
        {"fta_name": "MFN", "hs_code": "8534.00", "preferential_rate_pct": 0.0,
         "origin_country": "Taiwan", "effective_date": "2025-01-01"},
        {"fta_name": "MFN", "hs_code": "8501.52", "preferential_rate_pct": 5.0,
         "origin_country": "Taiwan", "effective_date": "2025-01-01"},
        {"fta_name": "MFN", "hs_code": "7604.29", "preferential_rate_pct": 5.0,
         "origin_country": "Taiwan", "effective_date": "2025-01-01"},
        {"fta_name": "MFN", "hs_code": "8542.31", "preferential_rate_pct": 0.0,
         "origin_country": "Taiwan", "effective_date": "2025-01-01"},
        {"fta_name": "MFN", "hs_code": "9001.90", "preferential_rate_pct": 0.0,
         "origin_country": "Taiwan", "effective_date": "2025-01-01"},

        # MFN baseline rates (PDK2025/ITA) — global fallback for all origins
        {"fta_name": "PDK", "hs_code": "8534.00", "preferential_rate_pct": 0.0,
         "origin_country": "MFN", "effective_date": "2025-01-01"},
        {"fta_name": "PDK", "hs_code": "8501.52", "preferential_rate_pct": 5.0,
         "origin_country": "MFN", "effective_date": "2025-01-01"},
        {"fta_name": "PDK", "hs_code": "7604.29", "preferential_rate_pct": 5.0,
         "origin_country": "MFN", "effective_date": "2025-01-01"},
        {"fta_name": "PDK", "hs_code": "8542.31", "preferential_rate_pct": 0.0,
         "origin_country": "MFN", "effective_date": "2025-01-01"},
        {"fta_name": "PDK", "hs_code": "9001.90", "preferential_rate_pct": 0.0,
         "origin_country": "MFN", "effective_date": "2025-01-01"},
    ]

    additional_roo = [
        # ATIGA RoO
        {"fta_name": "ATIGA", "hs_code": "8534.00", "roo_type": "RVC",
         "rvc_threshold_pct": 40.0,
         "tariff_shift_description": "Regional Value Content >= 40% (build-up method)"},
        {"fta_name": "ATIGA", "hs_code": "7604.29", "roo_type": "RVC",
         "rvc_threshold_pct": 40.0,
         "tariff_shift_description": "Regional Value Content >= 40%"},

        # RCEP RoO
        {"fta_name": "RCEP", "hs_code": "8534.00", "roo_type": "RVC",
         "rvc_threshold_pct": 40.0,
         "tariff_shift_description": "RVC >= 40%"},
        {"fta_name": "RCEP", "hs_code": "7604.29", "roo_type": "tariff_shift",
         "rvc_threshold_pct": 40.0,
         "tariff_shift_description": "RVC 40% OR Change in Tariff Sub-Heading (CTSH)"},
        {"fta_name": "RCEP", "hs_code": "8501.52", "roo_type": "RVC",
         "rvc_threshold_pct": 40.0,
         "tariff_shift_description": "RVC >= 40%"},
        {"fta_name": "RCEP", "hs_code": "9001.90", "roo_type": "RVC",
         "rvc_threshold_pct": 40.0,
         "tariff_shift_description": "RVC >= 40%"},

        # ACFTA RoO
        {"fta_name": "ACFTA", "hs_code": "8501.52", "roo_type": "RVC",
         "rvc_threshold_pct": 40.0,
         "tariff_shift_description": "RVC >= 40%"},

        # AKFTA RoO
        {"fta_name": "AKFTA", "hs_code": "9001.90", "roo_type": "RVC",
         "rvc_threshold_pct": 40.0,
         "tariff_shift_description": "RVC >= 40%"},
    ]

    try:
        for rate in additional_rates:
            supabase.table("fta_rates").upsert(
                rate, on_conflict="fta_name,hs_code,origin_country"
            ).execute()
        print(f"[seed] ✓ FTA rates seeded ({len(additional_rates)} rows, "
              "4 countries only: Vietnam, China, Taiwan, South Korea)")
    except Exception as e:
        print(f"[seed] Additional FTA rates failed: {e}")

    try:
        for rule in additional_roo:
            supabase.table("roo_rules").upsert(
                rule, on_conflict="fta_name,hs_code"
            ).execute()
        print(f"[seed] ✓ RoO rules seeded ({len(additional_roo)} rules)")
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
