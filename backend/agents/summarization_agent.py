import asyncio
import logging
import time
from typing import Any, Dict, List

import groq

from agents.registry import BaseAgent, AgentResult
from config import GROQ_API_KEY, FAST_MODEL

logger = logging.getLogger(__name__)

groq_client = groq.Groq(api_key=GROQ_API_KEY)


class SummarizationAgent(BaseAgent):
    name = "summarizer"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        history: List[Dict[str, str]] = context.get("conversation_history", [])
        max_turns = int(context.get("max_turns", 16))
        start = time.perf_counter()
        status = "ok"

        if len(history) <= max_turns:
            result = AgentResult(agent_name=self.name, data={"was_compressed": False, "new_history": history, "summary": ""}, error=None, latency_ms=0)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
            return result

        oldest = history[:8]
        rest = history[8:]
        content = "\n".join(f"{m['role']}: {m['content']}" for m in oldest)

        def _call_llm() -> str:
            response = groq_client.chat.completions.create(
                model=FAST_MODEL,
                messages=[
                    {"role": "system", "content": "Summarize the conversation into a single paragraph under 150 words. Start with 'Summary so far:'."},
                    {"role": "user", "content": content},
                ],
                max_tokens=180,
                temperature=0.2,
            )
            return response.choices[0].message.content or ""

        try:
            summary = await asyncio.to_thread(_call_llm)
            new_history = [{"role": "system", "content": summary}] + rest
            result = AgentResult(agent_name=self.name, data={"was_compressed": True, "new_history": new_history, "summary": summary}, error=None, latency_ms=0)
        except Exception as exc:
            logger.warning("summarization_agent error: %s", exc)
            status = "error"
            result = AgentResult(agent_name=self.name, data={"was_compressed": False, "new_history": history, "summary": ""}, error=str(exc), latency_ms=0)

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
        return result
