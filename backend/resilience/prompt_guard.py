"""
prompt_guard.py — sanitizes text before it reaches the LLM and detects
prompt-injection attempts (e.g. hidden instructions smuggled inside a
supplier PDF's product description, per NEXA's threat model).

Two independent signals are treated as suspicious:
  1. Known injection phrasing ("ignore previous instructions", role-play
     hijacks, fake "system:" turns, etc.)
  2. Hidden/invisible unicode characters (zero-width spaces, bidi overrides,
     BOM) — a common way to smuggle text past a casual human reviewer
     while an LLM still parses it.
"""
import re

_INJECTION_PATTERNS = [
    r"ignore (all|any|the)?\s*(previous|above|prior)\s*instructions",
    r"disregard (all|any|the)?\s*(previous|above|prior)\s*instructions",
    r"you are now\b",
    r"\bsystem\s*:\s*",
    r"\bact as\b.{0,30}\b(admin|root|developer)\b",
    r"new instructions?:",
    r"\boverride\b.{0,20}\b(confidence|threshold|rule)\b",
]

# Zero-width spaces/joiners (U+200B-U+200F), bidi override controls
# (U+202A-U+202E), and the BOM (U+FEFF) — invisible to a human skimming
# the text but still parsed by an LLM.
_HIDDEN_CHAR_RANGES = "​-‏‪-‮﻿"
_HIDDEN_CHARS = re.compile(f"[{_HIDDEN_CHAR_RANGES}]")

MAX_LEN = 2000


def scan_for_injection(text: str) -> dict:
    text = text or ""
    matched = [p for p in _INJECTION_PATTERNS if re.search(p, text, re.IGNORECASE)]
    has_hidden_chars = bool(_HIDDEN_CHARS.search(text))

    cleaned = _HIDDEN_CHARS.sub("", text)[:MAX_LEN]

    return {
        "suspicious":         bool(matched) or has_hidden_chars,
        "patterns_matched":   matched,
        "hidden_chars_found": has_hidden_chars,
        "cleaned_text":       cleaned,
    }
