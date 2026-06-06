import asyncio
import re
import time
import httpx
from datetime import datetime, timezone
from supabase import create_client

from config import settings
from ingestion.change_detector import has_source_changed, store_source_hash
from ingestion.pdf_extractor import extract_fta_rates_from_pdf

# ── JKDM ─────────────────────────────────────────────────────────
HS_CODES_TO_SCRAPE = [
    "8534.00", "8501.52", "7408.11", "7604.29",
    "9001.90", "8525.80", "8542.31",
]

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

# ── MITI page URLs ────────────────────────────────────────────────
FTA_PAGES = {
    "ATIGA":      "https://fta.miti.gov.my/index.php/pages/view/asean-afta",
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

# ── Complete metadata for all 17 FTAs ────────────────────────────
FTA_COVERAGE_META = {
    "AKFTA": {
        "effective_date": "2007-06-01", "in_force_date": "2007-06-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/asean-korea",
        "description":    "ASEAN-Korea Free Trade Agreement",
        "roo_summary":    "RVC >= 40% (build-up) OR CTH",
    },
    "ATIGA": {
        "effective_date": "2010-01-01", "in_force_date": "2010-01-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/asean-afta",
        "description":    "ASEAN Trade in Goods Agreement (ATIGA)",
        "roo_summary":    "RVC >= 40% (ATIGA build-up) OR CTH at 6-digit level",
    },
    "AHKFTA": {
        "effective_date": "2019-06-17", "in_force_date": "2019-06-17",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/asean-hongkong-china",
        "description":    "ASEAN-Hong Kong Free Trade Agreement",
        "roo_summary":    "RVC >= 35% OR CTH",
    },
    "ACFTA": {
        "effective_date": "2005-07-20", "in_force_date": "2005-07-20",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/asean-china",
        "description":    "ASEAN-China Free Trade Agreement",
        "roo_summary":    "RVC >= 40% OR CTH at subheading level",
    },
    "MICECA": {
        "effective_date": "2012-07-01", "in_force_date": "2012-07-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-india",
        "description":    "Malaysia-India Comprehensive Economic Cooperation Agreement",
        "roo_summary":    "RVC >= 35% OR CTH",
    },
    "AIFTA": {
        "effective_date": "2010-01-01", "in_force_date": "2010-01-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/asean-india",
        "description":    "ASEAN-India Free Trade Agreement",
        "roo_summary":    "RVC >= 35% OR CTH; India has Sensitive Track exclusions",
    },
    "MPCEPA": {
        "effective_date": "2008-01-01", "in_force_date": "2008-01-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-pakistan",
        "description":    "Malaysia-Pakistan Closer Economic Partnership Agreement",
        "roo_summary":    "RVC >= 40%",
    },
    "MCFTA": {
        "effective_date": "2012-02-25", "in_force_date": "2012-02-25",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-chile",
        "description":    "Malaysia-Chile Free Trade Agreement",
        "roo_summary":    "RVC >= 40% OR CTH",
    },
    "AJCEP": {
        "effective_date": "2008-12-01", "in_force_date": "2008-12-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/asean-japan",
        "description":    "ASEAN-Japan Comprehensive Economic Partnership",
        "roo_summary":    "RVC >= 40% OR CTH; compare with MJEPA, use lower rate",
    },
    "MNZFTA": {
        "effective_date": "2010-08-01", "in_force_date": "2010-08-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-newzealand",
        "description":    "Malaysia-New Zealand Free Trade Agreement",
        "roo_summary":    "RVC >= 40%; NZ also covered by AANZFTA and CPTPP",
    },
    "RCEP": {
        "effective_date": "2022-01-01", "in_force_date": "2022-01-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/rcep",
        "description":    "Regional Comprehensive Economic Partnership",
        "roo_summary":    "RVC >= 40% (build-up) OR CTSH; cumulation allowed across all RCEP members",
    },
    "TPS-OIC": {
        "effective_date": "1991-01-01", "in_force_date": "1991-01-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/109",
        "description":    "Trade Preferential System — Organisation of Islamic Cooperation",
        "roo_summary":    "RVC >= 40%; margin of preference, not zero rate",
    },
    "MTFTA": {
        "effective_date": "2015-08-01", "in_force_date": "2015-08-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-turkey",
        "description":    "Malaysia-Turkey Free Trade Agreement",
        "roo_summary":    "RVC >= 40% OR CTH; some goods staging through 2026-2028",
    },
    "MJEPA": {
        "effective_date": "2008-07-13", "in_force_date": "2008-07-13",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-japan",
        "description":    "Malaysia-Japan Economic Partnership Agreement",
        "roo_summary":    "More generous than AJCEP for some goods; always check both",
    },
    "AANZFTA": {
        "effective_date": "2012-01-01", "in_force_date": "2012-01-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/asean-australia-newzealand",
        "description":    "ASEAN-Australia-New Zealand Free Trade Agreement",
        "roo_summary":    "RVC >= 40% OR CTH; AU also covered by MAFTA and RCEP",
    },
    "CPTPP": {
        "effective_date": "2022-11-29", "in_force_date": "2022-11-29",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/tpp_cptpp",
        "description":    "Comprehensive and Progressive Agreement for Trans-Pacific Partnership",
        "roo_summary":    "RVC >= 40% OR CTH; categories EIF/B5/B7/B10/B12/X",
    },
    "MAFTA": {
        "effective_date": "2013-01-01", "in_force_date": "2013-01-01",
        "source_url":     "https://fta.miti.gov.my/index.php/pages/view/malaysia-australia",
        "description":    "Malaysia-Australia Free Trade Agreement",
        "roo_summary":    "RVC >= 40%; most goods at 0%; AU also covered by AANZFTA, RCEP, CPTPP",
    },
}

FTA_MEMBERS = {
    "ATIGA":      ["Malaysia", "Indonesia", "Thailand", "Singapore",
                   "Philippines", "Vietnam", "Brunei", "Cambodia", "Laos", "Myanmar"],
    "ACFTA":      ["China", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei", "Cambodia", "Laos", "Myanmar"],
    "AKFTA":      ["South Korea", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei", "Cambodia", "Laos", "Myanmar"],
    "AJCEP":      ["Japan", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei", "Cambodia", "Laos", "Myanmar"],
    "AIFTA":      ["India", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei", "Cambodia", "Laos", "Myanmar"],
    "AANZFTA":    ["Australia", "New Zealand", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei", "Cambodia", "Laos", "Myanmar"],
    "AHKFTA":     ["Hong Kong", "Malaysia", "Indonesia", "Thailand",
                   "Singapore", "Philippines", "Vietnam", "Brunei", "Cambodia", "Laos", "Myanmar"],
    "RCEP":       ["China", "Japan", "South Korea", "Australia", "New Zealand",
                   "Malaysia", "Indonesia", "Thailand", "Singapore", "Philippines",
                   "Vietnam", "Brunei", "Cambodia", "Laos", "Myanmar"],
    "CPTPP":      ["Australia", "Brunei", "Canada", "Chile", "Japan", "Malaysia",
                   "Mexico", "New Zealand", "Peru", "Singapore", "Vietnam", "United Kingdom"],
    "MAFTA":      ["Malaysia", "Australia"],
    "MCFTA":      ["Malaysia", "Chile"],
    "MICECA":     ["Malaysia", "India"],
    "MJEPA":      ["Malaysia", "Japan"],
    "MNZFTA":     ["Malaysia", "New Zealand"],
    "MPCEPA":     ["Malaysia", "Pakistan"],
    "MTFTA":      ["Malaysia", "Turkey"],
    "TPS-OIC":    ["Malaysia", "Turkey", "Pakistan", "Bangladesh", "Indonesia",
                   "Iran", "Egypt", "Morocco", "Nigeria", "Saudi Arabia",
                   "Jordan", "Tunisia", "Senegal", "Cameroon", "Burkina Faso"],
}

COUNTRY_CODE_MAP = {
    "CHN": "China",       "JPN": "Japan",         "KOR": "South Korea",
    "AUS": "Australia",   "NZL": "New Zealand",   "IND": "India",
    "CHL": "Chile",       "PAK": "Pakistan",       "TUR": "Turkey",
    "IDN": "Indonesia",   "THA": "Thailand",       "SGP": "Singapore",
    "PHL": "Philippines", "VNM": "Vietnam",        "BRN": "Brunei",
    "KHM": "Cambodia",    "LAO": "Laos",           "MMR": "Myanmar",
    "HKG": "Hong Kong",   "CAN": "Canada",         "MEX": "Mexico",
    "GBR": "United Kingdom", "PER": "Peru",        "BGD": "Bangladesh",
}

MITI_PDF_DIRS = {
    "RCEP":   "https://fta.miti.gov.my/miti-fta/resources/RCEP/",
    "CPTPP":  "https://fta.miti.gov.my/miti-fta/resources/CPTPP/",
    "MAFTA":  "https://fta.miti.gov.my/miti-fta/resources/MAFTA/",
    "MJEPA":  "https://fta.miti.gov.my/miti-fta/resources/MJEPA/",
    "MNZFTA": "https://fta.miti.gov.my/miti-fta/resources/MNZFTA/",
}


# ════════════════════════════════════════════════════════════════
# JKDM — sync Playwright wrapped in run_in_executor
# ════════════════════════════════════════════════════════════════

async def scrape_jkdm_rates() -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _scrape_jkdm_sync)


def _scrape_jkdm_sync() -> dict:
    from playwright.sync_api import sync_playwright
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    rates_updated = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, args=["--ignore-certificate-errors"]
            )
            context = browser.new_context(ignore_https_errors=True)
            page    = context.new_page()

            for hs_code in HS_CODES_TO_SCRAPE:
                for tariff_label, fta_name in JKDM_TARIFF_MAP.items():
                    for attempt in range(3):
                        try:
                            page.goto("https://ezhs.customs.gov.my", timeout=30000)
                            page.wait_for_load_state("networkidle")
                            page.select_option("select", label=tariff_label)
                            time.sleep(0.5)
                            page.fill("input[type='text']", hs_code.replace(".", ""))
                            page.click("input[type='submit'], button[type='submit']")
                            page.wait_for_load_state("networkidle")
                            time.sleep(1)

                            page_text    = page.inner_text("body")
                            rate_matches = re.findall(r"(\d+\.?\d*)\s*%", page_text)

                            if rate_matches:
                                rate = float(rate_matches[0])
                                supabase.table("fta_rates").upsert(
                                    {
                                        "fta_name":              fta_name,
                                        "hs_code":               hs_code,
                                        "preferential_rate_pct": rate,
                                        "effective_date":        "2025-01-01",
                                    },
                                    on_conflict="fta_name,hs_code,origin_country"
                                ).execute()
                                rates_updated += 1
                                print(f"[jkdm] {fta_name} | {hs_code} → {rate}%")
                            else:
                                print(f"[jkdm] No rate: {fta_name} | {hs_code}")
                            break

                        except Exception as e:
                            print(f"[jkdm] {fta_name}/{hs_code} attempt {attempt+1}: {e}")
                            time.sleep(2 ** attempt)

            browser.close()

    except Exception as e:
        print(f"[jkdm] _scrape_jkdm_sync failed: {e}")

    return {"rates_updated": rates_updated}


# ════════════════════════════════════════════════════════════════
# MITI FTA pages — sync Playwright wrapped in run_in_executor
# ════════════════════════════════════════════════════════════════

async def scrape_miti_fta_rates() -> dict:
    loop = asyncio.get_event_loop()

    # Step 1: update fta_coverage metadata (Playwright, sync in thread)
    fta_result  = await loop.run_in_executor(None, _scrape_miti_coverage_sync)

    # Step 2: download + parse PDFs (httpx, stays async)
    pdf_result  = await scrape_miti_fta_pdfs()

    # Step 3: JKDM sample rates (Playwright, sync in thread)
    jkdm_result = await scrape_jkdm_rates()

    return {
        "ftas_updated":       fta_result.get("ftas_updated", 0),
        "pdf_rates_upserted": pdf_result.get("pdfs_rates_upserted", 0),
        "jkdm_rates_updated": jkdm_result["rates_updated"],
    }


def _scrape_miti_coverage_sync() -> dict:
    """Visit each MITI FTA page and upsert fta_coverage metadata."""
    from playwright.sync_api import sync_playwright
    supabase    = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    ftas_updated = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()

            for fta_name, url in FTA_PAGES.items():
                meta    = FTA_COVERAGE_META.get(fta_name, {})
                members = FTA_MEMBERS.get(fta_name, [])

                for attempt in range(3):
                    try:
                        page.goto(url, timeout=30000)
                        page.wait_for_load_state("networkidle")

                        supabase.table("fta_coverage").upsert(
                            {
                                "fta_name":         fta_name,
                                "member_countries": members,
                                "source_url":       url,
                                "effective_date":   meta.get("effective_date"),
                                "in_force_date":    meta.get("in_force_date"),
                                "description":      meta.get("description"),
                                "roo_summary":      meta.get("roo_summary"),
                                "last_scraped_at":  datetime.now(timezone.utc).isoformat(),
                            },
                            on_conflict="fta_name"
                        ).execute()

                        print(f"[fta_scraper] Coverage updated: {fta_name}")
                        ftas_updated += 1
                        break

                    except Exception as e:
                        print(f"[fta_scraper] {fta_name} attempt {attempt+1}: {e}")
                        time.sleep(2 ** attempt)
                        if attempt == 2:
                            print(f"[fta_scraper] Skipping {fta_name}")

            browser.close()

    except Exception as e:
        print(f"[fta_scraper] _scrape_miti_coverage_sync failed: {e}")

    return {"ftas_updated": ftas_updated}


def _get_remaining_pdf_links_sync(remaining: dict) -> dict:
    """Use sync Playwright to collect PDF links from MITI pages."""
    from playwright.sync_api import sync_playwright
    pdf_map = {}  # fta_name → [pdf_url, ...]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
            page    = browser.new_page()

            for fta_name, page_url in remaining.items():
                try:
                    page.goto(page_url, timeout=30000)
                    page.wait_for_load_state("networkidle")
                    hrefs = page.evaluate(
                        "() => Array.from(document.querySelectorAll('a[href]'))"
                        ".map(a => a.href)"
                        ".filter(h => h.toLowerCase().endsWith('.pdf'))"
                    )
                    if hrefs:
                        pdf_map[fta_name] = hrefs
                        print(f"[fta_pdfs] {fta_name}: found {len(hrefs)} PDF links")
                except Exception as e:
                    print(f"[fta_pdfs] Could not scrape {fta_name} page: {e}")

            browser.close()

    except Exception as e:
        print(f"[fta_pdfs] _get_remaining_pdf_links_sync failed: {e}")

    return pdf_map


# ════════════════════════════════════════════════════════════════
# MITI PDF scraper — httpx (async) + Playwright fallback (sync thread)
# ════════════════════════════════════════════════════════════════

async def scrape_miti_fta_pdfs() -> dict:
    supabase      = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    total_updated = 0
    total_skipped = 0
    total_errors  = 0

    # Try known directory-listing URLs (no browser needed)
    for fta_name, dir_url in MITI_PDF_DIRS.items():
        pdf_links = await _get_pdf_links_from_directory(dir_url)
        for pdf_url in pdf_links:
            origin = _infer_origin_country(pdf_url, fta_name)
            ok, n  = await _process_pdf(pdf_url, fta_name, origin, supabase)
            if ok:
                total_updated += n
            elif n == -1:
                total_skipped += 1
            else:
                total_errors += 1

    # Fallback: use Playwright (in thread) for pages not in directory list
    scraped_ftas = set(MITI_PDF_DIRS.keys())
    remaining    = {k: v for k, v in FTA_PAGES.items() if k not in scraped_ftas}

    if remaining:
        loop    = asyncio.get_event_loop()
        pdf_map = await loop.run_in_executor(
            None, _get_remaining_pdf_links_sync, remaining
        )
        for fta_name, pdf_links in pdf_map.items():
            for pdf_url in pdf_links:
                origin = _infer_origin_country(pdf_url, fta_name)
                ok, n  = await _process_pdf(pdf_url, fta_name, origin, supabase)
                if ok:
                    total_updated += n
                elif n == -1:
                    total_skipped += 1
                else:
                    total_errors += 1

    print(
        f"[fta_pdfs] Done — {total_updated} rates upserted, "
        f"{total_skipped} PDFs skipped, {total_errors} errors"
    )
    return {
        "pdfs_rates_upserted": total_updated,
        "pdfs_skipped":        total_skipped,
        "pdfs_errors":         total_errors,
    }


async def _get_pdf_links_from_directory(dir_url: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=20, verify=False) as client:
            resp = await client.get(dir_url)
            if resp.status_code != 200:
                return []
            from bs4 import BeautifulSoup
            soup  = BeautifulSoup(resp.text, "html.parser")
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.lower().endswith(".pdf"):
                    full = href if href.startswith("http") else dir_url.rstrip("/") + "/" + href.lstrip("/")
                    links.append(full)
            return links
    except Exception as e:
        print(f"[fta_pdfs] Directory listing failed {dir_url}: {e}")
        return []


async def _process_pdf(
    pdf_url: str, fta_name: str, origin: str, supabase
) -> tuple[bool, int]:
    try:
        changed, new_hash = await has_source_changed(pdf_url, supabase)
        if not changed:
            return False, -1

        async with httpx.AsyncClient(timeout=60, verify=False) as client:
            resp = await client.get(pdf_url)
            if resp.status_code != 200:
                return False, 0

        records = extract_fta_rates_from_pdf(resp.content, fta_name, origin, pdf_url)
        if not records:
            store_source_hash(pdf_url, new_hash, supabase)
            return True, 0

        count = 0
        for i in range(0, len(records), 100):
            supabase.table("fta_rates").upsert(
                records[i:i + 100], on_conflict="fta_name,hs_code,origin_country"
            ).execute()
            count += len(records[i:i + 100])

        store_source_hash(pdf_url, new_hash, supabase)
        print(f"[fta_pdfs] {fta_name}/{origin}: {count} rates upserted")
        return True, count

    except Exception as e:
        print(f"[fta_pdfs] Error processing {pdf_url}: {e}")
        return False, 0


_COUNTRY_NAME_MAP = {
    # ISO-3 codes (already handled by COUNTRY_CODE_MAP, included here for completeness)
    "CHN": "China",         "JPN": "Japan",          "KOR": "South Korea",
    "AUS": "Australia",     "NZL": "New Zealand",     "IND": "India",
    "CHL": "Chile",         "PAK": "Pakistan",         "TUR": "Turkey",
    "IDN": "Indonesia",     "THA": "Thailand",         "SGP": "Singapore",
    "PHL": "Philippines",   "VNM": "Vietnam",          "BRN": "Brunei",
    "KHM": "Cambodia",      "LAO": "Laos",             "MMR": "Myanmar",
    "HKG": "Hong Kong",     "CAN": "Canada",           "MEX": "Mexico",
    "GBR": "United Kingdom","PER": "Peru",             "BGD": "Bangladesh",
    # Full / variant names found in MITI PDF filenames (uppercase-matched)
    "CHINA":         "China",
    "JAPAN":         "Japan",
    "KOREA":         "South Korea",     "SOUTH-KOREA":  "South Korea",
    "SOUTHKOREA":    "South Korea",     "REPUBLIC-OF-KOREA": "South Korea",
    "AUSTRALIA":     "Australia",
    "NEW-ZEALAND":   "New Zealand",     "NEWZEALAND":   "New Zealand",
    "INDIA":         "India",
    "CHILE":         "Chile",
    "PAKISTAN":      "Pakistan",
    "TURKEY":        "Turkey",
    "INDONESIA":     "Indonesia",
    "THAILAND":      "Thailand",
    "SINGAPORE":     "Singapore",
    "PHILIPPINES":   "Philippines",
    "VIETNAM":       "Vietnam",         "VIET-NAM":     "Vietnam",
    "VIET_NAM":      "Vietnam",
    "BRUNEI":        "Brunei",          "BRUNEI-DARUSSALAM": "Brunei",
    "CAMBODIA":      "Cambodia",
    "LAOS":          "Laos",            "LAO":          "Laos",
    "LAO-PDR":       "Laos",            "LAO_PDR":      "Laos",
    "MYANMAR":       "Myanmar",         "BURMA":        "Myanmar",
    "HONG-KONG":     "Hong Kong",       "HONGKONG":     "Hong Kong",
    "CANADA":        "Canada",
    "MEXICO":        "Mexico",
    "UNITED-KINGDOM":"United Kingdom",  "UK":           "United Kingdom",
    "PERU":          "Peru",
    "BANGLADESH":    "Bangladesh",
    "SAUDI-ARABIA":  "Saudi Arabia",    "SAUDIARABIA":  "Saudi Arabia",
    "IRAN":          "Iran",
    "EGYPT":         "Egypt",
    "MOROCCO":       "Morocco",
    "NIGERIA":       "Nigeria",
    "JORDAN":        "Jordan",
    "TUNISIA":       "Tunisia",
    "SENEGAL":       "Senegal",
}


def _infer_origin_country(url: str, fta_name: str) -> str:
    """
    Infer origin country from PDF filename.
    Tries ISO-3 codes and full/variant country names (case-insensitive).
    Falls back to bilateral default for bilateral FTAs, else 'Unknown'.
    """
    filename = url.split("/")[-1].upper().replace(".PDF", "").replace("_", "-")

    # Try longest match first to avoid "KOR" matching before "SOUTH-KOREA"
    for token in sorted(_COUNTRY_NAME_MAP.keys(), key=len, reverse=True):
        if token in filename:
            return _COUNTRY_NAME_MAP[token]

    bilateral_defaults = {
        "MAFTA": "Australia", "MCFTA": "Chile",       "MICECA": "India",
        "MJEPA": "Japan",     "MNZFTA": "New Zealand", "MPCEPA": "Pakistan",
        "MTFTA": "Turkey",
    }
    country = bilateral_defaults.get(fta_name)
    if country:
        return country

    print(f"[fta_scraper] Could not infer origin country from: {url} (fta={fta_name})")
    return "Unknown"


# ════════════════════════════════════════════════════════════════
# Seed (offline fallback + one-time metadata fix)
# ════════════════════════════════════════════════════════════════

async def seed_fta_data() -> None:
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

        for fta_name, members in FTA_MEMBERS.items():
            meta = FTA_COVERAGE_META.get(fta_name, {})
            supabase.table("fta_coverage").upsert(
                {
                    "fta_name":         fta_name,
                    "member_countries": members,
                    "source_url":       meta.get("source_url"),
                    "effective_date":   meta.get("effective_date"),
                    "in_force_date":    meta.get("in_force_date"),
                    "description":      meta.get("description"),
                    "roo_summary":      meta.get("roo_summary"),
                },
                on_conflict="fta_name"
            ).execute()

        fta_rates = [
            {
                "fta_name": "RCEP", "hs_code": "8534.00", "origin_country": "China",
                "preferential_rate_pct": 0.0, "effective_date": "2022-01-01",
                "rate_staging": {"2022": 0.0}, "final_rate": 0.0, "final_year": 2022,
                "staging_category": "EIF",
            },
            {
                "fta_name": "RCEP", "hs_code": "8542.31", "origin_country": "China",
                "preferential_rate_pct": 0.0, "effective_date": "2022-01-01",
                "rate_staging": {"2022": 0.0}, "final_rate": 0.0, "final_year": 2022,
                "staging_category": "EIF",
            },
            {
                "fta_name": "RCEP", "hs_code": "8501.52", "origin_country": "Japan",
                "preferential_rate_pct": 0.0, "effective_date": "2022-01-01",
                "rate_staging": {"2022": 0.0}, "final_rate": 0.0, "final_year": 2022,
                "staging_category": "EIF",
            },
            {
                "fta_name": "RCEP", "hs_code": "7408.11", "origin_country": "China",
                "preferential_rate_pct": 1.0, "effective_date": "2022-01-01",
                "rate_staging": {
                    "2022": 5.0, "2023": 4.0, "2024": 3.0,
                    "2025": 2.0, "2026": 1.0, "2027": 0.0,
                },
                "final_rate": 0.0, "final_year": 2027, "staging_category": "SL-5",
            },
            {
                "fta_name": "CPTPP", "hs_code": "8534.00", "origin_country": "Japan",
                "preferential_rate_pct": 0.0, "effective_date": "2022-11-29",
                "rate_staging": {"2022": 0.0}, "final_rate": 0.0, "final_year": 2022,
                "staging_category": "EIF",
            },
            {
                "fta_name": "CPTPP", "hs_code": "7604.29", "origin_country": "Australia",
                "preferential_rate_pct": 1.0, "effective_date": "2022-11-29",
                "rate_staging": {
                    "2023": 4.0, "2024": 3.0, "2025": 2.0,
                    "2026": 1.0, "2027": 0.0,
                },
                "final_rate": 0.0, "final_year": 2027, "staging_category": "B5",
            },
            {
                "fta_name": "ACFTA",  "hs_code": "8534.00", "origin_country": "China",
                "preferential_rate_pct": 0.0, "effective_date": "2005-07-20",
                "rate_staging": None, "final_rate": 0.0,
            },
            {
                "fta_name": "AKFTA",  "hs_code": "8501.52", "origin_country": "South Korea",
                "preferential_rate_pct": 0.0, "effective_date": "2007-06-01",
                "rate_staging": None, "final_rate": 0.0,
            },
            {
                "fta_name": "ATIGA",  "hs_code": "7408.11", "origin_country": "Vietnam",
                "preferential_rate_pct": 0.0, "effective_date": "2010-01-01",
                "rate_staging": None, "final_rate": 0.0,
            },
            {
                "fta_name": "AKFTA",  "hs_code": "9001.90", "origin_country": "South Korea",
                "preferential_rate_pct": 0.0, "effective_date": "2007-06-01",
                "rate_staging": None, "final_rate": 0.0,
            },
            {
                "fta_name": "AJCEP",  "hs_code": "8525.80", "origin_country": "Japan",
                "preferential_rate_pct": 0.0, "effective_date": "2008-12-01",
                "rate_staging": None, "final_rate": 0.0,
            },
            {
                "fta_name": "PDK", "hs_code": "8534.00", "origin_country": "MFN",
                "preferential_rate_pct": 5.0, "effective_date": "2025-01-01",
                "rate_staging": None, "final_rate": 5.0,
            },
            {
                "fta_name": "PDK", "hs_code": "8501.52", "origin_country": "MFN",
                "preferential_rate_pct": 5.0, "effective_date": "2025-01-01",
                "rate_staging": None, "final_rate": 5.0,
            },
            {
                "fta_name": "PDK", "hs_code": "7408.11", "origin_country": "MFN",
                "preferential_rate_pct": 5.0, "effective_date": "2025-01-01",
                "rate_staging": None, "final_rate": 5.0,
            },
            {
                "fta_name": "PDK", "hs_code": "7604.29", "origin_country": "MFN",
                "preferential_rate_pct": 5.0, "effective_date": "2025-01-01",
                "rate_staging": None, "final_rate": 5.0,
            },
            {
                "fta_name": "PDK", "hs_code": "9001.90", "origin_country": "MFN",
                "preferential_rate_pct": 0.0, "effective_date": "2025-01-01",
                "rate_staging": None, "final_rate": 0.0,
            },
        ]

        for rate in fta_rates:
            supabase.table("fta_rates").upsert(
                rate, on_conflict="fta_name,hs_code,origin_country"
            ).execute()

        roo_rules = [
            {"fta_name": "ACFTA",  "hs_code": "8534.00", "roo_type": "RVC", "rvc_threshold_pct": 40.0},
            {"fta_name": "AKFTA",  "hs_code": "8501.52", "roo_type": "RVC", "rvc_threshold_pct": 40.0},
            {"fta_name": "ATIGA",  "hs_code": "7408.11", "roo_type": "RVC", "rvc_threshold_pct": 40.0},
            {"fta_name": "RCEP",   "hs_code": "7604.29", "roo_type": "tariff_shift",
             "tariff_shift_description": "CTSH - Change in Tariff Sub-Heading"},
            {"fta_name": "AKFTA",  "hs_code": "9001.90", "roo_type": "RVC", "rvc_threshold_pct": 40.0},
            {"fta_name": "RCEP",   "hs_code": "8534.00", "roo_type": "RVC", "rvc_threshold_pct": 40.0},
            {"fta_name": "CPTPP",  "hs_code": "8534.00", "roo_type": "RVC", "rvc_threshold_pct": 40.0},
        ]

        for rule in roo_rules:
            supabase.table("roo_rules").upsert(
                rule, on_conflict="fta_name,hs_code"
            ).execute()

        print("[fta_scraper] seed_fta_data completed — all 17 FTAs with metadata")

    except Exception as e:
        print(f"[fta_scraper] seed_fta_data failed: {e}")
