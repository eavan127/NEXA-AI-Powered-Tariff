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
    from ingestion.fta_scraper import scrape_miti_fta_rates, seed_fta_data
except ImportError:
    async def scrape_miti_fta_rates():
        print("[scheduler] fta_scraper not available")
        return {}
    async def seed_fta_data():
        print("[scheduler] seed_fta_data not available")

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

        # Job 1 — Sync WTO tariff rates daily at 02:00
        scheduler.add_job(
            sync_tariff_rates,
            trigger=CronTrigger(hour=2, minute=0),
            id="sync_tariff_rates",
            name="Sync WTO Tariff Rates",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # Job 2 — Scrape MITI FTA pages + PDFs + JKDM every Sunday at 03:00
        scheduler.add_job(
            scrape_miti_fta_rates,
            trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="scrape_miti_fta_rates",
            name="Scrape MITI FTA + PDFs + JKDM",
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
        print("  ✓ sync_tariff_rates     → daily at 02:00")
        print("  ✓ scrape_miti_fta_rates → every Sunday at 03:00")
        print("  ✓ annual_rate_update    → Jan 2nd at 03:00")
        print("  ✓ startup_seeds         → once on startup")

    except Exception as e:
        print(f"[scheduler] Failed to start: {e}")
        print("[scheduler] App will continue without scheduler")
