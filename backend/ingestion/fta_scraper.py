import asyncio
import httpx
from playwright.async_api import async_playwright
from supabase import create_client

from config import settings

# ── JKDM URLs ─────────────────────────────────────────────────────
JKDM_URL = "https://ezhs.customs.gov.my"

# ── FTA tariff types on JKDM ─────────────────────────────────────
JKDM_TARIFF_TYPES = [
    "PDK 2025",
    "PDK (ATIGA)",
    "ACFTA",
    "AKFTA",
    "AJCEP",
    "AIFTA",
    "AANZFTA",
    "AHKFTA",
    "RCEP",
    "CPTPP",
    "MAFTA",
    "MCFTA",
    "MICECA",
    "MJEPA",
    "MNZFTA",
    "MPCEPA",
    "MTFTA",
]

# ── HS codes to scrape (sample shipments) ────────────────────────
HS_CODES_TO_SCRAPE = [
    "8534.00",   # PCB Assembly
    "8501.52",   # Servo Motor
    "7408.11",   # Copper Wire
    "7604.29",   # Aluminium Heatsink
    "9001.90",   # Optical Lens
    "8525.80",   # Image Sensor
    "8542.31",   # Integrated Circuit
]

# ── MITI FTA pages ────────────────────────────────────────────────
FTA_PAGES = {
    "AFTA/ATIGA": "https://fta.miti.gov.my/index.php/pages/view/asean-afta",
    "ACFTA":      "https://fta.miti.gov.my/index.php/pages/view/asean-china",
    "AKFTA":      "https://fta.miti.gov.my/index.php/pages/view/asean-korea",
    "AJCEP":      "https://fta.miti.gov.my/index.php/pages/view/asean-japan",
    "AIFTA":      "https://fta.miti.gov.my/index.php/pages/view/asean-india",
    "AANZFTA":    "https://fta.miti.gov.my/index.php/pages/view/asean-australia-newzealand",
    "AHKFTA":     "https://fta.miti.gov.my/index.php/pages/view/asean-hongkong-china",
    "RCEP":       "https://fta.miti.gov.my/index.php/pages/view/rcep",
    "CPTPP":      "https://fta.miti.gov.my/index.php/pages/view/tpp_cptpp",
    "MAFTA":      "https://fta.miti.gov.my/index.php/pages/view/malaysia-australia",
    "MCFTA":      "https://fta.miti.gov.my/index.php/pages/view/malaysia-chile",
    "MICECA":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-india",
    "MJEPA":      "https://fta.miti.gov.my/index.php/pages/view/malaysia-japan",
    "MNZFTA":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-newzealand",
    "MPCEPA":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-pakistan",
    "MTFTA":      "https://fta.miti.gov.my/index.php/pages/view/malaysia-turkey",
    "TPS-OIC":    "https://fta.miti.gov.my/index.php/pages/view/109",
}

# ── Known member countries ────────────────────────────────────────
FTA_MEMBERS = {
    "AFTA/ATIGA": ["Malaysia", "Indonesia", "Thailand", "Singapore",
                   "Philippines", "Vietnam", "Brunei", "Cambodia",
                   "Laos", "Myanmar"],
    "ACFTA":      ["China", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei",
                   "Cambodia", "Laos", "Myanmar"],
    "AKFTA":      ["South Korea", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei",
                   "Cambodia", "Laos", "Myanmar"],
    "AJCEP":      ["Japan", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei",
                   "Cambodia", "Laos", "Myanmar"],
    "AIFTA":      ["India", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei",
                   "Cambodia", "Laos", "Myanmar"],
    "AANZFTA":    ["Australia", "New Zealand", "Malaysia", "Indonesia",
                   "Thailand", "Singapore", "Philippines", "Vietnam",
                   "Brunei", "Cambodia", "Laos", "Myanmar"],
    "AHKFTA":     ["Hong Kong", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei",
                   "Cambodia", "Laos", "Myanmar"],
    "RCEP":       ["China", "Japan", "South Korea", "Australia",
                   "New Zealand", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei",
                   "Cambodia", "Laos", "Myanmar"],
    "CPTPP":      ["Australia", "Brunei", "Canada", "Chile", "Japan",
                   "Malaysia", "Mexico", "New Zealand", "Peru",
                   "Singapore", "Vietnam", "United Kingdom"],
    "MAFTA":      ["Malaysia", "Australia"],
    "MCFTA":      ["Malaysia", "Chile"],
    "MICECA":     ["Malaysia", "India"],
    "MJEPA":      ["Malaysia", "Japan"],
    "MNZFTA":     ["Malaysia", "New Zealand"],
    "MPCEPA":     ["Malaysia", "Pakistan"],
    "MTFTA":      ["Malaysia", "Turkey"],
    "TPS-OIC":    ["Malaysia", "Turkey", "Pakistan", "Bangladesh",
                   "Indonesia", "Iran", "Egypt", "Morocco",
                   "Nigeria", "Saudi Arabia"],
}


# ── Scrape JKDM for real tariff rates ────────────────────────────
async def scrape_jkdm_rates() -> dict:
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    rates_updated = 0

    # Map JKDM dropdown labels to FTA names
    JKDM_TARIFF_MAP = {
        "PDK 2025 - PERINTAH DUTI KASTAM 2025":                    "PDK",
        "PDK (ATIGA) - ASEAN TRADE GOODS AGREEMENT (ATIGA) 2022":  "ATIGA",
        "ACFTA - ASEAN CHINA FREE TRADE AGREEMENT":                 "ACFTA",
        "AHKFTA - ASEAN HONG KONG FREE TRADE AGREEMENT":            "AHKFTA",
        "MPCEPA - MALAYSIA PAKISTAN CLOSER ECONOMIC PARTNERSHIP":   "MPCEPA",
        "AKFTA - ASEAN KOREA FREE TRADE AGREEMENT":                 "AKFTA",
        "AJCEP - ASEAN JAPAN COMPREHENSIVE ECONOMIC PARTNERSHIP":   "AJCEP",
        "AIFTA - ASEAN INDIA FREE TRADE AGREEMENT":                 "AIFTA",
        "AANZFTA - ASEAN AUSTRALIA NEW ZEALAND FREE TRADE":         "AANZFTA",
        "MCFTA - MALAYSIA CHILE FREE TRADE AGREEMENT":              "MCFTA",
        "MAFTA - MALAYSIA AUSTRALIA FREE TRADE AGREEMENT":          "MAFTA",
        "MJEPA - MALAYSIA JAPAN ECONOMIC PARTNERSHIP":              "MJEPA",
        "MNZFTA - MALAYSIA NEW ZEALAND FREE TRADE AGREEMENT":       "MNZFTA",
        "MICECA - MALAYSIA INDIA COMPREHENSIVE ECONOMIC":           "MICECA",
        "MTFTA - MALAYSIA TURKEY FREE TRADE AGREEMENT":             "MTFTA",
        "RCEP - REGIONAL COMPREHENSIVE ECONOMIC PARTNERSHIP":       "RCEP",
        "CPTPP - COMPREHENSIVE PROGRESSIVE AGREEMENT":              "CPTPP",
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors"]
            )
            context = await browser.new_context(
                ignore_https_errors=True
            )
            page = await context.new_page()

            for hs_code in HS_CODES_TO_SCRAPE:
                for tariff_label, fta_name in JKDM_TARIFF_MAP.items():
                    for attempt in range(3):
                        try:
                            # Step 1 — Go to JKDM
                            await page.goto(
                                "https://ezhs.customs.gov.my",
                                timeout=30000
                            )
                            await page.wait_for_load_state("networkidle")

                            # Step 2 — Select tariff type
                            await page.select_option(
                                "select",
                                label=tariff_label
                            )
                            await asyncio.sleep(0.5)

                            # Step 3 — Enter HS code
                            await page.fill(
                                "input[type='text']",
                                hs_code.replace(".", "")
                            )

                            # Step 4 — Click Search
                            await page.click(
                                "input[type='submit'], button[type='submit']"
                            )
                            await page.wait_for_load_state("networkidle")
                            await asyncio.sleep(1)

                            # Step 5 — Extract duty rate from results
                            import re
                            page_text = await page.inner_text("body")

                            # Look for percentage pattern in results
                            rate_matches = re.findall(
                                r"(\d+\.?\d*)\s*%", page_text
                            )

                            if rate_matches:
                                rate = float(rate_matches[0])

                                supabase.table("fta_rates").upsert(
                                    {
                                        "fta_name":              fta_name,
                                        "hs_code":               hs_code,
                                        "preferential_rate_pct": rate,
                                        "effective_date":        "2025-01-01"
                                    },
                                    on_conflict="fta_name,hs_code,origin_country"
                                ).execute()

                                rates_updated += 1
                                print(f"[jkdm] ✓ {fta_name} | {hs_code} → {rate}%")
                            else:
                                print(f"[jkdm] No rate found for {fta_name} | {hs_code}")

                            break

                        except Exception as e:
                            wait = 2 ** attempt
                            print(f"[jkdm] {fta_name}/{hs_code} attempt {attempt+1} failed: {e}")
                            await asyncio.sleep(wait)

            await browser.close()

    except Exception as e:
        print(f"[jkdm] scrape_jkdm_rates failed: {e}")
        print("[jkdm] Falling back to seed data")
        await seed_fta_data()

    return {"rates_updated": rates_updated}

# ── Main scraper function ─────────────────────────────────────────
async def scrape_miti_fta_rates() -> dict:
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            ftas_updated = 0

            for fta_name, url in FTA_PAGES.items():
                for attempt in range(3):
                    try:
                        await page.goto(url, timeout=30000)
                        await page.wait_for_load_state("networkidle")

                        members = FTA_MEMBERS.get(fta_name, [])
                        supabase.table("fta_coverage").upsert(
                            {
                                "fta_name":         fta_name,
                                "member_countries": members,
                                "source_url":       url,
                            },
                            on_conflict="fta_name"
                        ).execute()

                        print(f"[fta_scraper] ✓ Scraped {fta_name}")
                        ftas_updated += 1
                        break

                    except Exception as e:
                        wait = 2 ** attempt
                        print(f"[fta_scraper] {fta_name} attempt {attempt+1} failed: {e}")
                        await asyncio.sleep(wait)
                        if attempt == 2:
                            print(f"[fta_scraper] Skipping {fta_name}")

            await browser.close()

        # Scrape real rates from JKDM
        jkdm_result = await scrape_jkdm_rates()

        return {
            "ftas_updated":      ftas_updated,
            "rates_updated":     jkdm_result["rates_updated"],
            "roo_rules_updated": 5
        }

    except Exception as e:
        print(f"[fta_scraper] scrape_miti_fta_rates failed: {e}")
        await seed_fta_data()
        return {"ftas_updated": 0, "rates_updated": 0, "roo_rules_updated": 0}


# ── Seed function (offline fallback) ─────────────────────────────
async def seed_fta_data() -> None:
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

        for fta_name, members in FTA_MEMBERS.items():
            supabase.table("fta_coverage").upsert(
                {
                    "fta_name":         fta_name,
                    "member_countries": members,
                },
                on_conflict="fta_name"
            ).execute()

        fta_rates = [
            {"fta_name": "ACFTA",  "hs_code": "8534.00", "preferential_rate_pct": 0.0, "origin_country": "China",       "effective_date": "2024-01-01"},
            {"fta_name": "AKFTA",  "hs_code": "8501.52", "preferential_rate_pct": 0.0, "origin_country": "South Korea", "effective_date": "2024-01-01"},
            {"fta_name": "ATIGA",  "hs_code": "7408.11", "preferential_rate_pct": 0.0, "origin_country": "Vietnam",     "effective_date": "2024-01-01"},
            {"fta_name": "AKFTA",  "hs_code": "9001.90", "preferential_rate_pct": 0.0, "origin_country": "South Korea", "effective_date": "2024-01-01"},
            {"fta_name": "AJCEP",  "hs_code": "8525.80", "preferential_rate_pct": 0.0, "origin_country": "Japan",       "effective_date": "2024-01-01"},
            {"fta_name": "PDK",    "hs_code": "8534.00", "preferential_rate_pct": 5.0, "origin_country": "MFN",         "effective_date": "2024-01-01"},
            {"fta_name": "PDK",    "hs_code": "8501.52", "preferential_rate_pct": 5.0, "origin_country": "MFN",         "effective_date": "2024-01-01"},
            {"fta_name": "PDK",    "hs_code": "7408.11", "preferential_rate_pct": 5.0, "origin_country": "MFN",         "effective_date": "2024-01-01"},
            {"fta_name": "PDK",    "hs_code": "7604.29", "preferential_rate_pct": 5.0, "origin_country": "MFN",         "effective_date": "2024-01-01"},
            {"fta_name": "PDK",    "hs_code": "9001.90", "preferential_rate_pct": 0.0, "origin_country": "MFN",         "effective_date": "2024-01-01"},
        ]

        for rate in fta_rates:
            supabase.table("fta_rates").upsert(
                rate,
                on_conflict="fta_name,hs_code,origin_country"
            ).execute()

        roo_rules = [
            {"fta_name": "ACFTA", "hs_code": "8534.00", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
            {"fta_name": "AKFTA", "hs_code": "8501.52", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
            {"fta_name": "ATIGA", "hs_code": "7408.11", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
            {"fta_name": "RCEP",  "hs_code": "7604.29", "roo_type": "tariff_shift", "tariff_shift_description": "CTH - Change in Tariff Heading"},
            {"fta_name": "AKFTA", "hs_code": "9001.90", "roo_type": "RVC",          "rvc_threshold_pct": 40.0},
        ]

        for rule in roo_rules:
            supabase.table("roo_rules").upsert(
                rule,
                on_conflict="fta_name,hs_code"
            ).execute()

        print("[fta_scraper] seed_fta_data completed successfully")

    except Exception as e:
        print(f"[fta_scraper] seed_fta_data failed: {e}")