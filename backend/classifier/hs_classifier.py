import httpx # Makes HTTP requests to Ollama
import json
from supabase import Client


# ─────────────────────────────────────────
# STEP 1: Get shipment from database
# ─────────────────────────────────────────
def get_shipment_description(shipment_id: str, supabase: Client) -> dict:
    result = supabase.table("shipments") \
        .select("*") \
        .eq("sap_shipment_id", shipment_id) \
        .single() \
        .execute()

    if not result.data:
        raise ValueError(f"Shipment {shipment_id} not found")

    shipment = result.data

    e2open_hs_code = None
    if shipment.get("bom_items"):
        bom = shipment["bom_items"]
        if isinstance(bom, list) and len(bom) > 0:
            e2open_hs_code = bom[0].get("hs_code")

    return {
        "shipment_id": shipment["id"],        # ← real UUID now
        "sap_shipment_id": shipment_id,       # ← keep original for reference
        "product_description": shipment["product_description"],
        "e2open_hs_code": e2open_hs_code
    }


# ─────────────────────────────────────────
# STEP 2: Embed the description
# ─────────────────────────────────────────
def embed_description(product_description: str) -> list:
    response = httpx.post(
        "http://localhost:11434/api/embeddings",
        json={
            "model": "nomic-embed-text",
            "prompt": product_description
        },
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()["embedding"]


# ─────────────────────────────────────────
# STEP 3: Search hs_reference with pgvector
def search_hs_reference(embedding: list, supabase: Client) -> list:
    import math
    
    # Fetch all hs_reference rows
    result = supabase.table("hs_reference") \
        .select("id, hs_code, description, explanatory_notes, embedding") \
        .not_.is_("embedding", "null") \
        .execute()
    
    if not result.data:
        raise ValueError("No HS reference data found")
    
    def cosine_similarity(vec1: list, vec2) -> float:
        # vec2 comes as string from database — convert it
        if isinstance(vec2, str):
            vec2 = [float(x) for x in vec2.strip("[]").split(",")]
        
        dot = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)
    
    # Score every row
    scored = []
    for row in result.data:
        sim = cosine_similarity(embedding, row["embedding"])
        scored.append({
            "id": row["id"],
            "hs_code": row["hs_code"],
            "description": row["description"],
            "explanatory_notes": row["explanatory_notes"],
            "similarity": sim
        })
    
    # Sort and return top 3
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    top_3 = scored[:3]
    
    print(f"[Step 3] Top match: {top_3[0]['hs_code']} "
          f"({round(top_3[0]['similarity']*100,1)}%)")
    
    return top_3

# ─────────────────────────────────────────
# STEP 4: Ask llama3.2 to pick best HS code
# ─────────────────────────────────────────
def ask_llama_for_classification(
    product_description: str,
    top_3_matches: list,
    e2open_hs_code: str
) -> dict:

    # Build candidates text
    candidates_text = ""
    for i, match in enumerate(top_3_matches, 1):
        candidates_text += f"""
Candidate {i}:
  HS Code: {match['hs_code']}
  Description: {match['description']}
  Explanatory Notes: {match.get('explanatory_notes', 'N/A')}
  Similarity Score: {round(match['similarity'] * 100, 1)}%
"""

    prompt = f"""You are a trade compliance expert specializing in 
HS (Harmonized System) code classification.

PRODUCT DESCRIPTION FROM SAP:
"{product_description}"

E2OPEN PRELIMINARY HS CODE: {e2open_hs_code or 'Not provided'}

TOP 3 CANDIDATE HS CODES FROM REFERENCE DATABASE:
{candidates_text}

YOUR TASK:
1. Analyze the product description carefully
2. Compare against the 3 candidate HS codes
3. Select the most accurate HS code
4. Give a confidence score from 0 to 100
5. Explain your reasoning clearly

RESPOND IN THIS EXACT JSON FORMAT (no other text):
{{
  "ai_hs_code": "XXXX.XX.XX",
  "confidence_score": 85,
  "reasoning_text": "Your explanation here",
  "alternative_codes": [
    {{"hs_code": "XXXX.XX", "confidence": 10, "reason": "why rejected"}},
    {{"hs_code": "XXXX.XX", "confidence": 5, "reason": "why rejected"}}
  ]
}}"""

    response = httpx.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2:latest",
            "prompt": prompt,
            "stream": False
        },
        timeout=180.0
    )

    response.raise_for_status()
    raw_response = response.json()["response"]

    # Clean response in case llama adds extra text
    raw_response = raw_response.strip()
    if "```json" in raw_response:
        raw_response = raw_response.split("```json")[1].split("```")[0]
    elif "```" in raw_response:
        raw_response = raw_response.split("```")[1].split("```")[0]

    return json.loads(raw_response)


# ─────────────────────────────────────────
# STEP 5: Write result to hs_classifications
# ─────────────────────────────────────────
def write_classification_result(
    shipment_id: str,
    e2open_hs_code: str,
    llama_result: dict,
    top_3_matches: list,
    supabase: Client
) -> dict:

    confidence = llama_result["confidence_score"]
    ai_hs_code = llama_result["ai_hs_code"]

    # Apply 85% threshold rule
    if confidence >= 85:
        module_a_status = "auto_passed"
    else:
        module_a_status = "flagged_low_confidence"

    record = {
        "shipment_id": shipment_id,
        "e2open_hs_code": e2open_hs_code,
        "ai_hs_code": ai_hs_code,
        "confidence_score": confidence,
        "reasoning_text": llama_result["reasoning_text"],
        "rag_sources": top_3_matches,
        "final_hs_code": ai_hs_code,
        "module_a_status": module_a_status
    }

    result = supabase.table("hs_classifications") \
        .insert(record) \
        .execute()

    return result.data[0]


# ─────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────
def classify_hs_code(shipment_id: str, supabase: Client) -> dict:

    print(f"\n[Module A] Starting: {shipment_id}")

    print("[Module A] Step 1 — Fetching shipment...")
    shipment_data = get_shipment_description(shipment_id, supabase)
    product_description = shipment_data["product_description"]
    e2open_hs_code = shipment_data["e2open_hs_code"]
    real_uuid = shipment_data["shipment_id"]
    print(f"[Module A] Description: {product_description}")

    print("[Module A] Step 2 — Embedding description...")
    embedding = embed_description(product_description)
    print(f"[Module A] Embedding done ({len(embedding)} dimensions)")

    print("[Module A] Step 3 — Searching hs_reference...")
    top_3_matches = search_hs_reference(embedding, supabase)
    print(f"[Module A] Top match: {top_3_matches[0]['hs_code']} "
          f"({round(top_3_matches[0]['similarity']*100,1)}%)")

    print("[Module A] Step 4 — Asking qwen2.5:1.5b...")
    llama_result = ask_llama_for_classification(
        product_description,
        top_3_matches,
        e2open_hs_code
    )
    print(f"[Module A] Decision: {llama_result['ai_hs_code']} "
          f"({llama_result['confidence_score']}% confidence)")

    print("[Module A] Step 5 — Writing to hs_classifications...")
    final_record = write_classification_result(
        real_uuid,
        e2open_hs_code,
        llama_result,
        top_3_matches,
        supabase
    )

    print(f"[Module A] Done — Status: {final_record['module_a_status']}")
    return final_record