"""
degraded_mode.py — system-wide circuit breaker.

When a regulatory data source is unreachable (or a prompt-injection attempt
is detected on inbound classification text), the system trips into
"degraded mode": SAP write-backs are frozen, AI classification falls back
to the deterministic local rules engine, and a high-priority alert is
raised for the Compliance Manager. Recovery is explicit — a manager (or
the retry job) must resolve the incident; nothing silently un-freezes.
"""
from datetime import datetime, timezone

_CONFIG_KEY = "degraded_mode"


def is_degraded(supabase) -> bool:
    row = supabase.table("config").select("value").eq("key", _CONFIG_KEY).execute()
    return bool(row.data) and row.data[0]["value"] == "true"


def trip_degraded_mode(supabase, source: str, alert_type: str, message: str, detail: dict | None = None) -> None:
    """Flip the breaker and raise an alert. Idempotent — re-tripping while
    already degraded just logs another alert (e.g. repeated injection attempts)
    without clearing/overwriting the original incident."""
    supabase.table("config").upsert({"key": _CONFIG_KEY, "value": "true"}).execute()
    supabase.table("system_alerts").insert({
        "severity":    "high",
        "source":      source,
        "alert_type":  alert_type,
        "message":     message,
        "detail":      detail or {},
        "status":      "active",
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }).execute()
    print(f"[degraded_mode] TRIPPED — source={source} type={alert_type}: {message}")


def resolve_degraded_mode(supabase, resolved_by: str, note: str = "") -> None:
    """Clear the breaker and resolve all active alerts. Explicit action only —
    no auto-clear without a human (or a verified successful retry) calling this."""
    supabase.table("config").upsert({"key": _CONFIG_KEY, "value": "false"}).execute()
    supabase.table("system_alerts").update({
        "status":      "resolved",
        "resolved_by": resolved_by,
        "resolved_note": note,
    }).eq("status", "active").execute()
    print(f"[degraded_mode] RESOLVED by {resolved_by}: {note}")


def get_active_alerts(supabase) -> list[dict]:
    res = supabase.table("system_alerts").select("*") \
        .eq("status", "active").order("created_at", desc=True).execute()
    return res.data or []
