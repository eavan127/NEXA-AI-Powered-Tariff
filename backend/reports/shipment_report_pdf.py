"""
Formal corporate shipment approval report — Times New Roman, A4.
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#0d2240")
GOLD   = colors.HexColor("#b8924a")
INK    = colors.HexColor("#111111")
MUTED  = colors.HexColor("#555555")
RULE   = colors.HexColor("#c8b89a")
ROW_A  = colors.white
ROW_B  = colors.HexColor("#f7f5f0")
HEAD   = colors.HexColor("#0d2240")

TH_TEXT = colors.white
TD_TEXT = INK

# ── ReportLab built-in Times New Roman equivalents ───────────────────────────
# These are the 14 standard PDF fonts; no file embedding required.
SERIF        = "Times-Roman"
SERIF_BOLD   = "Times-Bold"
SERIF_ITALIC = "Times-Italic"
SERIF_BI     = "Times-BoldItalic"


def _styles():
    base = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], fontName=SERIF, **kw)

    return {
        "cover_title": ps("cover_title",
            fontName=SERIF_BOLD, fontSize=22, textColor=NAVY,
            leading=28, spaceAfter=6, alignment=TA_CENTER),

        "cover_sub": ps("cover_sub",
            fontName=SERIF_ITALIC, fontSize=11, textColor=MUTED,
            spaceAfter=4, alignment=TA_CENTER),

        "cover_ref": ps("cover_ref",
            fontName=SERIF, fontSize=9, textColor=MUTED,
            spaceAfter=2, alignment=TA_CENTER),

        "section": ps("section",
            fontName=SERIF_BOLD, fontSize=12, textColor=NAVY,
            spaceBefore=14, spaceAfter=6, leading=16),

        "body": ps("body",
            fontSize=10, textColor=INK, leading=15,
            spaceAfter=8, alignment=TA_JUSTIFY),

        "caption": ps("caption",
            fontName=SERIF_ITALIC, fontSize=8, textColor=MUTED,
            spaceAfter=6),

        "footer": ps("footer",
            fontName=SERIF_ITALIC, fontSize=8, textColor=MUTED,
            alignment=TA_CENTER),

        "cell_wrap": ps("cell_wrap",
            fontSize=9, textColor=INK, leading=13),
    }


def _th_style(bg=HEAD):
    return TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), bg),
        ("TEXTCOLOR",   (0, 0), (-1, 0), TH_TEXT),
        ("FONTNAME",    (0, 0), (-1, 0), SERIF_BOLD),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_A, ROW_B]),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#ddd8cc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",(0, 0), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0,0), (-1, -1), 5),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("FONTNAME",    (0, 1), (-1, -1), SERIF),
    ])


def _kv_table(rows: list[list], col_w=(58*mm, 112*mm), header_bg=HEAD) -> Table:
    t = Table(rows, colWidths=col_w)
    t.setStyle(_th_style(header_bg))
    return t


def _rule(story):
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=10))


def _section(story, number: str, title: str, s):
    story.append(Paragraph(f"{number}. {title.upper()}", s["section"]))


def generate_formal_report_pdf(shipment: dict, audit_trail: list,
                                narrative: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=f"Trade Compliance Report — {shipment.get('sap_shipment_id', '')}",
        author="NEXA AI Tariff Intelligence",
        subject="Approved Shipment Report",
    )

    s    = _styles()
    story = []

    # ── extract data ──────────────────────────────────────────────────────────
    cls = _latest(shipment.get("hs_classifications"))
    fta = _latest(shipment.get("fta_results"))
    lc  = _latest(shipment.get("landed_costs"))
    bom = shipment.get("bom_items") or []

    cif = (
        (shipment.get("shipment_value_usd") or 0)
        + (shipment.get("freight_cost_usd") or 0)
        + (shipment.get("insurance_cost_usd") or 0)
    )
    now = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")
    sid = shipment.get("sap_shipment_id", "N/A")

    # ══════════════════════════════════════════════════════════════════════════
    # COVER BLOCK
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 10 * mm))

    # Letterhead bar (navy block via table)
    header_data = [[
        Paragraph(
            "<font color='white'><b>NEXA</b> AI Tariff Intelligence &nbsp;·&nbsp; "
            "Jabil Circuit Sdn. Bhd.</font>",
            ParagraphStyle("lh", fontName=SERIF_BOLD, fontSize=10,
                           textColor=colors.white, leading=14)
        )
    ]]
    lh_table = Table(header_data, colWidths=[166 * mm])
    lh_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]))
    story.append(lh_table)
    story.append(Spacer(1, 12 * mm))

    story.append(Paragraph("TRADE COMPLIANCE REPORT", s["cover_title"]))
    story.append(Paragraph("Approved Shipment — Formal Record", s["cover_sub"]))
    story.append(Spacer(1, 4))

    story.append(Paragraph(f"Shipment Reference: <b>{sid}</b>", s["cover_ref"]))
    story.append(Paragraph(f"Report Generated: {now}", s["cover_ref"]))
    story.append(Paragraph(
        f"Status: <b>{shipment.get('status', 'N/A').upper()}</b>", s["cover_ref"]))
    story.append(Spacer(1, 6 * mm))
    _rule(story)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    _section(story, "1", "Executive Summary", s)
    for para in narrative.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para, s["body"]))

    _rule(story)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — SHIPMENT PARTICULARS
    # ══════════════════════════════════════════════════════════════════════════
    _section(story, "2", "Shipment Particulars", s)
    ship_rows = [
        ["Field", "Value"],
        ["Shipment Reference",    sid],
        ["Product Description",   shipment.get("product_description", "-")],
        ["Origin Country",        shipment.get("origin_country", "-")],
        ["Destination Country",   shipment.get("destination_country", "-")],
        ["Shipment Value (FOB)",  f"USD {shipment.get('shipment_value_usd', 0) or 0:,.2f}"],
        ["Freight Cost",          f"USD {shipment.get('freight_cost_usd', 0) or 0:,.2f}"],
        ["Insurance Cost",        f"USD {shipment.get('insurance_cost_usd', 0) or 0:,.2f}"],
        ["CIF Total",             f"USD {cif:,.2f}"],
        ["Bill of Lading No.",    shipment.get("bill_of_lading_number", "-") or "-"],
        ["Vessel Name",           shipment.get("vessel_name", "-") or "-"],
        ["Port of Loading",       shipment.get("port_of_loading", "-") or "-"],
        ["Transport Mode",        (shipment.get("transport_mode") or "-").upper()],
        ["Loading Date",          _date(shipment.get("vessel_loading_date"))],
        ["Est. Arrival Date",     _date(shipment.get("estimated_arrival_date"))],
        ["Approval Status",       (shipment.get("status") or "-").upper()],
    ]
    story.append(_kv_table(ship_rows))
    _rule(story)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — CUSTOMS TARIFF CLASSIFICATION
    # ══════════════════════════════════════════════════════════════════════════
    _section(story, "3", "Customs Tariff Classification (Module A)", s)
    conf_raw = cls.get("confidence_score") or 0
    override = cls.get("analyst_override_hs")
    cls_rows = [
        ["Field", "Value"],
        ["e2open Preliminary HS Code",  cls.get("e2open_hs_code") or "-"],
        ["AI-Classified HS Code",       cls.get("ai_hs_code") or "-"],
        ["Final Accepted HS Code",      cls.get("final_hs_code") or "-"],
        ["AI Confidence Score",         f"{conf_raw}%"],
        ["Classification Status",
         (cls.get("module_a_status") or "-").replace("_", " ").title()],
        ["Analyst Override",
         override if override else "None — AI recommendation accepted"],
        ["Analyst Note",                cls.get("analyst_note") or "-"],
        ["AI Reasoning",
         Paragraph(cls.get("reasoning_text") or "-", s["cell_wrap"])],
    ]
    story.append(_kv_table(cls_rows, header_bg=colors.HexColor("#0f4c75")))
    _rule(story)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — FREE TRADE AGREEMENT ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    _section(story, "4", "Free Trade Agreement Analysis (Module B)", s)
    is_mfn   = (fta.get("best_fta_name") or "MFN") == "MFN"
    fta_rows = [
        ["Field", "Value"],
        ["FTA Agreement Applied",     fta.get("best_fta_name") or "MFN"],
        ["Preferential Duty Rate",    f"{fta.get('best_fta_rate_pct') or 0}%"],
        ["MFN (Standard) Duty Rate",  f"{fta.get('mfn_rate_pct') or 0}%"],
        ["Rules of Origin Type",      (fta.get("roo_type") or "-").upper()],
        ["RVC Supplier Declared",     f"{fta.get('rvc_supplier_declared') or 0}%"],
        ["RVC Threshold",             f"{fta.get('rvc_threshold') or 0}%"],
        ["Rules of Origin Passed",    "Yes" if fta.get("roo_passed") else "No"],
        ["Duty Saving",               f"USD {fta.get('duty_saving_usd') or 0:,.2f}"],
        ["FTA Module Status",
         "MFN Fallback — no FTA applicable" if is_mfn else
         (fta.get("module_b_status") or "FTA Applied").replace("_", " ").title()],
    ]
    story.append(_kv_table(fta_rows, header_bg=colors.HexColor("#7c4f12")))
    _rule(story)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — LANDED COST COMPUTATION
    # ══════════════════════════════════════════════════════════════════════════
    _section(story, "5", "Landed Cost Computation (Module C)", s)
    lc_rows = [
        ["Field", "Value"],
        ["CIF Value",              f"USD {lc.get('cif_value_usd') or cif:,.2f}"],
        ["Duty Rate Applied",      f"{lc.get('duty_rate_applied_pct') or 0}%"],
        ["Total Duty (MYR)",       f"MYR {lc.get('total_duty_myr') or 0:,.2f}"],
        ["GST / Sales Tax",        f"USD {lc.get('gst_amount_usd') or 0:,.2f}"],
        ["Other Fees",             f"USD {lc.get('other_fees_usd') or 0:,.2f}"],
        ["FX Rate",                f"{lc.get('fx_rate_myr') or 0} MYR / USD"],
        ["LMW Licensed Facility",
         "Yes — duty exemption applied" if lc.get("is_lmw_facility") else "No"],
        ["FTA Saving",             f"USD {lc.get('fta_saving_usd') or 0:,.2f}"],
        ["MFN Scenario Cost",      f"USD {lc.get('mfn_scenario_cost_usd') or 0:,.2f}"],
        ["Total Landed Cost (USD)",f"USD {lc.get('total_landed_cost_usd') or 0:,.2f}"],
    ]
    story.append(_kv_table(lc_rows, header_bg=colors.HexColor("#3d2a0a")))

    # Cost breakdown sub-table
    breakdown = lc.get("cost_breakdown") or []
    if breakdown:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Cost Breakdown by Line Item", s["caption"]))
        bd_header = [["SKU", "Qty", "Unit Value", "Weight (kg)",
                       "Duty Rate", "Duty Amount", "FTA Saving"]]
        bd_rows = []
        for item in breakdown:
            bd_rows.append([
                str(item.get("sku") or item.get("product_code") or "-"),
                str(item.get("quantity") or "-"),
                f"USD {item.get('unit_value_usd') or 0:,.2f}",
                str(item.get("weight_kg") or "-"),
                f"{item.get('duty_rate_pct') or item.get('duty_rate') or 0}%",
                f"USD {item.get('duty_amount_usd') or 0:,.2f}",
                f"USD {item.get('fta_saving_usd') or 0:,.2f}",
            ])
        bd_table = Table(
            bd_header + bd_rows,
            colWidths=[28*mm, 14*mm, 26*mm, 22*mm, 20*mm, 26*mm, 24*mm],
        )
        bd_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), SERIF_BOLD),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("FONTNAME",     (0, 1), (-1, -1), SERIF),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_A, ROW_B]),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#ddd8cc")),
            ("ALIGN",        (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ]))
        story.append(bd_table)

    _rule(story)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6 — BILL OF MATERIALS (if present)
    # ══════════════════════════════════════════════════════════════════════════
    if bom:
        _section(story, "6", "Bill of Materials", s)
        bom_header = [["Product Code", "Description", "Quantity", "Weight (kg)",
                        "Unit Value (USD)"]]
        bom_rows = []
        for item in bom:
            bom_rows.append([
                str(item.get("product_code") or item.get("sku") or "-"),
                str(item.get("description") or item.get("product_description") or "-"),
                str(item.get("quantity") or "-"),
                str(item.get("weight_kg") or "-"),
                f"{item.get('unit_value_usd') or 0:,.2f}",
            ])
        bom_table = Table(
            bom_header + bom_rows,
            colWidths=[30*mm, 66*mm, 18*mm, 22*mm, 30*mm],
        )
        bom_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), SERIF_BOLD),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("FONTNAME",     (0, 1), (-1, -1), SERIF),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_A, ROW_B]),
            ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#ddd8cc")),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ]))
        story.append(bom_table)
        _rule(story)
        next_section = "7"
    else:
        next_section = "6"

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6/7 — AUDIT TRAIL
    # ══════════════════════════════════════════════════════════════════════════
    _section(story, next_section, "Audit Trail & Compliance Record", s)
    audit_header = [["Timestamp (UTC)", "Event Type", "Analyst", "Action", "Note"]]
    audit_rows   = []
    for entry in sorted(audit_trail, key=lambda x: x.get("created_at", "")):
        audit_rows.append([
            _date_full(entry.get("created_at")),
            (entry.get("event_type") or "-").replace("_", " ").title(),
            entry.get("analyst_id") or "-",
            (entry.get("analyst_action") or "-").title(),
            Paragraph(entry.get("analyst_note") or "-", s["cell_wrap"]),
        ])
    if not audit_rows:
        audit_rows = [["—", "—", "—", "—", "No audit entries recorded."]]

    audit_table = Table(
        audit_header + audit_rows,
        colWidths=[30*mm, 30*mm, 22*mm, 18*mm, 66*mm],
    )
    audit_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#1a1a18")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), SERIF_BOLD),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("FONTNAME",     (0, 1), (-1, -1), SERIF),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_A, ROW_B]),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#ddd8cc")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(audit_table)

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=0.8, color=GOLD, spaceAfter=6))
    story.append(Paragraph(
        "CONFIDENTIAL — This report is generated by the NEXA AI Tariff Intelligence System. "
        "All duty figures have been reviewed and formally approved by a qualified Trade Compliance Analyst. "
        "This document constitutes an official compliance record and is retained for a minimum of "
        "seven (7) years in accordance with the Malaysian Customs Act 1967. "
        "Unauthorised disclosure is strictly prohibited.",
        s["footer"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"© {datetime.utcnow().year} Jabil Circuit Sdn. Bhd. &nbsp;|&nbsp; "
        f"NEXA AI Tariff Intelligence &nbsp;|&nbsp; Report generated {now}",
        s["footer"],
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ── helpers ───────────────────────────────────────────────────────────────────

def _latest(lst) -> dict:
    if not lst:
        return {}
    return sorted(lst, key=lambda x: x.get("created_at", ""), reverse=True)[0]


def _date(val) -> str:
    if not val:
        return "-"
    return str(val)[:10]


def _date_full(val) -> str:
    if not val:
        return "-"
    return str(val)[:19].replace("T", " ")
