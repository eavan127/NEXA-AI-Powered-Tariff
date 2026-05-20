import re
import httpx
import feedparser
import pdfplumber
import asyncio
from io import BytesIO
from supabase import create_client

from config import settings

# ── Main monitor function ─────────────────────────────────────────
async def monitor_gazette_rss() -> dict:
    new_entries    = 0
    tariff_related = 0

    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

        # Step 1 — Parse Really Simple Syndication (RSS) feed
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

                # Step 3 — Download PDF
                pdf_text = await _download_and_extract(gazette_url)

                # Step 4 — Classify with Ollama
                classification = await _classify_with_ollama(
                    gazette_title, pdf_text
                )

                is_tariff_related = classification.get("is_tariff_related", False)
                reason            = classification.get("reason", "")

                # Step 5 — Extract rates if tariff related
                extracted_rates = {}
                if is_tariff_related:
                    tariff_related += 1
                    extracted_rates = _extract_rates_from_text(pdf_text)
                    print(f"[gazette] Tariff related: {gazette_title}")
                    print(f"[gazette] Extracted rates: {extracted_rates}")

                # Step 6 — Save to Supabase
                supabase.table("gazette_alerts").upsert(
                    {
                        "gazette_title":    gazette_title,
                        "gazette_url":      gazette_url,
                        "published_date":   published[:10] if published else None,
                        "is_tariff_related": is_tariff_related,
                        "extracted_rates":  extracted_rates,
                        "processed_at":     "now()",
                    },
                    on_conflict="gazette_url"
                ).execute()

            except Exception as e:
                print(f"[gazette] Error processing entry: {e}")
                continue

    except Exception as e:
        print(f"[gazette] monitor_gazette_rss failed: {e}")

    return {
        "new_entries":    new_entries,
        "tariff_related": tariff_related
    }

# ── Download PDF and extract text ────────────────────────────────
async def _download_and_extract(url: str) -> str:
    try:
        async with httpx.AsyncClient(
            timeout=30,
            verify=False
        ) as client:
            response = await client.get(url)

            if response.status_code != 200:
                return ""

            # Try pdfplumber on downloaded content
            pdf_bytes = BytesIO(response.content)
            text = ""

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""

            return text

    except Exception as e:
        print(f"[gazette] PDF download/extract failed: {e}")
        return ""

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
                    "model":  "llama3",
                    "prompt": prompt,
                    "stream": False
                }
            )

            if response.status_code != 200:
                return {"is_tariff_related": False, "reason": "Ollama unavailable"}

            result      = response.json()
            raw_text    = result.get("response", "")

            # Parse JSON from Ollama response
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

    # Find HS codes pattern (e.g. 8534.00 or 8534.00.0000)
    hs_pattern    = r"\b(\d{4}\.\d{2}(?:\.\d{2,4})?)\b"
    hs_codes      = re.findall(hs_pattern, text)

    # Find percentage values near HS codes
    rate_pattern  = r"(\d+\.?\d*)\s*(?:per\s*cent|%)"
    rates         = re.findall(rate_pattern, text, re.IGNORECASE)

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
                    "hub.mode":     "subscribe",
                    "hub.topic":    settings.GAZETTE_RSS_URL,
                    "hub.callback": webhook_url,
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

