from mem0 import MemoryClient
from config import MEM0_API_KEY, USER_ID

client = MemoryClient(api_key=MEM0_API_KEY)

def store_memory(messages: list, user_id: str = USER_ID):
    """Extract and store memories from a conversation turn."""
    client.add(messages, user_id=user_id)

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

def search_memory_list(query: str, limit: int = 5) -> list:
    """Retrieve relevant memories as a list of strings."""
    results = client.search(query, user_id=USER_ID, limit=limit)
    if not results:
        return []
    return [r["memory"] for r in results]

def get_recent_memories(limit: int = 3) -> list:
    """Get the most recent memories."""
    all_memories = client.get_all(user_id=USER_ID)
    if not all_memories:
        return []
    return [m["memory"] for m in all_memories[-limit:]]
