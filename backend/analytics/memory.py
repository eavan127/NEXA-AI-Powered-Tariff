"""
memory.py — LangChain chat memory backed by Supabase's REST API
(supabase-py), not a raw Postgres connection. The project only has
SUPABASE_URL/SUPABASE_KEY (the REST credentials) configured — LangChain's
built-in PostgresChatMessageHistory needs a separate direct DB connection
string that isn't available here, so this implements the same
BaseChatMessageHistory interface against the REST client instead.

Keyed by analyst_id, not a real session/login — see ANALYSTS dict in
api/routes.py. There is no authentication in this prototype, so this is
"whoever the UI says is logged in," not a verified identity.
"""
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

HISTORY_LIMIT = 50


class SupabaseChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, supabase, analyst_id: str, limit: int = HISTORY_LIMIT):
        self.supabase = supabase
        self.analyst_id = analyst_id
        self.limit = limit

    @property
    def messages(self) -> list[BaseMessage]:
        res = (
            self.supabase.table("chat_history")
            .select("role,content,created_at")
            .eq("analyst_id", self.analyst_id)
            .order("created_at", desc=True)
            .limit(self.limit)
            .execute()
        )
        rows = list(reversed(res.data or []))  # chronological order
        return [
            HumanMessage(content=r["content"]) if r["role"] == "human" else AIMessage(content=r["content"])
            for r in rows
        ]

    def add_messages(self, messages: list[BaseMessage]) -> None:
        rows = [
            {
                "analyst_id": self.analyst_id,
                "role": "human" if isinstance(m, HumanMessage) else "ai",
                "content": m.content,
            }
            for m in messages
        ]
        if rows:
            self.supabase.table("chat_history").insert(rows).execute()

    def clear(self) -> None:
        self.supabase.table("chat_history").delete().eq("analyst_id", self.analyst_id).execute()


def get_history(supabase, analyst_id: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    """Plain dict form for the chatbox UI to render on reopen — the
    LangChain message objects above are for feeding context back into
    qwen, not for the frontend."""
    res = (
        supabase.table("chat_history")
        .select("role,content,created_at")
        .eq("analyst_id", analyst_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data or []))
