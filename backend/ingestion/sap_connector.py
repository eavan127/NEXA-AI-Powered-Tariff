import httpx
from config import settings

MOCK_SHIPMENTS = {
    "SHIP001": {
        "sap_shipment_id": "SHIP001",
        "product_description": "Printed Circuit Board Assembly",
        "shipment_value_usd": 15000,
        "freight_cost_usd": 200,
        "insurance_cost_usd": 50,
        "destination_country": "Malaysia",
        "origin_country": "China",
        "bom_items": [
            {"hs_code": "8534.00", "description": "PCB"},
            {"hs_code": "8541.10", "description": "Diode"}
        ]
    },
    "SHIP002": {
        "sap_shipment_id": "SHIP002",
        "product_description": "Industrial Servo Motor",
        "shipment_value_usd": 8500,
        "freight_cost_usd": 150,
        "insurance_cost_usd": 30,
        "destination_country": "Malaysia",
        "origin_country": "Japan",
        "bom_items": [
            {"hs_code": "8501.52", "description": "Motor"},
            {"hs_code": "8537.10", "description": "Controller"}
        ]
    },
    "SHIP003": {
        "sap_shipment_id": "SHIP003",
        "product_description": "Copper Wire Harness",
        "shipment_value_usd": 3200,
        "freight_cost_usd": 80,
        "insurance_cost_usd": 15,
        "destination_country": "Malaysia",
        "origin_country": "Vietnam",
        "bom_items": [
            {"hs_code": "7408.11", "description": "Copper wire"}
        ]
    },
    "SHIP004": {
        "sap_shipment_id": "SHIP004",
        "product_description": "Aluminium Heatsink Extrusion",
        "shipment_value_usd": 1800,
        "freight_cost_usd": 60,
        "insurance_cost_usd": 10,
        "destination_country": "Malaysia",
        "origin_country": "Taiwan",
        "bom_items": [
            {"hs_code": "7604.29", "description": "Aluminium profile"}
        ]
    },
    "SHIP005": {
        "sap_shipment_id": "SHIP005",
        "product_description": "Optical Lens Assembly",
        "shipment_value_usd": 22000,
        "freight_cost_usd": 300,
        "insurance_cost_usd": 80,
        "destination_country": "Malaysia",
        "origin_country": "South Korea",
        "bom_items": [
            {"hs_code": "9001.90", "description": "Optical element"}
        ]
    }
}


async def fetch_shipment_from_sap(shipment_id:str) -> dict :
    if settings.SAP_MOCK:
        return MOCK_SHIPMENTS.get(shipment_id, MOCK_SHIPMENTS['SHIP001'])
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.SAP_API_BASE_URL}/api/shipments/{shipment_id}",
                auth=(settings.SAP_USERNAME, settings.SAP_PASSWORD),
                timeout=10
            )
            response.raise_for_status()
            # SAP 'status code' should be 200 (success)
            data = response.json() 
            # upper that response returned data and convert to json format, save as data

            return {
                "sap_shipment_id":shipment_id,
                "product_description":data.get("ProductDescription",""),
                "shipment_value_usd": float(data.get("NetAmount",0)),
                "freight_cost_usd": float(data.get("FreightCost",0)),
                "insurance_cost_usd": float(data.get("InsuranceCost",0)),
                "destination_country": data.get("ShipToCountry",""),
                "origin_country": data.get("OriginCountry",""),
                "bom_items":data.get("BOMItems",[])
                # from that data json , retrieve the value out
            }

    except Exception as e:
        print(f"SAP fetch failed for {shipment_id}:{e}")
        return MOCK_SHIPMENTS["SHIP001"]
        # if falled, return mocked shipments as fallback