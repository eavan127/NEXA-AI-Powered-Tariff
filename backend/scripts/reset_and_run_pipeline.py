"""
reset_and_run_pipeline.py
Wipe all module outputs, reset shipment statuses to pending,
then run A → B → C for every shipment and report results.
Run from the backend/ directory:
    python scripts/reset_and_run_pipeline.py
"""
import sys, json, asyncio
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")          # make backend packages importable

import httpx
from supabase import create_client
from config import settings

BASE_URL = "http://localhost:8000"
SHIPS    = ["SHIP001", "SHIP002", "SHIP003", "SHIP004", "SHIP005"]

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


# ── helpers ──────────────────────────────────────────────────────────
def sep(title=""):
    print("\n" + "─" * 60)
    if title:
        print(f"  {title}")
        print("─" * 60)

def ok(msg):  print(f"  ✓  {msg}")
def err(msg): print(f"  ✗  {msg}")
def info(msg):print(f"     {msg}")


# ── 1. RESET ──────────────────────────────────────────────────────────
def reset_db():
    sep("RESET — clearing module outputs")

    tables = ["audit_trail", "landed_costs", "fta_results", "hs_classifications"]
    for tbl in tables:
        try:
            # Delete all rows (Supabase requires a filter; neq id '' works as "all")
            supabase.table(tbl).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            ok(f"Cleared {tbl}")
        except Exception as e:
            err(f"Clear {tbl}: {e}")

    # Reset shipment statuses to pending
    try:
        supabase.table("shipments").update({"status": "pending"}).neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
        ok("All shipments → pending")
    except Exception as e:
        err(f"Reset statuses: {e}")


# ── 2. PIPELINE ───────────────────────────────────────────────────────
async def run_pipeline():
    sep("PIPELINE — A → B → C for each shipment")

    results = {}

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        for ship_id in SHIPS:
            print(f"\n  [{ship_id}]")
            row = {"A": None, "B": None, "C": None}

            for module, path in [
                ("A", f"/api/classify/{ship_id}"),
                ("B", f"/api/match-fta/{ship_id}"),
                ("C", f"/api/calculate-landed-cost/{ship_id}"),
            ]:
                try:
                    r = await client.post(path)
                    raw = r.text
                    try:
                        body = r.json()
                    except Exception:
                        row[module] = "exception"
                        err(f"Module {module} HTTP {r.status_code} — non-JSON response: {raw[:200]}")
                        continue

                    if r.status_code == 200 and "error" not in body:
                        row[module] = "ok"
                        if module == "A":
                            cls = body.get("classification") or body
                            info(f"Module A  HS={cls.get('final_hs_code','?')}  "
                                 f"conf={cls.get('confidence_score','?')}%  "
                                 f"status={cls.get('module_a_status','?')}")
                        elif module == "B":
                            d = body.get("data") or body
                            info(f"Module B  FTA={d.get('best_fta','?')}  "
                                 f"rate={d.get('fta_rate_pct','?')}%  "
                                 f"MFN={d.get('mfn_rate_pct','?')}%  "
                                 f"saving=USD {d.get('duty_saving_usd','?')}")
                        elif module == "C":
                            d = body.get("data") or body
                            info(f"Module C  total=USD {d.get('total_landed_usd','?')}  "
                                 f"LMW={d.get('is_lmw_facility','?')}  "
                                 f"FTA saving=USD {d.get('fta_saving_usd','?')}")
                    else:
                        row[module] = "error"
                        detail = body.get("error") or body.get("detail") or str(body)
                        err(f"Module {module} HTTP {r.status_code}: {detail}")
                except Exception as exc:
                    row[module] = "exception"
                    err(f"Module {module}: {exc}")

            results[ship_id] = row

    return results


# ── 3. SUMMARY ────────────────────────────────────────────────────────
def print_summary(results):
    sep("SUMMARY")
    header = f"  {'Shipment':<10}  {'A':^6}  {'B':^6}  {'C':^6}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    icons = {"ok": "✓", "error": "✗", "exception": "!", None: "—"}
    for ship_id, row in results.items():
        a = icons[row["A"]]
        b = icons[row["B"]]
        c = icons[row["C"]]
        print(f"  {ship_id:<10}  {a:^6}  {b:^6}  {c:^6}")
    print()


# ── main ──────────────────────────────────────────────────────────────
async def main():
    reset_db()
    results = await run_pipeline()
    print_summary(results)

if __name__ == "__main__":
    asyncio.run(main())
