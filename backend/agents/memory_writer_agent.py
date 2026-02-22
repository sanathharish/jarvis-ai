import asyncio
import json
import logging
import time
from typing import Any, Dict

import groq

from agents.registry import BaseAgent, AgentResult
from config import GROQ_API_KEY, FAST_MODEL, USER_ID
from memory.mem0_client import store_memory

logger = logging.getLogger(__name__)

groq_client = groq.Groq(api_key=GROQ_API_KEY)


class MemoryWriterAgent(BaseAgent):
    name = "memory_writer"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        user_message = context.get("user_message", "")
        assistant_response = context.get("assistant_response", "")
        conversation_history = context.get("conversation_history", [])
        user_id = context.get("user_id", USER_ID)
        start = time.perf_counter()
        status = "ok"

        prompt = (
            "Extract only meaningful user facts or preferences to remember. "
            "Return JSON: {\"store\": true|false, \"memory\": \"...\"}. "
            "Do NOT store questions, greetings, or chit-chat."
        )

        def _call_llm() -> str:
            response = groq_client.chat.completions.create(
                model=FAST_MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"User: {user_message}\nAssistant: {assistant_response}"},
                ],
                max_tokens=120,
                temperature=0.1,
            )
            return response.choices[0].message.content or ""

        try:
            raw = await asyncio.to_thread(_call_llm)
            data = json.loads(raw)
            should_store = bool(data.get("store"))
            memory_text = (data.get("memory") or "").strip()

            if should_store and memory_text:
                await asyncio.to_thread(store_memory, [{"role": "user", "content": memory_text}], user_id)
                result = AgentResult(agent_name=self.name, data={"stored": True, "memory_summary": memory_text}, error=None, latency_ms=0)
                latency_ms = int((time.perf_counter() - start) * 1000)
                logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
                return result

            result = AgentResult(agent_name=self.name, data={"stored": False, "memory_summary": ""}, error=None, latency_ms=0)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
            return result
        except Exception as exc:
            logger.warning("memory_writer_agent error: %s", exc)
            status = "error"
            result = AgentResult(agent_name=self.name, data={"stored": False, "memory_summary": ""}, error=str(exc), latency_ms=0)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
            return result
