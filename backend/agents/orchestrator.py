import asyncio
import logging
import json
from typing import Any, Dict, List, Tuple

from agents.registry import registry, AgentResult
from agents.memory_agent import MemoryAgent
from agents.context_agent import ContextAgent
from agents.search_agent import SearchAgent
from agents.weather_agent import WeatherAgent
from agents.summarization_agent import SummarizationAgent
from agents.chat_agent import ChatAgent
from agents.memory_writer_agent import MemoryWriterAgent
from config import AGENT_TIMEOUT_PREFLIGHT, AGENT_TIMEOUT_TOOLS, AGENT_TIMEOUT_SUMMARY, USER_ID

logger = logging.getLogger(__name__)


def _result_map(results: List[AgentResult]) -> Dict[str, AgentResult]:
    return {r.agent_name: r for r in results}


class JarvisOrchestrator:
    def __init__(self) -> None:
        registry.register(MemoryAgent())
        registry.register(ContextAgent())
        registry.register(SearchAgent())
        registry.register(WeatherAgent())
        registry.register(SummarizationAgent())
        registry.register(ChatAgent())
        registry.register(MemoryWriterAgent())

    async def process(self, user_message: str, conversation_history: List[Dict[str, str]], stream_callback=None) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, str]]]:
        trace: List[Dict[str, Any]] = []

        # Phase 1: preflight
        preflight_results = await registry.run_parallel(
            ["memory", "context"],
            {"user_message": user_message, "conversation_history": conversation_history, "user_id": USER_ID},
            timeout_s=AGENT_TIMEOUT_PREFLIGHT,
        )
        preflight_map = _result_map(preflight_results)

        for name in ["memory", "context"]:
            res = preflight_map.get(name)
            trace.append({"agent": name, "duration_ms": res.latency_ms if res else 0, "status": "error" if res and res.error else "ok", "skipped": False})

        memory_context = (preflight_map.get("memory") or AgentResult("memory")).data or {}
        context_data = (preflight_map.get("context") or AgentResult("context")).data or {}

        # Phase 2: conditional agents
        needs_tools = context_data.get("needs_tools", []) or []
        intent = context_data.get("intent", "casual_chat")
        entities = context_data.get("entities", []) or []
        suggested_model = context_data.get("suggested_model", "groq")
        if intent in {"greeting", "casual_chat"} or context_data.get("complexity") == "simple":
            suggested_model = "groq"

        phase2_agents = []
        if "web_search" in needs_tools or intent == "search_needed":
            phase2_agents.append("search")
        if "weather" in needs_tools or intent == "weather_query":
            phase2_agents.append("weather")

        phase2_results = []
        if phase2_agents:
            phase2_results = await registry.run_parallel(
                phase2_agents,
                {"user_message": user_message, "entities": entities, "memory_context": memory_context.get("formatted", "")},
                timeout_s=AGENT_TIMEOUT_TOOLS,
            )

        phase2_map = _result_map(phase2_results)
        for name in ["search", "weather"]:
            if name in phase2_map:
                res = phase2_map[name]
                trace.append({"agent": name, "duration_ms": res.latency_ms, "status": "error" if res.error else "ok", "skipped": False})
            else:
                trace.append({"agent": name, "duration_ms": 0, "status": "skipped", "skipped": True})

        # Phase 3: summarization
        if len(conversation_history) > 16:
            summary_result = await registry.run_agent("summarizer", {"conversation_history": conversation_history, "max_turns": 16}, timeout_s=AGENT_TIMEOUT_SUMMARY)
            trace.append({"agent": "summarizer", "duration_ms": summary_result.latency_ms, "status": "error" if summary_result.error else "ok", "skipped": False})
            conversation_history = summary_result.data.get("new_history", conversation_history)
        else:
            trace.append({"agent": "summarizer", "duration_ms": 0, "status": "skipped", "skipped": True})

        # Phase 4: chat synthesis
        search_context = (phase2_map.get("search") or AgentResult("search")).data or {}
        weather_context = (phase2_map.get("weather") or AgentResult("weather")).data or {}

        weather_context_str = ""
        if weather_context.get("summary"):
            weather_context_str = f"Weather context for {weather_context.get('city', '')}: {weather_context.get('summary')} {weather_context.get('recommendation', '')}"

        chat_result = await registry.run_agent(
            "chat",
            {
                "user_message": user_message,
                "conversation_history": conversation_history,
                "model": suggested_model,
                "memory_context": memory_context.get("formatted", ""),
                "search_context": search_context.get("formatted", ""),
                "weather_context": weather_context_str,
                "intent": intent,
                "stream_callback": stream_callback,
            },
        )

        trace.append({"agent": "chat", "duration_ms": chat_result.latency_ms, "status": "error" if chat_result.error else "ok", "skipped": False})

        if chat_result.error and suggested_model == "gemini":
            fallback_result = await registry.run_agent(
                "chat",
                {
                    "user_message": user_message,
                    "conversation_history": conversation_history,
                    "model": "groq",
                    "memory_context": memory_context.get("formatted", ""),
                    "search_context": search_context.get("formatted", ""),
                    "weather_context": weather_context_str,
                    "intent": intent,
                    "stream_callback": stream_callback,
                },
            )
            trace.append({"agent": "chat_fallback", "duration_ms": fallback_result.latency_ms, "status": "error" if fallback_result.error else "ok", "skipped": False})
            if fallback_result.data:
                chat_result = fallback_result

        full_response = ""
        if chat_result.data:
            full_response = chat_result.data.get("full_response", "")

        # Phase 5: memory writer (fire-and-forget)
        asyncio.create_task(
            registry.run_agent(
                "memory_writer",
                {
                    "user_message": user_message,
                    "assistant_response": full_response,
                    "conversation_history": conversation_history,
                    "user_id": USER_ID,
                },
            )
        )

        for item in trace:
            logger.info("trace agent=%s status=%s duration_ms=%s", item["agent"], item["status"], item["duration_ms"])

        logger.info(
            "agent_trace_json=%s",
            json.dumps(
                {
                    "event": "agent_trace",
                    "trace": trace,
                    "intent": intent,
                    "model": suggested_model,
                }
            ),
        )

        return full_response, trace, conversation_history


from typing import Optional

_orchestrator: Optional[JarvisOrchestrator] = None


def get_orchestrator() -> JarvisOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = JarvisOrchestrator()
    return _orchestrator
