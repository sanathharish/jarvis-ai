import asyncio
import json
import logging
import time
from typing import Any, Dict

import groq

from agents.registry import BaseAgent, AgentResult
from config import GROQ_API_KEY, FAST_MODEL, CONTEXT_LLM_TIMEOUT_S

logger = logging.getLogger(__name__)

groq_client = groq.Groq(api_key=GROQ_API_KEY)


SYSTEM_PROMPT = (
    "Classify the user message and return JSON only with keys: "
    "intent, needs_tools, complexity, entities, suggested_model. "
    "intent must be one of [greeting, question_factual, question_reasoning, "
    "task_request, weather_query, memory_query, search_needed, casual_chat, followup]. "
    "needs_tools is a list from [web_search, weather, memory]. "
    "complexity is simple or complex. suggested_model is groq or gemini."
)


class ContextAgent(BaseAgent):
    name = "context"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        user_message = context.get("user_message", "")
        start = time.perf_counter()
        status = "ok"

        def _call_llm() -> str:
            response = groq_client.chat.completions.create(
                model=FAST_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=200,
                temperature=0.1,
            )
            return response.choices[0].message.content or ""

        try:
            raw = await asyncio.wait_for(asyncio.to_thread(_call_llm), timeout=CONTEXT_LLM_TIMEOUT_S)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                start_idx = raw.find("{")
                end_idx = raw.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    data = json.loads(raw[start_idx : end_idx + 1])
                else:
                    raise
        except Exception as exc:
            logger.warning("context_agent error: %s", exc)
            status = "error"
            error_msg = str(exc)
            data = {
                "intent": "casual_chat",
                "needs_tools": [],
                "complexity": "simple",
                "entities": [],
                "suggested_model": "groq",
                "_error": error_msg,
            }

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
        return AgentResult(
            agent_name=self.name,
            data=data,
            error=None if status == "ok" else data.get("_error", "context_classification_failed"),
            latency_ms=0,
        )
