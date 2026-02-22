import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from agents.registry import BaseAgent, AgentResult
from tools.search import async_web_search
from config import SEARCH_AGENT_TIMEOUT_S

logger = logging.getLogger(__name__)


def _build_queries(user_message: str, entities: List[str], query_override: Optional[str]) -> List[str]:
    if query_override:
        return [query_override]
    queries = [user_message]
    for ent in entities[:2]:
        if ent and ent.lower() not in user_message.lower():
            queries.append(f"{ent} {user_message}")
    return list(dict.fromkeys(queries))[:2]


def _trim_words(text: str, max_words: int = 200) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


class SearchAgent(BaseAgent):
    name = "search"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        user_message = context.get("user_message", "")
        entities = context.get("entities", []) or []
        query_override = context.get("query_override")
        start = time.perf_counter()
        status = "ok"

        queries = _build_queries(user_message, entities, query_override)

        async def _search(q: str) -> dict:
            return await asyncio.wait_for(async_web_search(q, max_results=5), timeout=SEARCH_AGENT_TIMEOUT_S)

        try:
            responses = await asyncio.gather(*[_search(q) for q in queries], return_exceptions=True)
            results = []
            for resp in responses:
                if isinstance(resp, Exception):
                    continue
                for r in resp.get("results", []):
                    results.append(
                        {
                            "title": r.get("title", "Untitled"),
                            "snippet": _trim_words(r.get("content", ""), 200),
                            "url": r.get("url", ""),
                        }
                    )

            results = results[:3]
            formatted = ""
            if results:
                formatted = "Web search context:\n" + "\n".join(
                    f"- {r['title']}: {r['snippet']} ({r['url']})" for r in results
                )

            result = AgentResult(agent_name=self.name, data={"results": results, "formatted": formatted}, error=None, latency_ms=0)
        except Exception as exc:
            logger.warning("search_agent error: %s", exc)
            status = "error"
            result = AgentResult(agent_name=self.name, data={"results": [], "formatted": ""}, error=str(exc), latency_ms=0)

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
        return result
