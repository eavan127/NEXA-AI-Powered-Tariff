"""
training_data.py — auto-generates HS-classification training examples
whenever an analyst overrides Module A's AI prediction.

Every override is a free, ground-truth-labeled signal: "the AI predicted
X, a human said the correct answer is Y." Each one inserts one canonical
row into `training_examples`, then asks qwen2.5:1.5b (via LangChain) to
paraphrase the product description 2 more ways — the same item described
the way a different SAP entry might phrase it — enriching the few-shot
set the local rules engine / future fine-tuning could draw on. Paraphrase
generation is best-effort: any failure just skips augmentation, never
blocks the override itself.
"""
import json
import re

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import settings

_QWEN_MODEL = "qwen2.5:1.5b"
_AUGMENT_COUNT = 2

_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You generate alternative phrasings for trade-compliance training data. "
     "Given a product description, write {n} alternative descriptions of the "
     "SAME physical product, the way a different SAP entry or supplier "
     "invoice might phrase it (different word order, synonyms, more/less "
     "detail) — but it must still clearly be the same item. "
     "Respond with JSON ONLY: a JSON array of {n} strings, nothing else."),
    ("human", "{description}"),
])

_chain = _PROMPT | ChatOllama(model=_QWEN_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0.6) | StrOutputParser()
_ARRAY_RE = re.compile(r"\[.*?\]", re.DOTALL)


def _generate_paraphrases(description: str, n: int = _AUGMENT_COUNT) -> list:
    try:
        raw = _chain.invoke({"description": description, "n": n})
        match = _ARRAY_RE.search(raw)
        if not match:
            return []
        parsed = json.loads(match.group())
        return [p.strip() for p in parsed if isinstance(p, str) and p.strip()][:n]
    except Exception:
        return []


def generate_training_examples(
    supabase,
    shipment_uuid: str,
    product_description: str,
    ai_hs_code: str,
    ai_confidence,
    corrected_hs_code: str,
    correction_reason: str,
    analyst_id: str,
) -> dict:
    """Inserts the canonical override example, then best-effort augments
    it with qwen-generated paraphrases. Never raises — a failure here
    must not block the override it's recording."""
    try:
        canonical = supabase.table("training_examples").insert({
            "shipment_id":         shipment_uuid,
            "product_description": product_description,
            "ai_hs_code":          ai_hs_code,
            "ai_confidence":       ai_confidence,
            "corrected_hs_code":   corrected_hs_code,
            "correction_reason":   correction_reason,
            "is_augmented":        False,
            "analyst_id":          analyst_id,
        }).execute()
        canonical_id = canonical.data[0]["id"] if canonical.data else None
    except Exception as e:
        print(f"[training_data] Failed to insert canonical example: {e}")
        return {"canonical": False, "augmented": 0}

    paraphrases = _generate_paraphrases(product_description)
    augmented_count = 0
    for text in paraphrases:
        try:
            supabase.table("training_examples").insert({
                "shipment_id":         shipment_uuid,
                "product_description": text,
                "ai_hs_code":          ai_hs_code,
                "ai_confidence":       ai_confidence,
                "corrected_hs_code":   corrected_hs_code,
                "correction_reason":   correction_reason,
                "is_augmented":        True,
                "source_example_id":   canonical_id,
                "analyst_id":          analyst_id,
            }).execute()
            augmented_count += 1
        except Exception:
            continue

    print(f"[training_data] {shipment_uuid}: 1 canonical + {augmented_count} qwen-paraphrased example(s) "
          f"for HS {corrected_hs_code}")
    return {"canonical": True, "augmented": augmented_count}
