import hashlib
import httpx
from datetime import datetime, timezone
from supabase import Client


async def has_source_changed(url: str, supabase: Client) -> tuple[bool, str]:
    """
    Check if a source URL has changed since the last pipeline run.

    Strategy (cheapest to most expensive):
      1. HEAD request → use ETag or Last-Modified header as the fingerprint
      2. If no useful headers → full GET → MD5 hash of content body

    Returns: (changed: bool, new_hash: str)
    On network error: returns (True, "") so we never silently skip a source.
    """
    config_key = f"hash_{hashlib.md5(url.encode()).hexdigest()}"
    new_hash = ""
    method_used = "MD5"

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            head = await client.head(url)
            etag = head.headers.get("etag", "").strip()
            last_mod = head.headers.get("last-modified", "").strip()

            if etag:
                new_hash = etag
                method_used = "ETag"
            elif last_mod:
                new_hash = last_mod
                method_used = "Last-Modified"
            else:
                # No cache headers — fetch full body and hash it
                get_resp = await client.get(url)
                new_hash = hashlib.md5(get_resp.content).hexdigest()
                method_used = "MD5"

        stored = supabase.table("config").select("value").eq("key", config_key).execute()
        old_hash = stored.data[0]["value"] if stored.data else None

        changed = (old_hash is None) or (old_hash != new_hash)
        _log_hash_check(url, old_hash, new_hash, changed, method_used, supabase)
        return changed, new_hash

    except Exception as e:
        print(f"[change_detector] Error checking {url}: {e}")
        return True, ""


def store_source_hash(url: str, new_hash: str, supabase: Client) -> None:
    """Persist the hash after successfully processing a source."""
    if not new_hash:
        return
    config_key = f"hash_{hashlib.md5(url.encode()).hexdigest()}"
    supabase.table("config").upsert({"key": config_key, "value": new_hash}).execute()


def _log_hash_check(
    url: str,
    old_hash,
    new_hash: str,
    changed: bool,
    method: str,
    supabase: Client,
) -> None:
    if changed:
        desc = "Source CHANGED (hash mismatch) — downloading..."
        print(f"[change_detector] {desc} [{method}] {url}")
    else:
        desc = f"Source unchanged since last check ({old_hash}) — skipping download"
        print(f"[change_detector] {desc} [{method}] {url}")

    try:
        supabase.table("pipeline_logs").insert({
            "event_type":  "hash_check",
            "source_url":  url,
            "description": desc,
            "detail": {
                "old_hash": old_hash,
                "new_hash": new_hash,
                "method":   method,
                "changed":  changed,
                "url":      url,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        # Non-fatal — logging failure must not break the pipeline
        print(f"[change_detector] pipeline_logs insert failed: {e}")
