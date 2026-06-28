"""
monthly_report_pdf.py — combined savings + cost + forecast PDF, generated
on request from the NEXA chatbot ("generate monthly report" etc.).

Reuses the same pandas/numpy stats and matplotlib chart renderers as the
chatbox (analytics/chat_analytics.py) rather than recomputing anything —
the PDF and the chat reply are always backed by the identical numbers.

English only: reportlab's default fonts (same ones compliance_pdf.py
uses) can't render CJK without embedding extra font files, so this does
not attempt to localize the document itself, even though the chat reply
announcing it may be in Bahasa Malaysia or Mandarin.
"""
import base64
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage

from analytics.chat_analytics import (
    savings_overview, cost_overview, forecast_savings,
    _render_bar_chart_png, _render_forecast_chart_png, _external_citations_for_ftas,
)

TEAL    = colors.HexColor("#0d9488")
AMBER   = colors.HexColor("#d97706")
INK     = colors.HexColor("#1a1a18")
MUTED   = colors.HexColor("#6b7280")
SURFACE = colors.HexColor("#f5f5f0")

_TABLE_STYLE = TableStyle([
    ("BACKGROUND",     (0, 0), (-1, 0), TEAL),
    ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
    ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE",       (0, 0), (-1, -1), 9),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
    ("GRID",           (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e5e0")),
    ("LEFTPADDING",    (0, 0), (-1, -1), 8),
    ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
    ("TOPPADDING",     (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
])

_PERIOD_LABEL = {"today": "Today", "week": "the Last 7 Days", "month": "the Last 30 Days", "all": "All Time"}


def _fmt_money(n) -> str:
    return f"${n:,.2f}"


def _stats_table(overview: dict) -> Table:
    data = [
        ["Metric", "Value"],
        ["Count",  str(overview["count"])],
        ["Total",  _fmt_money(overview["total"])],
        ["Mean",   _fmt_money(overview["mean"])],
        ["Median", _fmt_money(overview["median"])],
        ["Mode",   _fmt_money(overview["mode"]) if overview["mode"] is not None else "n/a"],
        ["Std Dev", _fmt_money(overview["std"])],
    ]
    t = Table(data, colWidths=[55 * mm, 115 * mm])
    t.setStyle(_TABLE_STYLE)
    return t


def _embed_chart(story: list, data_uri: str | None, max_width_mm: float = 160.0) -> None:
    if not data_uri:
        return
    raw = base64.b64decode(data_uri.split(",", 1)[1])
    iw, ih = ImageReader(io.BytesIO(raw)).getSize()
    width = max_width_mm * mm
    height = width * (ih / float(iw))
    story.append(Spacer(1, 6))
    story.append(RLImage(io.BytesIO(raw), width=width, height=height))


def generate_monthly_report_pdf(supabase, period: str = "month") -> bytes:
    """Returns a combined savings + cost + 7-day forecast PDF as bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm,
                             topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("title", parent=styles["Normal"], fontSize=22, textColor=INK,
                                  fontName="Helvetica-Bold", spaceAfter=8, leading=28)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=2)
    section_style = ParagraphStyle("section", parent=styles["Normal"], fontSize=13, textColor=TEAL,
                                    fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=6)
    note_style = ParagraphStyle("note", parent=styles["Normal"], fontSize=9, textColor=MUTED,
                                 fontName="Helvetica-Oblique", spaceAfter=4)

    period_label = _PERIOD_LABEL.get(period, period)

    # ── Header ──
    story.append(Paragraph("NEXA · AI Tariff Intelligence", ParagraphStyle(
        "brand", parent=styles["Normal"], fontSize=10, textColor=TEAL,
        fontName="Helvetica-Bold", spaceAfter=8)))
    story.append(Paragraph(f"Tariff Savings & Cost Report — {period_label}", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M UTC')}", sub_style))
    story.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=12))

    savings = savings_overview(supabase, period)
    cost = cost_overview(supabase, period)
    forecast = forecast_savings(supabase, horizon_days=7)

    # ── FTA Duty Savings ──
    story.append(Paragraph("FTA Duty Savings", section_style))
    story.append(_stats_table(savings))
    _embed_chart(story, _render_bar_chart_png(savings["by_day"], "FTA Savings by Day (USD)"))

    # ── Landed Cost ──
    story.append(Paragraph("Total Landed Cost", section_style))
    story.append(_stats_table(cost))
    _embed_chart(story, _render_bar_chart_png(cost["by_day"], "Landed Cost by Day (USD)"))

    # ── Forecast ──
    story.append(Paragraph("7-Day Savings Forecast", section_style))
    if forecast.get("insufficient_data"):
        story.append(Paragraph(
            "Not enough historical data yet for a forecast (need at least 2 days with recorded savings).",
            note_style))
    else:
        story.append(Paragraph(
            f"Linear trend over {forecast['count']} day(s) of history: {forecast['trend']}, "
            f"slope {_fmt_money(forecast['slope_per_day'])}/day. Projected savings over the next "
            f"{forecast['horizon_days']} days: {_fmt_money(forecast['predicted_total'])}. "
            "This is a simple trendline extrapolation, not a predictive model.", note_style))
        _embed_chart(story, _render_forecast_chart_png(
            forecast["history"], forecast["forecast"], "Savings Forecast (USD)", "Actual", "Forecast (linear trend)"))

    # ── Citations ──
    story.append(Paragraph("Sources", section_style))
    shipment_ids = []
    if savings["count"]:
        from analytics.chat_analytics import _load_landed_costs_df, _filter_period
        df = _filter_period(_load_landed_costs_df(supabase), period)
        shipment_ids = df["shipment_id"].tolist() if not df.empty else []
    citations = [f"Internal: {savings['count']} record(s) from `landed_costs`, computed live from Supabase."]
    citations += _external_citations_for_ftas("en", supabase, shipment_ids)
    for c in citations:
        story.append(Paragraph(f"• {c}", note_style))

    doc.build(story)
    return buffer.getvalue()
