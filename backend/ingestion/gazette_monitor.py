import re
import httpx
import feedparser
import pdfplumber
import asyncio
from io import BytesIO
from supabase import create_client

from config import settings
from ingestion.change_detector import has_source_changed, store_source_hash
from ingestion.xml_parser import parse_tariff_xml

# ── Main monitor function ─────────────────────────────────────────
async def monitor_gazette_rss() -> dict:
    new_entries    = 0
    tariff_related = 0

    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

        # Step 0 — Hash check: only parse if RSS feed actually changed
        changed, new_hash = await has_source_changed(settings.GAZETTE_RSS_URL, supabase)
        if not changed:
            print("[gazette] RSS feed unchanged — skipping")
            return {"new_entries": 0, "tariff_related": 0, "skipped": "no_change"}

        # Step 1 — Parse RSS feed
        feed = feedparser.parse(settings.GAZETTE_RSS_URL)

        if not feed.entries:
            print("[gazette] No entries found in RSS feed")
            return {"new_entries": 0, "tariff_related": 0}

        for entry in feed.entries:
            try:
                gazette_url   = entry.get("link", "")
                gazette_title = entry.get("title", "")
                published     = entry.get("published", "")

                # Step 2 — Skip if already in database
                existing = supabase.table("gazette_alerts") \
                    .select("id") \
                    .eq("gazette_url", gazette_url) \
                    .execute()

                if existing.data:
                    continue

                new_entries += 1
                print(f"[gazette] New entry: {gazette_title}")

                # Step 3 — Download and parse (XML / PDF / HTML)
                parsed = await _download_and_parse(gazette_url)
                parse_method   = parsed["parse_method"]
                extracted_rates = parsed["rates"]

                # Step 4 — Classify and rate-extract based on parse method
                is_tariff_related = False
                reason = ""

                if parse_method == "xml":
                    # XML structure already contains rate data — no Ollama needed
                    is_tariff_related = bool(extracted_rates)
                    reason = "Extracted directly from XML tariff schedule"
                    if is_tariff_related:
                        tariff_related += 1
                        print(f"[gazette] XML tariff data found: {gazette_title}")
                else:
                    # PDF or HTML — classify with Ollama then extract via regex
                    classification = await _classify_with_ollama(
                        gazette_title, parsed["text"]
                    )
                    is_tariff_related = classification.get("is_tariff_related", False)
                    reason            = classification.get("reason", "")

                    if is_tariff_related:
                        tariff_related += 1
                        extracted_rates = _extract_rates_from_text(parsed["text"])
                        print(f"[gazette] Tariff related ({parse_method}): {gazette_title}")
                        print(f"[gazette] Extracted rates: {extracted_rates}")

                # Step 5 — Save to Supabase
                supabase.table("gazette_alerts").upsert(
                    {
                        "gazette_title":     gazette_title,
                        "gazette_url":       gazette_url,
                        "published_date":    published[:10] if published else None,
                        "is_tariff_related": is_tariff_related,
                        "extracted_rates":   extracted_rates,
                        "processed_at":      "now()",
                    },
                    on_conflict="gazette_url"
                ).execute()

            except Exception as e:
                print(f"[gazette] Error processing entry: {e}")
                continue

        # Step 6 — Persist the RSS feed hash so next run skips if unchanged
        store_source_hash(settings.GAZETTE_RSS_URL, new_hash, supabase)

    except Exception as e:
        print(f"[gazette] monitor_gazette_rss failed: {e}")

    return {
        "new_entries":    new_entries,
        "tariff_related": tariff_related
    }


# ── Download and route to correct parser ─────────────────────────
async def _download_and_parse(url: str) -> dict:
    """
    Fetch URL, detect Content-Type, route to XML / PDF / HTML parser.
    Returns: {"text": str, "rates": dict, "parse_method": str}
    """
    try:
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            response = await client.get(url)

            if response.status_code != 200:
                return {"text": "", "rates": {}, "parse_method": "failed"}

            content_type = response.headers.get("content-type", "").lower()

            # ── XML ──────────────────────────────────────────────
            if "xml" in content_type:
                print(f"[gazette] Parsed as XML: {url}")
                rate_records = parse_tariff_xml(response.content)
                rates = {}
                if rate_records:
                    rates["hs_codes"]    = list({r["hs_code"] for r in rate_records})
                    rates["rates_found"] = [r["duty_rate"] for r in rate_records]
                    rates["raw"]         = rate_records
                return {"text": "", "rates": rates, "parse_method": "xml"}

            # ── PDF (by Content-Type or magic bytes) ─────────────
            is_pdf = "pdf" in content_type or response.content[:4] == b"%PDF"
            if is_pdf:
                print(f"[gazette] Parsed as PDF (pdfplumber): {url}")
                text = ""
                with pdfplumber.open(BytesIO(response.content)) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                return {"text": text, "rates": {}, "parse_method": "pdf"}

            # ── HTML / plain text ─────────────────────────────────
            print(f"[gazette] Parsed as HTML/text: {url}")
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                text = soup.get_text(separator="\n")
            except ImportError:
                text = response.text
            return {"text": text, "rates": {}, "parse_method": "html"}

    except Exception as e:
        print(f"[gazette] Download/parse failed for {url}: {e}")
        return {"text": "", "rates": {}, "parse_method": "error"}


# ── Classify with Ollama ──────────────────────────────────────────
async def _classify_with_ollama(title: str, text: str) -> dict:
    try:
        prompt = f"""Is this Malaysian government gazette related to tariff rates,
customs duty, HS codes, or import/export taxes?
Answer with JSON only: {{"is_tariff_related": true/false, "reason": "one sentence"}}

Gazette title: {title}
Gazette text (first 2000 chars):
{text[:2000]}"""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model":  "qwen2.5:1.5b",
                    "prompt": prompt,
                    "stream": False
                }
            )

            if response.status_code != 200:
                return {"is_tariff_related": False, "reason": "Ollama unavailable"}

            result   = response.json()
            raw_text = result.get("response", "")

            json_match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
            if json_match:
                import json
                return json.loads(json_match.group())

            return {"is_tariff_related": False, "reason": "Could not parse response"}

    except Exception as e:
        print(f"[gazette] Ollama classification failed: {e}")
        return {"is_tariff_related": False, "reason": f"Error: {e}"}


# ── Extract HS codes and rates from text ─────────────────────────
def _extract_rates_from_text(text: str) -> dict:
    extracted = {}

    hs_pattern   = r"\b(\d{4}\.\d{2}(?:\.\d{2,4})?)\b"
    rate_pattern = r"(\d+\.?\d*)\s*(?:per\s*cent|%)"

    hs_codes = re.findall(hs_pattern, text)
    rates    = re.findall(rate_pattern, text, re.IGNORECASE)

    if hs_codes:
        extracted["hs_codes"] = list(set(hs_codes))
    if rates:
        extracted["rates_found"] = [float(r) for r in rates]

    return extracted


# ── Superfeedr webhook setup ──────────────────────────────────────
async def setup_superfeedr_webhook(webhook_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://push.superfeedr.com",
                data={
                    "hub.mode":      "subscribe",
                    "hub.topic":     settings.GAZETTE_RSS_URL,
                    "hub.callback":  webhook_url,
                    "authorization": settings.SUPERFEEDR_TOKEN
                }
            )

            if response.status_code in [200, 204]:
                print(f"[gazette] Superfeedr webhook registered: {webhook_url}")
                return True

            print(f"[gazette] Superfeedr registration failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[gazette] setup_superfeedr_webhook failed: {e}")
        return False
