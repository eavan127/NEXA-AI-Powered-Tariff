from datetime import datetime, timezone
from supabase import create_client
from config import settings


async def apply_annual_rate_updates() -> dict:
    """
    Scheduled Jan 2nd each year.
    Reads rate_staging JSON for every fta_rates row and updates
    preferential_rate_pct to the value applicable for the current year.
    """
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    current_year = datetime.now().year
    updated = 0
    unchanged = 0
    errors = 0

    try:
        rates = (
            supabase.table("fta_rates")
            .select("id,fta_name,hs_code,origin_country,preferential_rate_pct,rate_staging")
            .not_.is_("rate_staging", "null")
            .execute()
        )

        for row in rates.data:
            try:
                staging = row.get("rate_staging") or {}
                if not staging:
                    continue

                # Find most recent year <= current_year
                applicable_rate = None
                for year in sorted(
                    (k for k in staging.keys() if str(k).isdigit()), reverse=True
                ):
                    if int(year) <= current_year:
                        applicable_rate = staging[year]
                        break

                if applicable_rate is None:
                    continue

                old_rate = row.get("preferential_rate_pct")
                if old_rate is not None and abs(float(applicable_rate) - float(old_rate)) < 0.001:
                    unchanged += 1
                    continue

                supabase.table("fta_rates").update({
                    "preferential_rate_pct": applicable_rate,
                    "last_verified_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", row["id"]).execute()

                supabase.table("pipeline_logs").insert({
                    "event_type": "rate_staging_update",
                    "description": (
                        f"{current_year} rate update: {row['fta_name']} "
                        f"HS {row['hs_code']} {old_rate}% → {applicable_rate}%"
                    ),
                    "detail": {
                        "fta_name":  row["fta_name"],
                        "hs_code":   row["hs_code"],
                        "origin":    row["origin_country"],
                        "old_rate":  old_rate,
                        "new_rate":  applicable_rate,
                        "year":      current_year,
                    },
                }).execute()

                print(
                    f"[annual_updater] {row['fta_name']} HS {row['hs_code']} "
                    f"{old_rate}% → {applicable_rate}%"
                )
                updated += 1

            except Exception as e:
                print(f"[annual_updater] Error on row {row.get('id')}: {e}")
                errors += 1

        summary = (
            f"Annual {current_year} rate update: "
            f"{updated} updated, {unchanged} unchanged, {errors} errors"
        )
        print(f"[annual_updater] {summary}")
        supabase.table("pipeline_logs").insert({
            "event_type":  "rate_staging_update",
            "description": summary,
            "detail": {
                "updated": updated, "unchanged": unchanged,
                "errors": errors, "year": current_year,
            },
        }).execute()

    except Exception as e:
        print(f"[annual_updater] Fatal: {e}")
        errors += 1

    return {"updated": updated, "unchanged": unchanged, "errors": errors}
