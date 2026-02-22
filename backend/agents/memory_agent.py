import asyncio
import logging
import time
from typing import Dict, Any, List

from agents.registry import BaseAgent, AgentResult
from memory.mem0_client import search_memory_list, get_recent_memories
from config import AGENT_TIMEOUT_PREFLIGHT

logger = logging.getLogger(__name__)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _cap_tokens(items: List[str], max_tokens: int = 800) -> List[str]:
    # Approximate: 1 token ~= 1 word
    count = 0
    capped = []
    for item in items:
        words = item.split()
        if count + len(words) > max_tokens:
            break
        capped.append(item)
        count += len(words)
    return capped


class MemoryAgent(BaseAgent):
    name = "memory"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        user_message = context.get("user_message", "")
        start = time.perf_counter()
        status = "ok"
        try:
            relevant_task = asyncio.wait_for(
                asyncio.to_thread(search_memory_list, user_message, 5),
                timeout=AGENT_TIMEOUT_PREFLIGHT,
            )
            recent_task = asyncio.wait_for(
                asyncio.to_thread(get_recent_memories, 3),
                timeout=AGENT_TIMEOUT_PREFLIGHT,
            )
            relevant, recent = await asyncio.gather(relevant_task, recent_task, return_exceptions=True)

            if isinstance(relevant, Exception):
                relevant = []
            if isinstance(recent, Exception):
                recent = []

            relevant = _dedupe(relevant or [])
            recent = _dedupe(recent or [])
            all_memories = _cap_tokens(_dedupe(relevant + recent), max_tokens=800)

            formatted = ""
            if all_memories:
                formatted = "User memory context:\n" + "\n".join(f"- {m}" for m in all_memories)

            result = AgentResult(
                agent_name=self.name,
                data={
                    "relevant_memories": relevant,
                    "recent_memories": recent,
                    "formatted": formatted,
                },
                error=None,
                latency_ms=0,
            )
        except Exception as exc:
            logger.warning("memory_agent error: %s", exc)
            status = "error"
            result = AgentResult(
                agent_name=self.name,
                data={"relevant_memories": [], "recent_memories": [], "formatted": ""},
                error=str(exc),
                latency_ms=0,
            )

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
        return result
