from mem0 import MemoryClient
from config import MEM0_API_KEY, USER_ID

client = MemoryClient(api_key=MEM0_API_KEY)

def store_memory(messages: list):
    """Extract and store memories from a conversation turn."""
    client.add(messages, user_id=USER_ID)

def search_memory(query: str) -> str:
    """Retrieve relevant memories for a query."""
    results = client.search(query, user_id=USER_ID, limit=5)
    if not results:
        return ""
    memories = [r["memory"] for r in results]
    return "Relevant things I remember about you:\n" + "\n".join(f"- {m}" for m in memories)

def get_all_memories() -> list:
    """Get all stored memories."""
    return client.get_all(user_id=USER_ID)