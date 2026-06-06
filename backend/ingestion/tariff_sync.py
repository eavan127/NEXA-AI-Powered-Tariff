import hashlib 
import httpx
from config import settings 
from supabase import create_client

supabase = create_client(settings.SUPABASE_URL,settings.SUPABASE_KEY)

SEED_TARIFF_RATES = [
    {"hs_code": "8534.00", "country_code": "MYS", "mfn_rate_pct": 5.0, "source": "WTO"},
    {"hs_code": "8501.52", "country_code": "MYS", "mfn_rate_pct": 5.0, "source": "WTO"},
    {"hs_code": "7408.11", "country_code": "MYS", "mfn_rate_pct": 5.0, "source": "WTO"},
    {"hs_code": "7604.29", "country_code": "MYS", "mfn_rate_pct": 5.0, "source": "WTO"},
    {"hs_code": "9001.90", "country_code": "MYS", "mfn_rate_pct": 0.0, "source": "WTO"},
]

async def seed_tariff_data() -> None:
    try:
        existing = supabase.table("tariff_rates").select("id").limit(1).execute()
        if len(existing.data) > 0:
            print("Tariff already seeded. Skipping.")
            return 
        print("Seeding initial tariff data...")
        for item in SEED_TARIFF_RATES:
            supabase.table("tariff_rates").insert(item).execute()
    except Exception as e:
        print(f"Error seeding tariff data: {e}")


async def sync_tariff_rates() -> dict:
    result = {"updated": 0, "skipped": 0, "errors": 0}

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                "https://tariffdata.wto.org/api/v1/tariffs",
                params={"reporter": "MYS", "year": "2024"},
                timeout=30
            )
            response.raise_for_status()

            content_hash = hashlib.md5(response.content).hexdigest()
            # hashlib.md5 = feed those bytes into MD5 algorithm
            # hexdigest() = convert the hash into a hexadecimal string

            stored = supabase.table("config").select("value").eq("key", "wto_tariff_hash").execute()

            if stored.data and stored.data[0]["value"] == content_hash:
                total = len(response.json())
                result["skipped"] = total
                print("WTO tariff data unchanged, skipping update")
                return result

            rates = response.json()
            batch = []

            for rate in rates:
                batch.append({
                    "hs_code": rate.get("hsCode", ""),
                    "country_code": "MYS",
                    "mfn_rate_pct": float(rate.get("dutyRate", 0)),
                    "source": "WTO"
                })

                if len(batch) == 100:
                    supabase.table("tariff_rates").upsert(batch).execute()
                    result["updated"] += len(batch)
                    batch = []

            if batch:
                supabase.table("tariff_rates").upsert(batch).execute()
                result["updated"] += len(batch)

            supabase.table("config").upsert({
                "key": "wto_tariff_hash",
                "value": content_hash
            }).execute()

            print(f"Tariff sync complete: {result['updated']} updated")

    except Exception as e:
        print(f"Tariff sync failed: {e}")
        result["errors"] += 1

    return result