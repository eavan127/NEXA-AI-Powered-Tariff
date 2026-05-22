import sys
import os
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import get_supabase_client

def test_rpc():
    supabase = get_supabase_client()
    
    # Get a real embedding from hs_reference
    result = supabase.table("hs_reference") \
        .select("hs_code, embedding") \
        .eq("hs_code", "8534.00") \
        .single() \
        .execute()
    
    embedding = result.data["embedding"]
    print(f"Embedding type: {type(embedding)}")
    
    # Embedding comes back as STRING — use it directly
    # No need to convert — just pass the string as is
    print(f"Embedding sample: {str(embedding)[:50]}")
    
    rpc_result = supabase.rpc(
        "match_hs_reference",
        {
            "query_embedding": embedding,  # pass string directly
            "match_count": 3
        }
    ).execute()
    
    print(f"RPC result: {rpc_result.data}")

if __name__ == "__main__":
    test_rpc()