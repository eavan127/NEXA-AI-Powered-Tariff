from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import io
from datetime import datetime


def generate_compliance_pdf(shipment: dict, audit_trail: list) -> bytes:
    """
    Generates a compliance PDF report for a single shipment.
    Returns PDF as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Colours ──
    TEAL    = colors.HexColor("#0d9488")
    AMBER   = colors.HexColor("#d97706")
    INK     = colors.HexColor("#1a1a18")
    MUTED   = colors.HexColor("#6b7280")
    SURFACE = colors.HexColor("#f5f5f0")

    # ── Custom styles ──
    title_style = ParagraphStyle("title", parent=styles["Normal"],
        fontSize=22, textColor=INK, fontName="Helvetica-Bold", spaceAfter=8, leading=28)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"],
        fontSize=10, textColor=MUTED, spaceAfter=2)
    section_style = ParagraphStyle("section", parent=styles["Normal"],
        fontSize=11, textColor=TEAL, fontName="Helvetica-Bold",
        spaceBefore=12, spaceAfter=6)
    small_style = ParagraphStyle("small", parent=styles["Normal"],
        fontSize=8, textColor=MUTED)
    wrap_style = ParagraphStyle("wrap", parent=styles["Normal"],
        fontSize=9, textColor=INK, wordWrap='CJK')

    # ── Extract nested data using CORRECT field names ──
    cls_list = shipment.get("hs_classifications") or []
    fta_list = shipment.get("fta_results") or []
    lc_list  = shipment.get("landed_costs") or []

    # Sort by created_at desc to get latest
    cls = sorted(cls_list, key=lambda x: x.get("created_at",""), reverse=True)[0] if cls_list else {}
    fta = sorted(fta_list, key=lambda x: x.get("created_at",""), reverse=True)[0] if fta_list else {}
    lc  = sorted(lc_list,  key=lambda x: x.get("created_at",""), reverse=True)[0] if lc_list  else {}

    cif = (shipment.get("shipment_value_usd", 0) +
           shipment.get("freight_cost_usd", 0) +
           shipment.get("insurance_cost_usd", 0))

    # ── Header ──
    story.append(Paragraph("NEXA · AI Tariff Intelligence", ParagraphStyle("brand",
        parent=styles["Normal"], fontSize=10, textColor=TEAL,
        fontName="Helvetica-Bold", spaceAfter=8)))
    story.append(Paragraph("Trade Compliance Report", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M UTC')}  |  Jabil Circuit Sdn. Bhd.",
        sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=12))

    # ── Shipment Details ──
    story.append(Paragraph("Shipment Details", section_style))
    shipment_data = [
        ["Field", "Value"],
        ["Shipment ID",          shipment.get("sap_shipment_id", "-")],
        ["Product",              shipment.get("product_description", "-")],
        ["Origin → Destination", f"{shipment.get('origin_country','-')} → {shipment.get('destination_country','-')}"],
        ["Shipment Value",       f"USD {shipment.get('shipment_value_usd', 0):,.2f}"],
        ["Freight Cost",         f"USD {shipment.get('freight_cost_usd', 0):,.2f}"],
        ["Insurance Cost",       f"USD {shipment.get('insurance_cost_usd', 0):,.2f}"],
        ["CIF Total",            f"USD {cif:,.2f}"],
        ["Status",               shipment.get("status", "-").upper()],
    ]
    t = Table(shipment_data, colWidths=[55*mm, 115*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), TEAL),
        ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
        ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, SURFACE]),
        ("GRID",           (0,0), (-1,-1), 0.5, colors.HexColor("#e5e5e0")),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
    ]))
    story.append(t)

    # ── Module A — HS Classification ──
    story.append(Paragraph("Module A — HS Classification", section_style))

    # correct field names: e2open_hs_code, ai_hs_code, final_hs_code, confidence_score, reasoning_text
    e2open_code  = cls.get("e2open_hs_code") or "-"
    ai_code      = cls.get("ai_hs_code")     or cls.get("final_hs_code") or "-"
    final_code   = cls.get("final_hs_code")  or "-"
    confidence   = cls.get("confidence_score") or 0
    reasoning    = cls.get("reasoning_text") or "-"
    override     = cls.get("analyst_override_hs") or None
    mod_a_status = cls.get("module_a_status") or "-"

    mod_a_data = [
        ["Field", "Value"],
        ["e2open Preliminary Code", e2open_code],
        ["AI Classified Code",      ai_code],
        ["Final HS Code",           final_code],
        ["Confidence Score",        f"{confidence}%"],
        ["Module A Status",         mod_a_status.replace("_", " ").title()],
        ["Analyst Override",        override if override else "None — AI recommendation accepted"],
        ["AI Reasoning",            Paragraph(reasoning, wrap_style)],
    ]
    t2 = Table(mod_a_data, colWidths=[55*mm, 115*mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
        ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, SURFACE]),
        ("GRID",           (0,0), (-1,-1), 0.5, colors.HexColor("#e5e5e0")),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t2)

    # ── Module B — FTA Match ──
    story.append(Paragraph("Module B — FTA Match", section_style))

    # correct field names: best_fta_name, best_fta_rate_pct, mfn_rate_pct, duty_saving_usd
    best_fta      = fta.get("best_fta_name")     or fta.get("best_fta") or "-"
    fta_rate      = fta.get("best_fta_rate_pct") or fta.get("fta_rate_pct") or 0
    mfn_rate      = fta.get("mfn_rate_pct")      or 0
    duty_saving   = fta.get("duty_saving_usd")   or 0
    fta_status    = fta.get("module_b_status")   or "-"
    is_fallback   = best_fta == "MFN"

    mod_b_data = [
        ["Field", "Value"],
        ["Best FTA Available",  best_fta],
        ["FTA Preferential Rate", f"{fta_rate}%"],
        ["MFN (Standard) Rate", f"{mfn_rate}%"],
        ["Duty Saving",         f"USD {duty_saving:,.2f}"],
        ["FTA Status",          "MFN Fallback — no FTA applicable" if is_fallback else "FTA Applied"],
    ]
    t3 = Table(mod_b_data, colWidths=[55*mm, 115*mm])
    t3.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), colors.HexColor("#b45309")),
        ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
        ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, SURFACE]),
        ("GRID",           (0,0), (-1,-1), 0.5, colors.HexColor("#e5e5e0")),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
    ]))
    story.append(t3)

    # ── Module C — Landed Cost ──
    story.append(Paragraph("Module C — Landed Cost", section_style))

    # correct field names: total_landed_cost_usd, duty_rate_applied_pct, fx_rate_myr, is_lmw_facility
    total_landed_usd = lc.get("total_landed_cost_usd") or lc.get("total_landed_usd") or 0
    total_duty_myr   = lc.get("total_duty_myr")        or 0
    fx_rate          = lc.get("fx_rate_myr")           or 0
    is_lmw           = lc.get("is_lmw_facility")       or False
    duty_rate        = lc.get("duty_rate_applied_pct") or lc.get("applied_fta_rate_pct") or 0
    fta_saving_usd   = lc.get("fta_saving_usd")        or 0

    mod_c_data = [
        ["Field", "Value"],
        ["Total Duty (MYR)",      f"MYR {total_duty_myr:,.2f}"],
        ["Total Landed Cost",     f"USD {total_landed_usd:,.2f}"],
        ["Duty Rate Applied",     f"{duty_rate}%"],
        ["FX Rate",               f"{fx_rate} MYR/USD"],
        ["FTA Saving",            f"USD {fta_saving_usd:,.2f}"],
        ["LMW Licensed Facility", "Yes — duty exemption applied" if is_lmw else "No"],
    ]
    t4 = Table(mod_c_data, colWidths=[55*mm, 115*mm])
    t4.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), colors.HexColor("#92400e")),
        ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
        ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, SURFACE]),
        ("GRID",           (0,0), (-1,-1), 0.5, colors.HexColor("#e5e5e0")),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("RIGHTPADDING",   (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
    ]))
    story.append(t4)

    # ── Audit Trail ──
    story.append(Paragraph("Audit Trail", section_style))
    audit_rows = [["Timestamp", "Event Type", "Note"]]
    for entry in sorted(audit_trail, key=lambda x: x.get("created_at", "")):
        audit_rows.append([
            entry.get("created_at", "")[:19].replace("T", " "),
            entry.get("event_type", "-").replace("_", " ").title(),
            Paragraph(entry.get("analyst_note", "-"), wrap_style)
        ])
    t5 = Table(audit_rows, colWidths=[38*mm, 35*mm, 97*mm])
    t5.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0), INK),
        ("TEXTCOLOR",      (0,0), (-1,0), colors.white),
        ("FONTNAME",       (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, SURFACE]),
        ("GRID",           (0,0), (-1,-1), 0.5, colors.HexColor("#e5e5e0")),
        ("LEFTPADDING",    (0,0), (-1,-1), 6),
        ("RIGHTPADDING",   (0,0), (-1,-1), 6),
        ("TOPPADDING",     (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 4),
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t5)

    # ── Footer ──
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED))
    story.append(Paragraph(
        "This report is generated by NEXA AI Tariff Intelligence. "
        "All duty figures have been reviewed and approved by a qualified Trade Compliance Analyst. "
        "Retained for 7 years per Malaysian Customs Act 1967.",
        small_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
