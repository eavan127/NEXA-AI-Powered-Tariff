"""
intent_router.py — LangChain-orchestrated intent classification via
qwen2.5:1.5b (Ollama), replacing keyword matching with actual question
understanding (handles paraphrasing and any of the 3 supported languages
without needing translated keyword lists).

Deliberately NOT a free-roaming LangChain agent: qwen2.5:1.5b is a 1.5B
model, and a multi-step autonomous tool-calling loop is unreliable at
that size — it can pick the wrong tool, malform output, or loop. Instead
this does exactly one structured-classification call, parsed defensively,
with a keyword-based fallback if Ollama is unreachable or returns
unparseable output. The actual data retrieval (the "tool") is plain
deterministic Python in chat_analytics.py — qwen only decides which one
to call and with what period, never computes a number itself.
"""
import json
import re

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import settings

_QWEN_MODEL = "qwen2.5:1.5b"

_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You classify questions for a tariff-compliance chatbot called NEXA. "
     "The question may be in English, Bahasa Malaysia, or Mandarin Chinese. "
     "Classify it and respond with JSON ONLY, no other text, in this exact shape:\n"
     '{{"intent": "savings" | "cost" | "forecast" | "other", '
     '"period": "today" | "week" | "month" | "all"}}\n\n'
     "intent meanings:\n"
     "- savings: asking about FTA duty savings, cost reduction, or (mistakenly) \"profit\"\n"
     "- cost: asking about landed cost, expenses, duty amount\n"
     "- forecast: asking to predict, forecast, project, or \"what if\" about future savings/trend\n"
     "- other: anything else, including greetings or unrelated questions\n\n"
     "period meanings: today / this week / this month / otherwise \"all\". "
     "Default to \"all\" if no timeframe is mentioned."),
    ("human", "{question}"),
])

_RESULT_RE = re.compile(r"\{.*?\}", re.DOTALL)
_ALLOWED_INTENTS = {"savings", "cost", "forecast", "other"}
_ALLOWED_PERIODS = {"today", "week", "month", "all"}

_chain = _PROMPT | ChatOllama(model=_QWEN_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0) | StrOutputParser()


def _keyword_fallback(text: str) -> dict:
    """Used only if Ollama is unreachable or returns unparseable JSON —
    same logic the chatbox used before this LangChain integration existed."""
    text = text.lower()
    if any(w in text for w in ("predict", "forecast", "projection", "what if", "next week", "next month", "trend", "future")):
        intent = "forecast"
    elif any(w in text for w in ("profit", "saving", "savings", "earn", "earning", "margin")):
        intent = "savings"
    elif any(w in text for w in ("cost", "expense", "spend", "spending", "landed cost", "duty")):
        intent = "cost"
    else:
        intent = "other"

    if "today" in text:
        period = "today"
    elif "week" in text:
        period = "week"
    elif "month" in text:
        period = "month"
    else:
        period = "all"

    return {"intent": intent, "period": period, "source": "keyword_fallback"}


def classify(message: str) -> dict:
    try:
        raw = _chain.invoke({"question": message})
        match = _RESULT_RE.search(raw)
        if not match:
            return _keyword_fallback(message)
        parsed = json.loads(match.group())
        intent = parsed.get("intent")
        period = parsed.get("period")
        if intent not in _ALLOWED_INTENTS or period not in _ALLOWED_PERIODS:
            return _keyword_fallback(message)
        return {"intent": intent, "period": period, "source": "qwen"}
    except Exception:
        return _keyword_fallback(message)
