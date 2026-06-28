"""
chat_analytics.py — pandas/numpy-backed statistics for the NEXA chatbox,
with qwen2.5:1.5b (via Ollama) used ONLY to phrase a role-appropriate
framing sentence around facts that are already computed deterministically.

Design principle (matches the case study's own "Ethical AI vs Pure
Automation" theme): the LLM never computes or states a number itself —
every figure, chart, and citation is produced by pandas/numpy/SQL and
appended in code. Qwen only adjusts tone for the audience (Analyst vs
Compliance Manager). If Ollama is unreachable, the deterministic reply
is used as-is — there is no silent gap in functionality.

NEXA is a cost-avoidance tool (tariff/duty calculation), not a revenue
system — there is no "profit" column anywhere in the schema. The closest
business-equivalent metric is FTA duty savings (landed_costs.fta_saving_usd),
so "profit" queries are answered with savings data and a note clarifying
the distinction.
"""
import base64
from io import BytesIO

import matplotlib
matplotlib.use("Agg")  # headless — no display on a server process
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
import re

import httpx

from config import settings

_NUMERIC_COLS = (
    "total_landed_cost_usd",
    "duty_amount_usd",
    "fta_saving_usd",
    "mfn_scenario_cost_usd",
)

_QWEN_MODEL = "qwen2.5:1.5b"

_ROLE_PROMPTS = {
    "analyst": (
        "You are writing for a Trade Compliance Analyst who needs precise, "
        "operational framing — focus on what to verify or act on next. "
        "Write exactly one short sentence (max 25 words)."
    ),
    "manager": (
        "You are writing for a Compliance Manager who needs a strategic, "
        "risk- and ROI-oriented framing — keep it decision-focused, not "
        "operational detail. Write exactly one short sentence (max 25 words)."
    ),
}


# ── Data loading ───────────────────────────────────────────────────
def _load_landed_costs_df(supabase) -> pd.DataFrame:
    res = supabase.table("landed_costs").select(
        "shipment_id, total_landed_cost_usd, duty_amount_usd, "
        "fta_saving_usd, mfn_scenario_cost_usd, created_at"
    ).execute()
    df = pd.DataFrame(res.data or [])
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    for col in _NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _filter_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    if df.empty or period == "all":
        return df
    now = pd.Timestamp.now(tz="UTC")
    start = {
        "today": now.normalize(),
        "week":  now - pd.Timedelta(days=7),
        "month": now - pd.Timedelta(days=30),
    }.get(period)
    return df[df["created_at"] >= start] if start is not None else df


def _mode_bucketed(series: pd.Series):
    """Continuous dollar values rarely repeat exactly — bucket to the
    nearest $10 before taking the mode so it's a meaningful statistic."""
    if series.empty:
        return None
    bucketed = (series / 10).round() * 10
    m = bucketed.mode()
    return float(m.iloc[0]) if not m.empty else None


def _by_day(df: pd.DataFrame, value_col: str) -> list[dict]:
    grouped = (
        df.assign(day=df["created_at"].dt.date)
          .groupby("day")[value_col].sum()
          .reset_index()
          .sort_values("day")
    )
    return [{"day": str(r.day), "value": float(np.round(getattr(r, value_col), 2))}
            for r in grouped.itertuples()]


# ── Citations — deterministic, never LLM-generated ─────────────────
def _internal_citation(table: str, count: int, df: pd.DataFrame) -> str:
    if df.empty or "created_at" not in df:
        return f"Internal: {count} record(s) from `{table}` (Supabase, queried live)."
    start = df["created_at"].min().date()
    end = df["created_at"].max().date()
    return (f"Internal: {count} record(s) from `{table}`, dated {start} to {end} "
            "(Supabase, queried live).")


def _external_citations_for_ftas(supabase, shipment_ids: list) -> list[str]:
    """Looks up the source PDF + page for any FTA actually used by these
    shipments — only cites a document when one is genuinely on file."""
    if not shipment_ids:
        return []
    try:
        fr = supabase.table("fta_results").select("best_fta_name") \
            .in_("shipment_id", shipment_ids).execute()
        names = sorted({r["best_fta_name"] for r in (fr.data or []) if r.get("best_fta_name")})
        if not names:
            return []
        rates = supabase.table("fta_rates").select("fta_name,pdf_source_url,pdf_page_number") \
            .in_("fta_name", names).not_.is_("pdf_source_url", "null").limit(50).execute()
        seen = {}
        for r in (rates.data or []):
            seen.setdefault(r["fta_name"], r)
        return [
            f"External: {fta} rate schedule — {r['pdf_source_url']}"
            + (f" (p.{r['pdf_page_number']})" if r.get("pdf_page_number") else "")
            for fta, r in seen.items()
        ]
    except Exception:
        return []


# ── Chart rendering (pandas .plot() over a headless matplotlib Agg backend) ──
def _render_bar_chart_png(by_day: list, title: str) -> str | None:
    """Deliberately does NOT overlay per-shipment mean/median as reference
    lines — those are computed over individual shipments, while these bars
    are daily *sums* across many shipments. Mixing the two units on one
    axis would mislead a viewer. Mean/median stay in the text reply."""
    if not by_day:
        return None

    series = pd.Series([d["value"] for d in by_day], index=[d["day"] for d in by_day], name=title)

    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=130)
    series.plot(kind="bar", ax=ax, color="#0090cf", edgecolor="#0164a1", width=0.65, legend=False)
    _style_axes(ax, fig, title)
    return _fig_to_data_uri(fig)


def _render_forecast_chart_png(history: list, forecast: list, title: str) -> str | None:
    if not history:
        return None
    hist = pd.Series([d["value"] for d in history], index=[d["day"] for d in history])
    fc   = pd.Series([d["value"] for d in forecast], index=[d["day"] for d in forecast])
    combined = pd.concat([hist, fc])
    colors = ["#0090cf"] * len(hist) + ["#e8a55a"] * len(fc)

    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=130)
    combined.plot(kind="bar", ax=ax, color=colors, edgecolor="#576d84", width=0.65, legend=False)
    if len(hist) > 0:
        ax.axvline(len(hist) - 0.5, color="#576d84", linestyle="--", linewidth=1)
    handles = [mpatches.Patch(color="#0090cf", label="Actual"),
               mpatches.Patch(color="#e8a55a", label="Forecast (linear trend)")]
    ax.legend(handles=handles, fontsize=8, frameon=False, loc="upper left")
    _style_axes(ax, fig, title)
    return _fig_to_data_uri(fig)


def _style_axes(ax, fig, title: str) -> None:
    ax.set_title(title, fontsize=11, color="#002b49", fontweight="bold", pad=10)
    ax.set_ylabel("USD", fontsize=9, color="#576d84")
    ax.tick_params(axis="x", rotation=35, labelsize=8, colors="#576d84")
    ax.tick_params(axis="y", labelsize=8, colors="#576d84")
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#dbe5ee")
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    fig.tight_layout()


def _fig_to_data_uri(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor="#ffffff")
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("ascii")


# ── Overview stats ──────────────────────────────────────────────────
def _overview(df: pd.DataFrame, value_col: str) -> dict:
    if df.empty:
        return {"count": 0, "total": 0.0, "mean": 0.0, "median": 0.0,
                "mode": None, "std": 0.0, "by_day": []}
    series = df[value_col]
    return {
        "count":  int(len(df)),
        "total":  float(np.round(series.sum(), 2)),
        "mean":   float(np.round(series.mean(), 2)),
        "median": float(np.round(series.median(), 2)),
        "mode":   _mode_bucketed(series),
        "std":    float(np.round(series.std(ddof=0), 2)) if len(df) > 1 else 0.0,
        "by_day": _by_day(df, value_col),
    }


def savings_overview(supabase, period: str = "all") -> dict:
    df = _filter_period(_load_landed_costs_df(supabase), period)
    return _overview(df, "fta_saving_usd")


def cost_overview(supabase, period: str = "all") -> dict:
    df = _filter_period(_load_landed_costs_df(supabase), period)
    return _overview(df, "total_landed_cost_usd")


# ── Forecast — linear trend over daily savings, projected forward ──
def forecast_savings(supabase, horizon_days: int = 7) -> dict:
    """Simple linear regression (numpy.polyfit) over the daily savings
    series, projected `horizon_days` forward. This is explicitly NOT a
    sophisticated time-series model — it's a transparent trendline, and
    the reply always says so. Predicting cannot go negative (savings
    can't be less than $0)."""
    df = _load_landed_costs_df(supabase)
    by_day = _by_day(df, "fta_saving_usd") if not df.empty else []

    if len(by_day) < 2:
        return {"insufficient_data": True, "count": len(by_day), "history": by_day}

    dates = [pd.Timestamp(d["day"]) for d in by_day]
    values = np.array([d["value"] for d in by_day], dtype=float)
    x = np.array([(d - dates[0]).days for d in dates], dtype=float)

    slope, intercept = np.polyfit(x, values, 1)
    last_x = x[-1]
    future_x = np.arange(last_x + 1, last_x + 1 + horizon_days)
    future_values = np.clip(slope * future_x + intercept, 0, None)

    future_dates = [dates[-1] + pd.Timedelta(days=int(i)) for i in range(1, horizon_days + 1)]
    forecast = [{"day": str(d.date()), "value": float(np.round(v, 2))}
                for d, v in zip(future_dates, future_values)]

    trend = "increasing" if slope > 1 else "decreasing" if slope < -1 else "roughly flat"

    return {
        "insufficient_data": False,
        "count": len(by_day),
        "trend": trend,
        "slope_per_day": float(np.round(slope, 2)),
        "predicted_total": float(np.round(future_values.sum(), 2)),
        "horizon_days": horizon_days,
        "history": by_day,
        "forecast": forecast,
    }


# ── Qwen synthesis — framing only, never figures ────────────────────
_HAS_DIGIT = re.compile(r"\d")


def _qwen_intro(role: str, facts_text: str) -> str | None:
    """Asks qwen for a one-sentence, role-appropriate framing. The model is
    instructed not to state any figures, but small models don't reliably
    follow that — so any response containing a digit is discarded rather
    than trusted. A small model restating a number it wasn't authoritative
    over is exactly the failure mode this whole pipeline is designed to
    avoid (see module docstring)."""
    role = role if role in _ROLE_PROMPTS else "analyst"
    prompt = (
        f"{_ROLE_PROMPTS[role]}\n\n"
        f"FACTS (for context only — do not state any number, dollar amount, "
        f"percentage, or count from these facts):\n{facts_text}\n\n"
        "Write only the framing sentence, nothing else — purely qualitative, no digits at all."
    )
    try:
        resp = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={"model": _QWEN_MODEL, "prompt": prompt, "stream": False,
                  "options": {"num_predict": 60, "temperature": 0.2}},
            timeout=15.0,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        if not text or _HAS_DIGIT.search(text):
            return None
        return text
    except Exception:
        return None


def _fmt_money(n) -> str:
    return f"${n:,.2f}"


def _detect_period(text: str) -> str:
    if "today" in text:
        return "today"
    if "week" in text:
        return "week"
    if "month" in text:
        return "month"
    return "all"


# ── Main entry point ─────────────────────────────────────────────────
def answer_chat_query(message: str, supabase, role: str = "analyst") -> dict:
    """Routes a free-text chatbox message. Returns
    {reply, chart_image, stats, citations, role}."""
    text = (message or "").lower()
    role = role if role in _ROLE_PROMPTS else "analyst"

    wants_forecast = any(w in text for w in
        ("predict", "forecast", "projection", "what if", "next week", "next month", "trend", "future"))
    wants_savings = any(w in text for w in
        ("profit", "saving", "savings", "earn", "earning", "margin"))
    wants_cost = any(w in text for w in
        ("cost", "expense", "spend", "spending", "landed cost", "duty"))

    # ── Forecast ──────────────────────────────────────────────────
    if wants_forecast:
        f = forecast_savings(supabase, horizon_days=7)
        if f.get("insufficient_data"):
            return {
                "reply": ("Not enough historical data yet for a forecast (need at least 2 days "
                           "with recorded savings). NEXA also doesn't track \"profit\" — the "
                           "closest metric is FTA duty savings."),
                "chart_image": None, "stats": f, "citations": [], "role": role,
            }

        facts = (
            f"Linear trend over {f['count']} day(s) of historical FTA savings data: "
            f"{f['trend']}, slope ${f['slope_per_day']}/day. Projected savings over the next "
            f"{f['horizon_days']} days: {_fmt_money(f['predicted_total'])}."
        )
        intro = _qwen_intro(role, facts)
        deterministic = (
            f"NEXA doesn't track \"profit\" — this is a projection of FTA duty savings, not revenue. "
            f"Based on a linear trend over the last {f['count']} day(s) of data ({f['trend']}), "
            f"projected savings for the next {f['horizon_days']} days: "
            f"{_fmt_money(f['predicted_total'])}. This is a simple trendline extrapolation, not a "
            "predictive model — treat it as directional, not a committed forecast."
        )
        reply = f"{intro}\n\n{deterministic}" if intro else deterministic
        citations = ["Internal: linear regression (numpy.polyfit) over `landed_costs.fta_saving_usd`, "
                     "grouped by day, computed live from Supabase."]
        chart_image = _render_forecast_chart_png(f["history"], f["forecast"], "Savings Forecast (USD)")
        return {"reply": reply, "chart_image": chart_image, "stats": f, "citations": citations, "role": role}

    # ── Savings ───────────────────────────────────────────────────
    if wants_savings:
        period = _detect_period(text)
        period_label = {"today": "today", "week": "the last 7 days", "month": "the last 30 days", "all": "all time"}[period]
        df = _filter_period(_load_landed_costs_df(supabase), period)
        s = _overview(df, "fta_saving_usd")

        if s["count"] == 0:
            return {
                "reply": (f"No landed-cost records found for {period_label}. NEXA tracks duty "
                           "savings, not \"profit\" — this is a cost-avoidance tool, not a revenue system."),
                "chart_image": None, "stats": s, "citations": [], "role": role,
            }

        facts = (f"FTA duty savings for {period_label}: total {_fmt_money(s['total'])} across "
                 f"{s['count']} shipments, mean {_fmt_money(s['mean'])}, median {_fmt_money(s['median'])}.")
        intro = _qwen_intro(role, facts)
        deterministic = (
            f"NEXA doesn't store \"profit\" — it's a cost-avoidance tool, so the closest metric is "
            f"FTA duty savings. For {period_label}: {_fmt_money(s['total'])} saved across "
            f"{s['count']} shipment(s). Mean {_fmt_money(s['mean'])} · Median {_fmt_money(s['median'])} · "
            f"Mode {_fmt_money(s['mode']) if s['mode'] is not None else 'n/a'} per shipment."
        )
        reply = f"{intro}\n\n{deterministic}" if intro else deterministic

        citations = [_internal_citation("landed_costs", s["count"], df)]
        citations += _external_citations_for_ftas(supabase, df["shipment_id"].tolist())

        chart_image = _render_bar_chart_png(s["by_day"], "FTA Savings by Day (USD)")
        return {"reply": reply, "chart_image": chart_image, "stats": s, "citations": citations, "role": role}

    # ── Cost ──────────────────────────────────────────────────────
    if wants_cost:
        period = _detect_period(text)
        period_label = {"today": "today", "week": "the last 7 days", "month": "the last 30 days", "all": "all time"}[period]
        df = _filter_period(_load_landed_costs_df(supabase), period)
        s = _overview(df, "total_landed_cost_usd")

        if s["count"] == 0:
            return {"reply": f"No landed-cost records found for {period_label}.",
                     "chart_image": None, "stats": s, "citations": [], "role": role}

        facts = (f"Total landed cost for {period_label}: {_fmt_money(s['total'])} across "
                 f"{s['count']} shipments, mean {_fmt_money(s['mean'])}, median {_fmt_money(s['median'])}.")
        intro = _qwen_intro(role, facts)
        deterministic = (
            f"Total landed cost for {period_label}: {_fmt_money(s['total'])} across {s['count']} "
            f"shipment(s). Mean {_fmt_money(s['mean'])} · Median {_fmt_money(s['median'])} · "
            f"Mode {_fmt_money(s['mode']) if s['mode'] is not None else 'n/a'} per shipment."
        )
        reply = f"{intro}\n\n{deterministic}" if intro else deterministic

        citations = [_internal_citation("landed_costs", s["count"], df)]
        citations += _external_citations_for_ftas(supabase, df["shipment_id"].tolist())

        chart_image = _render_bar_chart_png(s["by_day"], "Landed Cost by Day (USD)")
        return {"reply": reply, "chart_image": chart_image, "stats": s, "citations": citations, "role": role}

    return {
        "reply": (
            "I can answer questions about FTA duty savings, landed cost, or a savings forecast — try "
            "\"what's our savings today\", \"show cost this month\", or \"predict next week's savings\". "
            "NEXA doesn't track \"profit\" directly since it's a cost-avoidance tool, not a revenue P&L."
        ),
        "chart_image": None, "stats": None, "citations": [], "role": role,
    }
