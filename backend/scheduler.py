from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings

try:
    from ingestion.tariff_sync import sync_tariff_rates, seed_tariff_data
except ImportError:
    async def sync_tariff_rates():
        print("[scheduler] tariff_sync not available")
        return {}
    async def seed_tariff_data():
        print("[scheduler] seed_tariff_data not available")

try:
    from ingestion.fta_scraper import scrape_miti_fta_rates, seed_fta_data, scrape_jkdm_rates
except ImportError:
    async def scrape_miti_fta_rates():
        print("[scheduler] fta_scraper not available")
        return {}
    async def seed_fta_data():
        print("[scheduler] seed_fta_data not available")
    async def scrape_jkdm_rates():
        print("[scheduler] scrape_jkdm_rates not available")
        return {}

try:
    from ingestion.gazette_monitor import monitor_gazette_rss
except ImportError:
    async def monitor_gazette_rss():
        print("[scheduler] gazette_monitor not available")
        return {}

try:
    from ingestion.annual_rate_updater import apply_annual_rate_updates
except ImportError:
    async def apply_annual_rate_updates():
        print("[scheduler] annual_rate_updater not available")
        return {}


# ── JKDM scrape with change detection ────────────────────────────
async def _run_jkdm_with_change_detection():
    """
    Scrapes JKDM for latest rates. Compares each result against what is
    already stored — logs a pipeline_logs entry if any rate changed.
    """
    from supabase import create_client
    from datetime import datetime, timezone

    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    # Snapshot current fta_rates before scrape
    before = supabase.table("fta_rates").select("fta_name,hs_code,origin_country,preferential_rate_pct").execute()
    before_map = {
        (r["fta_name"], r["hs_code"], r["origin_country"]): r["preferential_rate_pct"]
        for r in (before.data or [])
    }

    result = await scrape_jkdm_rates()

    # Snapshot after scrape
    after = supabase.table("fta_rates").select("fta_name,hs_code,origin_country,preferential_rate_pct").execute()
    changes = []
    for r in (after.data or []):
        key     = (r["fta_name"], r["hs_code"], r["origin_country"])
        old_val = before_map.get(key)
        new_val = r["preferential_rate_pct"]
        if old_val is not None and old_val != new_val:
            changes.append({"fta": r["fta_name"], "hs": r["hs_code"],
                            "origin": r["origin_country"], "old": old_val, "new": new_val})
            print(f"[scheduler] RATE CHANGED: {r['fta_name']} {r['hs_code']} [{r['origin_country']}] "
                  f"{old_val}% → {new_val}%")

    if changes:
        supabase.table("pipeline_logs").insert({
            "event_type":  "jkdm_rates_changed",
            "source_url":  "https://ezhs.customs.gov.my",
            "description": f"{len(changes)} FTA rate(s) changed in scheduled JKDM scrape",
            "detail":      {"changes": changes, "scraped_at": datetime.now(timezone.utc).isoformat()},
        }).execute()
    else:
        print(f"[scheduler] JKDM scrape complete — no rate changes detected. Updated: {result.get('rates_updated', 0)}")


# ── Startup seed ──────────────────────────────────────────────────
async def _run_startup_seeds():
    try:
        from supabase import create_client
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

        tariff_check = supabase.table("tariff_rates").select("id").limit(1).execute()
        if not tariff_check.data:
            print("[scheduler] tariff_rates empty — seeding...")
            await seed_tariff_data()

        fta_check = supabase.table("fta_coverage").select("id").limit(1).execute()
        if not fta_check.data:
            print("[scheduler] fta_coverage empty — seeding...")
            await seed_fta_data()

    except Exception as e:
        print(f"[scheduler] Startup seed failed: {e}")


# ── Main scheduler ────────────────────────────────────────────────
def start_scheduler(app) -> None:
    try:
        scheduler = AsyncIOScheduler()

        # Job 2 — JKDM scrape with change detection every Sunday at 03:00
        scheduler.add_job(
            _run_jkdm_with_change_detection,
            trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="scrape_jkdm_rates",
            name="JKDM Rates Scrape + Change Detection",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # Job 2b — WTO MFN cross-check daily at 02:00 (auto-detects latest year)
        scheduler.add_job(
            sync_tariff_rates,
            trigger=CronTrigger(hour=2, minute=0),
            id="sync_tariff_rates",
            name="WTO MFN Rates (latest year auto-detect)",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # Job 3 — Monitor Federal Gazette (only if enabled)
        if settings.GAZETTE_ENABLED:
            scheduler.add_job(
                monitor_gazette_rss,
                trigger=IntervalTrigger(minutes=15),
                id="monitor_gazette_rss",
                name="Monitor Federal Gazette RSS",
                replace_existing=True,
                misfire_grace_time=300,
            )
            print("  ✓ monitor_gazette_rss  → every 15 minutes")
        else:
            print("  ✗ monitor_gazette_rss  → DISABLED (GAZETTE_ENABLED=false)")

        # Job 4 — Annual rate staging update: Jan 2nd at 03:00
        scheduler.add_job(
            apply_annual_rate_updates,
            trigger=CronTrigger(month=1, day=2, hour=3, minute=0),
            id="annual_rate_update",
            name="Annual FTA Rate Staging Update",
            replace_existing=True,
            misfire_grace_time=86400,
        )

        # Job 5 — Startup seeds (once)
        scheduler.add_job(
            _run_startup_seeds,
            trigger="date",
            id="startup_seeds",
            name="Run Startup Seed Data",
            replace_existing=True,
        )

        scheduler.start()
        app.state.scheduler = scheduler

        @app.on_event("shutdown")
        async def shutdown_scheduler():
            if scheduler.running:
                scheduler.shutdown(wait=False)
                print("[scheduler] Scheduler stopped")

        print("[scheduler] Scheduler started:")
        print("  ✓ scrape_jkdm_rates     → every Sunday 03:00 (change detection)")
        print("  ✓ sync_tariff_rates     → daily 02:00 (WTO auto-latest year)")
        print("  ✓ annual_rate_update    → Jan 2nd 03:00")
        print("  ✓ startup_seeds         → once on startup")

    except Exception as e:
        print(f"[scheduler] Failed to start: {e}")
        print("[scheduler] App will continue without scheduler")
