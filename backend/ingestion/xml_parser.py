import re
import xml.etree.ElementTree as ET


def parse_tariff_xml(xml_content: bytes | str) -> list[dict]:
    """
    Parse WCO/ASEAN tariff schedule XML into a list of rate records.

    Handles two common structures:

    1. Structured WCO/ASEAN format:
       <TariffSchedule>
         <Chapter>
           <Heading code="8534">
             <Rate fta="ATIGA" origin="MY" effectiveDate="2024-01-01">0</Rate>
             <Rate fta="MFN">5</Rate>
           </Heading>
         </Chapter>
       </TariffSchedule>

    2. Generic key-value XML (HS code and rate in sibling/adjacent elements).

    Returns list of dicts with keys:
      hs_code, duty_rate (float), fta_name, origin_country, effective_date
    """
    if isinstance(xml_content, bytes):
        xml_content = xml_content.decode("utf-8", errors="replace")

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"[xml_parser] XML parse error: {e}")
        return []

    results = _parse_wco_format(root)
    if results:
        print(f"[xml_parser] WCO format: extracted {len(results)} rate records")
        return results

    results = _parse_generic_format(root)
    print(f"[xml_parser] Generic format: extracted {len(results)} rate records")
    return results


# ── WCO / ASEAN structured format ────────────────────────────────────────────

def _parse_wco_format(root: ET.Element) -> list[dict]:
    ns = _detect_namespace(root)
    headings = root.findall(f".//{ns}Heading") or root.findall(".//Heading")
    if not headings:
        return []

    results = []
    for heading in headings:
        hs_code = heading.get("code", "").strip()
        if not hs_code:
            continue

        rate_els = heading.findall(f"{ns}Rate") or heading.findall("Rate")

        if not rate_els:
            pct = _parse_rate(heading.text or "")
            if pct is not None:
                results.append(_make_record(hs_code, pct, "MFN", None, None))
        else:
            for rate_el in rate_els:
                pct = _parse_rate(rate_el.text or "")
                if pct is None:
                    continue
                results.append(_make_record(
                    hs_code,
                    pct,
                    rate_el.get("fta", "MFN"),
                    rate_el.get("origin", None),
                    rate_el.get("effectiveDate", None),
                ))

    return results


# ── Generic key-value XML ─────────────────────────────────────────────────────

def _parse_generic_format(root: ET.Element) -> list[dict]:
    """
    Walk all elements; when an element's text looks like an HS code,
    search the next few siblings for a numeric rate value.
    """
    hs_re   = re.compile(r"^\d{4}\.?\d{0,2}\.?\d{0,4}$")
    rate_re = re.compile(r"^(\d+\.?\d*)\s*%?$")

    all_els = list(root.iter())
    results = []

    for i, el in enumerate(all_els):
        text = (el.text or "").strip().replace(" ", "")
        if not hs_re.match(text):
            continue

        hs_code = text
        for j in range(i + 1, min(i + 6, len(all_els))):
            neighbor = (all_els[j].text or "").strip()
            m = rate_re.match(neighbor)
            if m:
                results.append(_make_record(
                    hs_code,
                    float(m.group(1)),
                    all_els[j].get("fta", "MFN"),
                    all_els[j].get("origin", None),
                    all_els[j].get("effectiveDate", None),
                ))
                break

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_record(
    hs_code: str,
    duty_rate: float,
    fta_name: str,
    origin_country,
    effective_date,
) -> dict:
    return {
        "hs_code":        hs_code,
        "duty_rate":      duty_rate,
        "fta_name":       fta_name,
        "origin_country": origin_country,
        "effective_date": effective_date,
    }


def _detect_namespace(root: ET.Element) -> str:
    tag = root.tag
    if tag.startswith("{"):
        return tag[: tag.index("}") + 1]
    return ""


def _parse_rate(text: str):
    cleaned = text.strip().rstrip("%").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None
