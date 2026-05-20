import re # Regular Expression
import pdfplumber
from paddleocr import PaddleOCR

from config import settings

# ── PaddleOCR instance (initialized once, reused) ────────────────
_ocr = None

def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang='en')
    return _ocr


# ── Main function ─────────────────────────────────────────────────
async def extract_coo_data(pdf_path: str) -> dict:
    try:
        # Step 1: Try pdfplumber first
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

        extraction_method = "pdfplumber"

        # Step 2: Fallback to PaddleOCR if text too short
        if len(text) < 50:
            ocr = _get_ocr()
            text = ""
            result = ocr.ocr(pdf_path, cls=True)
            for page in result:
                for line in page:
                    text += line[1][0] + "\n"
            extraction_method = "paddleocr"

        # Extract fields using regex
        country_of_origin = _extract_country(text)
        rvc_percentage    = _extract_rvc(text)
        material          = _extract_material(text)

        return {
            "country_of_origin":    country_of_origin,
            "rvc_percentage":       rvc_percentage,
            "material_composition": material,
            "extraction_method":    extraction_method,
            "raw_text_length":      len(text)
        }

    except Exception as e:
        print(f"[ocr_processor] extract_coo_data failed: {e}")
        return {
            "country_of_origin":    None,
            "rvc_percentage":       None,
            "material_composition": None,
            "extraction_method":    "failed",
            "raw_text_length":      0
        }


# ── Mock function (works 100% offline) ───────────────────────────
async def extract_coo_data_mock(shipment_id: str) -> dict:
    mock_data = {
        "SHIP001": {
            "country_of_origin":    "China",
            "rvc_percentage":       45.2,
            "material_composition": "FR4 substrate, copper traces",
            "extraction_method":    "mock",
            "raw_text_length":      512
        },
        "SHIP002": {
            "country_of_origin":    "Japan",
            "rvc_percentage":       62.5,
            "material_composition": "Silicon steel laminations, copper windings",
            "extraction_method":    "mock",
            "raw_text_length":      480
        },
        "SHIP003": {
            "country_of_origin":    "Vietnam",
            "rvc_percentage":       38.0,
            "material_composition": "99.9% electrolytic copper",
            "extraction_method":    "mock",
            "raw_text_length":      390
        },
        "SHIP004": {
            "country_of_origin":    "Taiwan",
            "rvc_percentage":       55.0,
            "material_composition": "6063 aluminium alloy",
            "extraction_method":    "mock",
            "raw_text_length":      420
        },
        "SHIP005": {
            "country_of_origin":    "South Korea",
            "rvc_percentage":       71.3,
            "material_composition": "Borosilicate optical glass",
            "extraction_method":    "mock",
            "raw_text_length":      550
        },
    }

    return mock_data.get(shipment_id, mock_data["SHIP001"])


# ── Regex helpers ─────────────────────────────────────────────────
def _extract_country(text: str) -> str | None:
    patterns = [
        r"Country of Origin[:\s]+([A-Za-z\s]+)",
        r"Origin Country[:\s]+([A-Za-z\s]+)",
        r"Produced in[:\s]+([A-Za-z\s]+)",
        r"Manufactured in[:\s]+([A-Za-z\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_rvc(text: str) -> float | None:
    patterns = [
        r"RVC[:\s]+([\d.]+)\s*%?",
        r"Regional Value Content[:\s]+([\d.]+)\s*%?",
        r"Value Content[:\s]+([\d.]+)\s*%?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _extract_material(text: str) -> str | None:
    patterns = [
        r"Material[:\s]+(.+)",
        r"Composition[:\s]+(.+)",
        r"Made of[:\s]+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None