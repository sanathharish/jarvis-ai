from memory.mem0_client import search_memory, get_all_memories

def recall_memory(query: str) -> str:
    return search_memory(query)

def list_memories() -> str:
    memories = get_all_memories()
    if not memories:
        return "I don't have any memories stored yet."
    return "\n".join(f"- {m['memory']}" for m in memories[:20])