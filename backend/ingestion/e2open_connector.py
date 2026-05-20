import httpx 
from config import settings 

MOCK_HS_CODES = {
    "SHIP001": "8534.00.0000",
    "SHIP002": "8501.52.0000",
    "SHIP003": "7408.11.1000",
    "SHIP004": "7604.29.9000",
    "SHIP005": "9001.90.0000"
}

async def fetch_hs_from_e2open(shipment_id:str)-> str:
    if settings.E2OPEN_MOCK:
        return MOCK_HS_CODES.get(shipment_id,"8534.00.0000")

    # Real e2open
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.E2OPEN_BASE_URL}/api/v1/classifications/{shipment_id}",
            headers={"Authorization":f"Bearer {settings.E2OPEN_API_KEY}"},
            timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get("hs_code","8534.00.0000" )
    except Exception as e:
        print(f"e2open fetch failed for {shipment_id}:{e}")
        return MOCK_HS_CODES.get(shipment_id,"8534.00.0000" )