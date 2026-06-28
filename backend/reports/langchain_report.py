import logging
from langchain_ollama import OllamaLLM
try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

_PROMPT = PromptTemplate.from_template(
    "You are a Senior Trade Compliance Officer writing a formal shipment approval report "
    "for submission to regulatory authorities and internal audit. "
    "Write a professional executive summary in 3 to 4 paragraphs using formal business prose. "
    "Do not use bullet points, markdown, or headings. Write in plain continuous paragraphs only.\n\n"
    "SHIPMENT DATA:\n"
    "  Reference:          {shipment_id}\n"
    "  Product:            {product}\n"
    "  Trade Route:        {origin} to {destination}\n"
    "  CIF Value:          USD {cif_value}\n"
    "  HS Code (Final):    {hs_code}\n"
    "  AI Confidence:      {confidence}%\n"
    "  FTA Applied:        {fta_name} at {fta_rate}% preferential duty rate\n"
    "  MFN Rate:           {mfn_rate}%\n"
    "  Total Duty Saving:  USD {duty_saving}\n"
    "  Total Landed Cost:  USD {total_landed}\n"
    "  Approval Status:    APPROVED\n\n"
    "Write the executive summary now:"
)


def generate_narrative(shipment: dict, base_url: str = "http://localhost:11434",
                       model: str = "llama3.2") -> str:
    try:
        cls = _latest(shipment.get("hs_classifications"))
        fta = _latest(shipment.get("fta_results"))
        lc  = _latest(shipment.get("landed_costs"))
        cif = _cif(shipment)

        llm   = OllamaLLM(model=model, base_url=base_url, timeout=120)
        chain = _PROMPT | llm
        result = chain.invoke({
            "shipment_id": shipment.get("sap_shipment_id", "N/A"),
            "product":     shipment.get("product_description", "N/A"),
            "origin":      shipment.get("origin_country", "N/A"),
            "destination": shipment.get("destination_country", "N/A"),
            "cif_value":   f"{cif:,.2f}",
            "hs_code":     cls.get("final_hs_code", "N/A"),
            "confidence":  cls.get("confidence_score", 0),
            "fta_name":    fta.get("best_fta_name", "MFN"),
            "fta_rate":    fta.get("best_fta_rate_pct", 0),
            "mfn_rate":    fta.get("mfn_rate_pct", 0),
            "duty_saving": f"{fta.get('duty_saving_usd', 0) or 0:,.2f}",
            "total_landed": f"{lc.get('total_landed_cost_usd', 0) or 0:,.2f}",
        })
        text = str(result).strip()
        if len(text) > 80:
            return text
        raise ValueError("Response too short — falling back to template")
    except Exception as exc:
        logger.warning("LangChain narrative failed (%s); using template fallback.", exc)
        return _fallback(shipment)


# ── helpers ───────────────────────────────────────────────────────────────────

def _latest(lst: list | None) -> dict:
    if not lst:
        return {}
    return sorted(lst, key=lambda x: x.get("created_at", ""), reverse=True)[0]


def _cif(shipment: dict) -> float:
    return (
        (shipment.get("shipment_value_usd") or 0)
        + (shipment.get("freight_cost_usd") or 0)
        + (shipment.get("insurance_cost_usd") or 0)
    )


def _fallback(shipment: dict) -> str:
    cls = _latest(shipment.get("hs_classifications"))
    fta = _latest(shipment.get("fta_results"))
    lc  = _latest(shipment.get("landed_costs"))
    cif = _cif(shipment)

    sid      = shipment.get("sap_shipment_id", "N/A")
    prod     = shipment.get("product_description", "N/A")
    origin   = shipment.get("origin_country", "N/A")
    dest     = shipment.get("destination_country", "N/A")
    hs       = cls.get("final_hs_code", "N/A")
    conf     = cls.get("confidence_score", 0)
    fta_name = fta.get("best_fta_name", "MFN")
    fta_rate = fta.get("best_fta_rate_pct", 0)
    mfn_rate = fta.get("mfn_rate_pct", 0)
    saving   = fta.get("duty_saving_usd", 0) or 0
    total    = lc.get("total_landed_cost_usd", 0) or 0

    return (
        f"This report documents the formal approval of shipment reference {sid} pursuant to "
        f"the requirements of the Malaysian Customs Act 1967 and applicable Free Trade Agreement "
        f"obligations. The consignment pertains to {prod}, transported on the trade corridor from "
        f"{origin} to {dest}, with a declared Cost, Insurance and Freight (CIF) valuation of "
        f"USD {cif:,.2f}.\n\n"
        f"Following automated classification conducted by the NEXA AI Tariff Intelligence System, "
        f"the product has been assigned Harmonised System (HS) Code {hs}, with an AI confidence "
        f"score of {conf}%. This classification was subject to mandatory human review and was "
        f"confirmed by the authorised Trade Compliance Analyst in accordance with the World Customs "
        f"Organisation (WCO) Harmonised System nomenclature and applicable Malaysian customs "
        f"classification guidelines.\n\n"
        f"The Free Trade Agreement analysis identified {fta_name} as the most favourable duty "
        f"treatment applicable to this shipment, with a preferential duty rate of {fta_rate}% "
        f"compared to the Most Favoured Nation (MFN) rate of {mfn_rate}%. This resulted in a total "
        f"duty saving of USD {saving:,.2f}. The total landed cost, inclusive of all applicable "
        f"duties, sales tax, and handling fees, has been computed at USD {total:,.2f}.\n\n"
        f"This shipment has been reviewed, verified, and formally approved by authorised compliance "
        f"personnel in accordance with internal standard operating procedures. All supporting "
        f"documentation is retained in the NEXA system audit trail in compliance with the seven-year "
        f"statutory record-keeping requirement under the Malaysian Customs Act 1967 and is available "
        f"for inspection by the Royal Malaysian Customs Department upon request."
    )
