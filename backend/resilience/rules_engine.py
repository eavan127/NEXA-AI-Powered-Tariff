"""
rules_engine.py — deterministic local HS-code classifier.

Fallback path used when the AI pipeline (Ollama + pgvector RAG) is
unavailable or untrusted (system in degraded mode, or the inbound text
failed the prompt-injection guard). Covers the product categories present
in NEXA's seed data. Unlike the AI path, this NEVER auto-passes — every
match is flagged for mandatory analyst review, because a keyword match is
a much weaker signal than embedding similarity + LLM reasoning.
"""

# (keywords, hs_code, human label) — checked in order, first match wins
RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("printed circuit board", "pcb"),
     "8534.00", "Printed Circuit Board"),
    (("aluminium alloy", "aluminum alloy", "extruded bar", "extruded profile"),
     "7604.29", "Aluminium Alloy Extruded Bar/Profile"),
    (("spindle motor", "dc electric motor", "dc motor"),
     "8501.10", "DC Electric Motor"),
    (("integrated circuit", "memory chip", "microcontroller", "mcu",
      "dram", "nand flash", "nor flash", "fpga", "soc application processor",
      "dsp", "pmic"),
     "8542.31", "Electronic Integrated Circuit"),
    (("optical lens", "optical filter", "optical prism", "camera lens",
      "telecentric", "collimat", "objective camera"),
     "9001.90", "Optical Lens / Element"),
]

FALLBACK_CONFIDENCE = 60.0  # always below the 85% auto-pass threshold


def classify_local(product_description: str) -> dict:
    """Keyword match against the local ruleset. Always returns
    module_a_status='flagged_low_confidence' territory (confidence capped
    below the auto-pass threshold) — a human must verify."""
    text = (product_description or "").lower()

    for keywords, hs_code, label in RULES:
        if any(k in text for k in keywords):
            return {
                "hs_code":    hs_code,
                "confidence": FALLBACK_CONFIDENCE,
                "method":     "local_rules_engine",
                "matched_label": label,
                "reasoning_text": (
                    f"[LOCAL RULES ENGINE] Matched keyword rule for '{label}' "
                    f"→ HS {hs_code}. AI pipeline unavailable — flagged for "
                    f"mandatory analyst verification."
                ),
            }

    return {
        "hs_code":    None,
        "confidence": 0.0,
        "method":     "local_rules_engine",
        "matched_label": None,
        "reasoning_text": (
            "[LOCAL RULES ENGINE] No keyword rule matched this description. "
            "AI pipeline unavailable — requires manual classification."
        ),
    }
