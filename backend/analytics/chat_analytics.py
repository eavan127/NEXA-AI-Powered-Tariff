"""
chat_analytics.py — pandas/numpy-backed statistics for the NEXA chatbox.

NEXA is a cost-avoidance tool (tariff/duty calculation), not a revenue
system — there is no "profit" column anywhere in the schema. The closest
business-equivalent metric is FTA duty savings (landed_costs.fta_saving_usd),
so "profit" queries are answered with savings data and a note clarifying
the distinction.
"""
import pandas as pd
import numpy as np

_NUMERIC_COLS = (
    "total_landed_cost_usd",
    "duty_amount_usd",
    "fta_saving_usd",
    "mfn_scenario_cost_usd",
)


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


def savings_overview(supabase, period: str = "all") -> dict:
    df = _filter_period(_load_landed_costs_df(supabase), period)
    if df.empty:
        return {"count": 0, "total": 0.0, "mean": 0.0, "median": 0.0,
                "mode": None, "std": 0.0, "by_day": []}

    saving = df["fta_saving_usd"]
    return {
        "count":  int(len(df)),
        "total":  float(np.round(saving.sum(), 2)),
        "mean":   float(np.round(saving.mean(), 2)),
        "median": float(np.round(saving.median(), 2)),
        "mode":   _mode_bucketed(saving),
        "std":    float(np.round(saving.std(ddof=0), 2)) if len(df) > 1 else 0.0,
        "by_day": _by_day(df, "fta_saving_usd"),
    }


def cost_overview(supabase, period: str = "all") -> dict:
    df = _filter_period(_load_landed_costs_df(supabase), period)
    if df.empty:
        return {"count": 0, "total": 0.0, "mean": 0.0, "median": 0.0,
                "mode": None, "std": 0.0, "by_day": []}

    cost = df["total_landed_cost_usd"]
    return {
        "count":  int(len(df)),
        "total":  float(np.round(cost.sum(), 2)),
        "mean":   float(np.round(cost.mean(), 2)),
        "median": float(np.round(cost.median(), 2)),
        "mode":   _mode_bucketed(cost),
        "std":    float(np.round(cost.std(ddof=0), 2)) if len(df) > 1 else 0.0,
        "by_day": _by_day(df, "total_landed_cost_usd"),
    }


def _detect_period(text: str) -> str:
    if "today" in text:
        return "today"
    if "week" in text:
        return "week"
    if "month" in text:
        return "month"
    return "all"


def _fmt_money(n) -> str:
    return f"${n:,.2f}"


def answer_chat_query(message: str, supabase) -> dict:
    """Routes a free-text chatbox message to the right stats lookup.
    Returns {reply: str, chart: dict|None, stats: dict|None}."""
    text = (message or "").lower()
    period = _detect_period(text)
    period_label = {"today": "today", "week": "the last 7 days",
                     "month": "the last 30 days", "all": "all time"}[period]

    wants_savings = any(w in text for w in
        ("profit", "saving", "savings", "earn", "earning", "margin"))
    wants_cost = any(w in text for w in
        ("cost", "expense", "spend", "spending", "landed cost", "duty"))

    if wants_savings:
        s = savings_overview(supabase, period)
        if s["count"] == 0:
            reply = (f"No landed-cost records found for {period_label}. Note: NEXA tracks duty "
                      "savings, not \"profit\" — this is a cost-avoidance tool, not a revenue system.")
            return {"reply": reply, "chart": None, "stats": s}
        reply = (
            f"NEXA doesn't store \"profit\" — it's a cost-avoidance tool, so the closest metric is "
            f"FTA duty savings. For {period_label}: {_fmt_money(s['total'])} saved across "
            f"{s['count']} shipment(s). Mean {_fmt_money(s['mean'])} · Median {_fmt_money(s['median'])} · "
            f"Mode {_fmt_money(s['mode']) if s['mode'] is not None else 'n/a'} per shipment."
        )
        chart = {"type": "bar", "label": "FTA Savings (USD)",
                  "labels": [d["day"] for d in s["by_day"]],
                  "values": [d["value"] for d in s["by_day"]]}
        return {"reply": reply, "chart": chart, "stats": s}

    if wants_cost:
        s = cost_overview(supabase, period)
        if s["count"] == 0:
            reply = f"No landed-cost records found for {period_label}."
            return {"reply": reply, "chart": None, "stats": s}
        reply = (
            f"Total landed cost for {period_label}: {_fmt_money(s['total'])} across {s['count']} "
            f"shipment(s). Mean {_fmt_money(s['mean'])} · Median {_fmt_money(s['median'])} · "
            f"Mode {_fmt_money(s['mode']) if s['mode'] is not None else 'n/a'} per shipment."
        )
        chart = {"type": "bar", "label": "Landed Cost (USD)",
                  "labels": [d["day"] for d in s["by_day"]],
                  "values": [d["value"] for d in s["by_day"]]}
        return {"reply": reply, "chart": chart, "stats": s}

    return {
        "reply": (
            "I can answer questions about FTA duty savings or landed cost — try \"what's our "
            "savings today\", \"show cost this month\", or \"what's the average savings per "
            "shipment\". NEXA doesn't track \"profit\" directly since it's a cost-avoidance tool, "
            "not a revenue P&L."
        ),
        "chart": None,
        "stats": None,
    }
