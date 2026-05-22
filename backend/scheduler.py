from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings

try:
    from ingestion.tariff_sync import sync_tariff_rates, seed_tariff_data
except ImportError:
    async def sync_tariff_rates():
        print("[scheduler] tariff_sync not available yet")
        return {}
    async def seed_tariff_data():
        print("[scheduler] seed_tariff_data not available yet")

try:
    from ingestion.fta_scraper import scrape_miti_fta_rates, seed_fta_data
except ImportError:
    async def scrape_miti_fta_rates():
        print("[scheduler] fta_scraper not available yet")
        return {}
    async def seed_fta_data():
        print("[scheduler] seed_fta_data not available yet")

try:
    from ingestion.gazette_monitor import monitor_gazette_rss
except ImportError:
    async def monitor_gazette_rss():
        print("[scheduler] gazette_monitor not available yet")
        return {}


# ── Startup seed jobs 
async def _run_startup_seeds():
    try:
        from config import settings
        supabase_url = settings.SUPABASE_URL
    except Exception:
        print("[scheduler] config not available — skipping seeds")
        return

    try:
        from supabase import create_client
        supabase = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )

        # Seed tariff rates if table is empty
        tariff_check = supabase.table("tariff_rates") \
            .select("id") \
            .limit(1) \
            .execute()

        if not tariff_check.data:
            print("[scheduler] tariff_rates empty — seeding...")
            await seed_tariff_data()

        # Seed FTA data if table is empty
        fta_check = supabase.table("fta_coverage") \
            .select("id") \
            .limit(1) \
            .execute()

        if not fta_check.data:
            print("[scheduler] fta_coverage empty — seeding...")
            await seed_fta_data()

    except Exception as e:
        print(f"[scheduler] Startup seed failed: {e}")


# ── Main scheduler function ───────────────────────────────────────
def start_scheduler(app) -> None:
    try:
        scheduler = AsyncIOScheduler()

        # Job 1 — Sync tariff rates daily at 2:00 AM
        scheduler.add_job(
            sync_tariff_rates,
            trigger=CronTrigger(hour=2, minute=0),
            id="sync_tariff_rates",
            name="Sync WTO/USITC Tariff Rates",
            replace_existing=True,
            misfire_grace_time=3600
        )

        # Job 2 — Scrape MITI FTA rates every Sunday at 3:00 AM
        scheduler.add_job(
            scrape_miti_fta_rates,
            trigger=CronTrigger(
                day_of_week="sun",
                hour=3,
                minute=0
            ),
            id="scrape_miti_fta_rates",
            name="Scrape MITI FTA + JKDM Rates",
            replace_existing=True,
            misfire_grace_time=3600
        )

        # Job 3 — Monitor gazette RSS every 15 minutes
        scheduler.add_job(
            monitor_gazette_rss,
            trigger=IntervalTrigger(minutes=15),
            id="monitor_gazette_rss",
            name="Monitor Federal Gazette RSS",
            replace_existing=True,
            misfire_grace_time=300
        )

        # Job 4 — Run startup seeds once
        scheduler.add_job(
            _run_startup_seeds,
            trigger="date",
            id="startup_seeds",
            name="Run Startup Seed Data",
            replace_existing=True
        )

        # Start scheduler
        scheduler.start()

        # Store on app state so it can be accessed later
        app.state.scheduler = scheduler

        # Graceful shutdown when app stops
        @app.on_event("shutdown")
        async def shutdown_scheduler():
            if scheduler.running:
                scheduler.shutdown(wait=False)
                print("[scheduler] Scheduler stopped")

        print("[scheduler] Scheduler started with 4 jobs:")
        print("  ✓ sync_tariff_rates    → daily at 02:00")
        print("  ✓ scrape_miti_fta_rates → every Sunday at 03:00")
        print("  ✓ monitor_gazette_rss  → every 15 minutes")
        print("  ✓ startup_seeds        → once on startup")

    except Exception as e:
        print(f"[scheduler] Failed to start: {e}")
        print("[scheduler] App will continue without scheduler")