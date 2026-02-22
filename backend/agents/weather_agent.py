import logging
import re
import time
from typing import Any, Dict, List, Optional

from agents.registry import BaseAgent, AgentResult
from tools.weather import async_get_weather

logger = logging.getLogger(__name__)


def _extract_city(entities: List[str], user_message: str, memory_context: str = "") -> Optional[str]:
    for ent in entities:
        if ent:
            return ent
    match = re.search(r"weather in ([A-Za-z\\s]+)", user_message, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if memory_context:
        match = re.search(r"Location:\\s*([A-Za-z\\s]+)", memory_context)
        if match:
            return match.group(1).strip()
    return None


def _summarize(temp_c: float, description: str) -> str:
    if temp_c <= 5:
        feel = "freezing"
    elif temp_c <= 12:
        feel = "cold"
    elif temp_c <= 20:
        feel = "cool"
    elif temp_c <= 28:
        feel = "pleasant"
    else:
        feel = "hot"
    return f"It feels {feel} with {description}."


def _recommendation(description: str) -> str:
    desc = description.lower()
    if "rain" in desc or "storm" in desc:
        return "Umbrella advised."
    if "snow" in desc:
        return "Bundle up and watch for slick roads."
    if "clear" in desc:
        return "Great time for a walk outside."
    return "Dress comfortably for the conditions."


class WeatherAgent(BaseAgent):
    name = "weather"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        entities = context.get("entities", []) or []
        user_message = context.get("user_message", "")
        memory_context = context.get("memory_context", "")
        start = time.perf_counter()
        status = "ok"

        city = _extract_city(entities, user_message, memory_context)
        if not city:
            status = "error"
            result = AgentResult(agent_name=self.name, data={"city": "", "raw": {}, "summary": "", "recommendation": ""}, error="no_city", latency_ms=0)
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
            return result

        try:
            raw = await async_get_weather(city)
            description = raw["weather"][0]["description"]
            temp_c = float(raw["main"]["temp"])
            summary = _summarize(temp_c, description)
            rec = _recommendation(description)
            result = AgentResult(
                agent_name=self.name,
                data={"city": city, "raw": raw, "summary": summary, "recommendation": rec},
                error=None,
                latency_ms=0,
            )
        except Exception as exc:
            logger.warning("weather_agent error: %s", exc)
            status = "error"
            result = AgentResult(agent_name=self.name, data={"city": city, "raw": {}, "summary": "", "recommendation": ""}, error=str(exc), latency_ms=0)

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
        return result
