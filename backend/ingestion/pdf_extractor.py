import re
import pdfplumber
from datetime import datetime
from io import BytesIO

FTA_EIF_YEAR = {
    "RCEP": 2022, "CPTPP": 2022, "AKFTA": 2007, "ATIGA": 2010,
    "AHKFTA": 2019, "ACFTA": 2005, "MICECA": 2012, "AIFTA": 2010,
    "MPCEPA": 2008, "MCFTA": 2012, "AJCEP": 2008, "MNZFTA": 2010,
    "TPS-OIC": 1991, "MTFTA": 2015, "MJEPA": 2008, "AANZFTA": 2012, "MAFTA": 2013,
}

# Strict rate regex: 0–100, up to 4 decimal places
_RATE_RE = re.compile(r"^(100(\.0{1,4})?|[0-9]{1,2}(\.[0-9]{1,4})?)$")

# Valid HS code: 4–10 digits (chapters 01–97), dots allowed
_HS_RE = re.compile(r"^\d{4,10}$")


# ── Public entry point ────────────────────────────────────────────

def extract_fta_rates_from_pdf(
    content: bytes,
    fta_name: str,
    origin_country: str,
    pdf_source_url: str = "",
    dry_run: bool = False,
) -> list[dict]:
    """
    Parse a MITI FTA tariff schedule PDF.

    dry_run=True → prints first 10 rows of each table, returns [] without upserting.
    Returns list of dicts ready for upsert to fta_rates.
    """
    eif_year = FTA_EIF_YEAR.get(fta_name, 2022)
    records  = []

    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            pages_to_scan = pdf.pages[:3] if dry_run else pdf.pages

            for page_num, page in enumerate(pages_to_scan, start=1):
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header = [str(c or "").strip() for c in table[0]]
                    print(f"[pdf_extractor] Page {page_num} columns: {header}")

                    col_map = _parse_header(header, eif_year)
                    print(
                        f"[pdf_extractor] Mapped → "
                        f"hs={col_map['hs_col']} "
                        f"pref={col_map['pref_col']} "
                        f"base={col_map['base_col']} "
                        f"stages={list(col_map['stage_cols'].keys())}"
                    )

                    if col_map["hs_col"] is None:
                        print(f"[pdf_extractor] No HS column detected — skipping table")
                        continue

                    if dry_run:
                        print(f"[pdf_extractor] DRY RUN — first 10 rows:")
                        for i, row in enumerate(table[1:11]):
                            print(f"  row {i+1}: {row}")
                        continue

                    for row in table[1:]:
                        rec = _parse_row(
                            row, col_map, fta_name, origin_country,
                            pdf_source_url, page_num,
                        )
                        if rec:
                            records.append(rec)

    except Exception as e:
        print(f"[pdf_extractor] Failed to parse {pdf_source_url}: {e}")
        return []

    if dry_run:
        return []

    # Deduplicate
    seen = {}
    for r in records:
        key = (r["hs_code"], r["fta_name"], r["origin_country"])
        seen[key] = r

    result = list(seen.values())

    # Sanity check: warn if every rate is 0.0
    if result:
        non_zero = sum(1 for r in result if (r["preferential_rate_pct"] or 0) > 0)
        if non_zero == 0:
            print(
                f"[pdf_extractor] WARNING: 100% of {len(result)} extracted rates "
                f"are 0.0 — column detection may be wrong for {pdf_source_url}"
            )

    print(
        f"[pdf_extractor] {fta_name}/{origin_country}: "
        f"{len(result)} valid rate records extracted"
    )
    return result


# ── Header parsing ────────────────────────────────────────────────

# Keywords that identify each column type (checked in header cells, case-insensitive)
_HS_KW    = ("hs code", "hs no", "hs ", "tariff code", "kod hs", "item no",
              "heading", "subheading", "hs/ts")
_PREF_KW  = ("atiga", "preferential", "fta rate", "cept rate", "applicable rate",
              "kadar atiga", "kadar pilihan", "rcep rate", "cptpp rate",
              "akfta rate", "acfta rate", "ajcep rate", "aanzfta rate",
              "aifta rate", "mjepa rate", "mafta rate", "fta duty",
              "reduced rate", "agreed rate", "negotiated")
_BASE_KW  = ("base rate", "mfn rate", "pdk rate", "normal rate", "general rate",
             "kadar am", "kadar pdk", "most favoured nation", "mfn duty")
_FINAL_KW = ("final rate", "end rate", "ultimate rate", "fully liberalised")
_RATE_KW  = ("rate", "duty", "duti", "kadar", "tariff rate")  # generic fallback
_STAGE_RE = re.compile(
    r"(?:y|year|stage|yr)\s*(\d+)" r"|(\d{4})", re.IGNORECASE
)


def _parse_header(header: list[str], eif_year: int) -> dict:
    hs_col     = None
    pref_col   = None   # preferential / FTA rate column  ← THE important one
    base_col   = None
    final_col  = None
    stage_cols = {}

    header_lower = [h.lower() for h in header]

    for i, h in enumerate(header_lower):
        if hs_col is None and any(k in h for k in _HS_KW):
            hs_col = i
        elif pref_col is None and any(k in h for k in _PREF_KW):
            pref_col = i
        elif base_col is None and any(k in h for k in _BASE_KW):
            base_col = i
        elif final_col is None and any(k in h for k in _FINAL_KW):
            final_col = i
        else:
            m = _STAGE_RE.search(h)
            if m:
                if m.group(1):
                    stage_cols[eif_year + int(m.group(1)) - 1] = i
                elif m.group(2):
                    stage_cols[int(m.group(2))] = i

    # Generic fallback: any column with "rate/duty/kadar" that isn't already assigned
    if pref_col is None and base_col is None and not stage_cols and final_col is None:
        assigned = {hs_col}
        for i, h in enumerate(header_lower):
            if i not in assigned and any(k in h for k in _RATE_KW):
                pref_col = i
                break

    # hs_col fallback: look for a column whose header has "hs" or "code" alone
    if hs_col is None:
        for i, h in enumerate(header_lower):
            if h.strip() in ("hs", "code", "hs code", "tariff", "item"):
                hs_col = i
                break

    # Do NOT fall back to column 0 blindly — return None to skip unparseable tables
    return {
        "hs_col":    hs_col,
        "pref_col":  pref_col,
        "base_col":  base_col,
        "final_col": final_col,
        "stage_cols": stage_cols,
    }


# ── Row parsing ───────────────────────────────────────────────────

def _parse_row(
    row: list,
    col_map: dict,
    fta_name: str,
    origin_country: str,
    pdf_source_url: str,
    page_num: int,
) -> dict | None:
    hs_col     = col_map["hs_col"]
    pref_col   = col_map["pref_col"]
    base_col   = col_map["base_col"]
    final_col  = col_map["final_col"]
    stage_cols = col_map["stage_cols"]

    if hs_col is None or len(row) <= hs_col:
        return None

    # ── HS code validation ────────────────────────────────────────
    hs_raw = str(row[hs_col] or "").strip().replace(" ", "").replace("\n", "").replace(".", "")
    if not _HS_RE.match(hs_raw):
        return None
    chapter = int(hs_raw[:2])
    if chapter < 1 or chapter > 97:
        return None
    # Re-add dot notation for 6+ digit codes (e.g. 853400 → 8534.00)
    hs_code = _normalise_hs(hs_raw)

    # ── Rate extraction ───────────────────────────────────────────
    # Priority: preferential column > stage columns > final col > base col
    current_rate = None
    if pref_col is not None and pref_col < len(row):
        current_rate = _parse_rate_cell(row[pref_col])

    staging: dict[str, float] = {}
    for year, col_idx in stage_cols.items():
        if col_idx < len(row):
            r = _parse_rate_cell(row[col_idx])
            if r is not None:
                staging[str(year)] = r

    if current_rate is None and staging:
        current_rate = _current_applicable_rate(staging)

    if current_rate is None and final_col is not None and final_col < len(row):
        current_rate = _parse_rate_cell(row[final_col])

    if current_rate is None and base_col is not None and base_col < len(row):
        current_rate = _parse_rate_cell(row[base_col])

    if current_rate is None:
        return None

    # ── Rate sanity check ─────────────────────────────────────────
    if current_rate > 100:
        print(
            f"[pdf_extractor] SKIP corrupt rate {current_rate}% "
            f"for HS {hs_code} page {page_num}"
        )
        return None

    final_year = None
    if staging:
        min_r = min(staging.values())
        for y in sorted(staging.keys(), key=int):
            if staging[y] == min_r:
                final_year = int(y)
                break

    # earliest staging year, or FTA's known EIF year, or None
    eif_yr = min((int(y) for y in staging), default=None) if staging else None
    if eif_yr is None:
        eif_yr = FTA_EIF_YEAR.get(fta_name)

    return {
        "fta_name":              fta_name,
        "hs_code":               hs_code,
        "preferential_rate_pct": current_rate,
        "origin_country":        origin_country,
        "effective_date":        f"{eif_yr}-01-01" if eif_yr else None,
        "rate_staging":          staging or None,
        "final_rate":            _parse_rate_cell(row[final_col]) if final_col and final_col < len(row) else None,
        "final_year":            final_year,
        "pdf_source_url":        pdf_source_url,
        "pdf_page_number":       page_num,
        "last_verified_at":      datetime.utcnow().isoformat(),
    }


# ── Helpers ───────────────────────────────────────────────────────

def _normalise_hs(digits: str) -> str:
    """853400 → 8534.00,  85340010 → 8534.00.10"""
    if len(digits) >= 6:
        return digits[:4] + "." + digits[4:6] + ("." + digits[6:] if len(digits) > 6 else "")
    return digits


def _parse_rate_cell(cell) -> float | None:
    text = str(cell or "").strip().replace("%", "").replace("\n", "").replace(",", ".").strip()
    if text.lower() in ("free", "ex", "exempt", "nil", "-", "", "0%"):
        return 0.0
    if text.upper() in ("X", "N/A", "NA", "EXCLUDED"):
        return None  # excluded — don't store
    # Must match strict 0-100 pattern
    if not _RATE_RE.match(text):
        return None
    try:
        val = float(text)
        return val if 0.0 <= val <= 100.0 else None
    except ValueError:
        return None


def _current_applicable_rate(staging: dict) -> float | None:
    current_year = datetime.now().year
    for year in sorted(staging.keys(), key=int, reverse=True):
        if int(year) <= current_year:
            return staging[year]
    return staging[min(staging.keys(), key=int)]
