import httpx
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_supabase_client

def embed_text(text: str) -> list:
    """Call Ollama to convert text into 768 numbers"""
    response = httpx.post(
        "http://localhost:11434/api/embeddings",
        json={
            "model": "nomic-embed-text",
            "prompt": text
        },
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()["embedding"]


def embed_all_hs_references():
    supabase = get_supabase_client()

    # Step 1 — Get all rows from hs_reference
    print("Fetching HS reference rows...")

    result = supabase.table("hs_reference") \
    .select("*") \
    .is_("embedding", "null") \
    .execute()

    rows = result.data
    print(f"Found {len(rows)} rows to embed")

    # Step 2 — For each row, generate embedding and update
    for i, row in enumerate(rows):
        hs_code = row["hs_code"]
        description = row["description"]
        notes = row.get("explanatory_notes", "")

        # Combine description + notes for richer embedding
        text_to_embed = f"{hs_code} {description} {notes}"

        text_to_embed = f"""
        HS Code: {hs_code}
        Category: {description}
        Details: {notes}
        Keywords: {description} {notes}
        Related products: {description}
        """.strip()

        print(f"[{i+1}/{len(rows)}] Embedding HS {hs_code}...")

        try:
            embedding = embed_text(text_to_embed)

            # Update this row with the embedding
            supabase.table("hs_reference") \
                .update({"embedding": embedding}) \
                .eq("id", row["id"]) \
                .execute()

            print(f"Done — {hs_code}")

        except Exception as e:
            print(f"Failed — {hs_code}: {e}")

    print("\nAll embeddings complete!")


if __name__ == "__main__":
    embed_all_hs_references()