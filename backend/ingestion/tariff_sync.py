import hashlib
from datetime import datetime
import httpx
from config import settings
from supabase import create_client

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

WTO_HS_CODES = ["853400", "850110", "760429", "854231", "900190"]


async def seed_tariff_data() -> None:
    print("[tariff] MFN rates come from JKDM PDK scraper (primary) or WTO API (cross-check).")


async def _find_latest_wto_year(client: httpx.AsyncClient, hs_nodot: str) -> tuple[str | None, dict | None]:
    """
    Walk back from current year until WTO returns data.
    Returns (year_string, rate_data_dict) or (None, None) if unavailable.
    """
    current_year = datetime.now().year
    for year in range(current_year, current_year - 4, -1):
        try:
            response = await client.get(
                "https://tariffdata.wto.org/api/v1/tariffs",
                params={"reporter": "MYS", "product": hs_nodot, "year": str(year)},
                timeout=30,
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            data = response.json()
            if data:
                return str(year), response
        except Exception:
            continue
    return None, None


async def sync_tariff_rates() -> dict:
    """
    Fetch MFN rates from WTO tariff API using the latest available year (auto-detected).
    Detects rate changes vs what is already stored and logs them.
    Falls back to JKDM PDK rates if WTO is unreachable.
    """
    result = {"updated": 0, "skipped": 0, "errors": 0, "changed": 0, "pdk_promoted": 0}

    async with httpx.AsyncClient(verify=False) as client:
        for hs_nodot in WTO_HS_CODES:
            hs_dot = f"{hs_nodot[:4]}.{hs_nodot[4:6]}"

            year, response = await _find_latest_wto_year(client, hs_nodot)

            if year is None or response is None:
                # WTO unavailable — promote PDK rate as MFN baseline
                pdk = (
                    supabase.table("fta_rates")
                    .select("preferential_rate_pct")
                    .eq("fta_name", "PDK")
                    .eq("hs_code", hs_dot)
                    .limit(1)
                    .execute()
                )
                if pdk.data:
                    mfn_rate = pdk.data[0]["preferential_rate_pct"]
                    supabase.table("tariff_rates").upsert(
                        {
                            "hs_code":        hs_dot,
                            "country_code":   "MYS",
                            "mfn_rate_pct":   mfn_rate,
                            "source":         "JKDM_PDK2025",
                            "effective_date": "2025-01-01",
                        },
                        on_conflict="hs_code,country_code",
                    ).execute()
                    print(f"[tariff] PDK fallback MFN: HS {hs_dot} = {mfn_rate}%")
                    result["pdk_promoted"] += 1
                else:
                    print(f"[tariff] No MFN source found for {hs_dot}")
                    result["errors"] += 1
                continue

            content_hash = hashlib.md5(response.content).hexdigest()
            cache_key    = f"wto_hash_{hs_nodot}"

            stored = supabase.table("config").select("value").eq("key", cache_key).execute()
            if stored.data and stored.data[0]["value"] == content_hash:
                print(f"[tariff] WTO {hs_nodot} ({year}) unchanged")
                result["skipped"] += 1
                continue

            rates     = response.json()
            rate_data = rates[0] if isinstance(rates, list) else rates
            new_rate  = float(rate_data.get("dutyRate", 0))

            # Cross-check WTO rate vs JKDM PDK rate already stored
            pdk = (
                supabase.table("fta_rates")
                .select("preferential_rate_pct")
                .eq("fta_name", "PDK").eq("hs_code", hs_dot)
                .limit(1).execute()
            )
            if pdk.data:
                pdk_rate = float(pdk.data[0]["preferential_rate_pct"])
                if pdk_rate != new_rate:
                    print(f"[tariff] CROSSCHECK MISMATCH: HS {hs_dot} — WTO({year})={new_rate}% vs PDK={pdk_rate}%")
                    supabase.table("pipeline_logs").insert({
                        "event_type":  "mfn_crosscheck_mismatch",
                        "source_url":  "https://tariffdata.wto.org",
                        "description": f"HS {hs_dot}: WTO {year}={new_rate}% but JKDM PDK={pdk_rate}% — review needed",
                        "detail":      {"hs_code": hs_dot, "wto_rate": new_rate, "pdk_rate": pdk_rate, "wto_year": year},
                    }).execute()
                else:
                    print(f"[tariff] CROSSCHECK OK: HS {hs_dot} WTO({year})={new_rate}% matches PDK={pdk_rate}%")

            # Detect change vs previously stored tariff_rates value
            existing = (
                supabase.table("tariff_rates")
                .select("mfn_rate_pct", "source")
                .eq("hs_code", hs_dot).eq("country_code", "MYS")
                .limit(1).execute()
            )
            if existing.data:
                old_rate = float(existing.data[0]["mfn_rate_pct"])
                if old_rate != new_rate:
                    print(f"[tariff] RATE CHANGED: HS {hs_dot} MFN {old_rate}% → {new_rate}% (WTO {year})")
                    supabase.table("pipeline_logs").insert({
                        "event_type":  "mfn_rate_changed",
                        "source_url":  "https://tariffdata.wto.org",
                        "description": f"MFN rate changed: HS {hs_dot} = {old_rate}% → {new_rate}%",
                        "detail":      {"hs_code": hs_dot, "old_rate": old_rate, "new_rate": new_rate, "wto_year": year},
                    }).execute()
                    result["changed"] += 1

            supabase.table("tariff_rates").upsert(
                {
                    "hs_code":        hs_dot,
                    "country_code":   "MYS",
                    "mfn_rate_pct":   new_rate,
                    "source":         f"WTO_API_{year}",
                    "effective_date": f"{year}-01-01",
                },
                on_conflict="hs_code,country_code",
            ).execute()

            supabase.table("config").upsert(
                {"key": cache_key, "value": content_hash}, on_conflict="key"
            ).execute()

            print(f"[tariff] WTO MFN (latest={year}): HS {hs_dot} = {new_rate}%")
            result["updated"] += 1

    return result
