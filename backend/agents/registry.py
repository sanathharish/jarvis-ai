import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from config import AGENT_TIMEOUT_DEFAULT

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    agent_name: str
    data: Any = None
    error: Optional[str] = None
    latency_ms: int = 0


class BaseAgent:
    name: str = "base"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}
        self._stats: Dict[str, Dict[str, Any]] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent
        if agent.name not in self._stats:
            self._stats[agent.name] = {
                "last_run_ms": 0,
                "last_status": "skipped",
                "runs_today": 0,
                "last_run_date": date.today(),
            }

    def get(self, agent_name: str) -> Optional[BaseAgent]:
        return self._agents.get(agent_name)

    def _update_stats(self, agent_name: str, result: AgentResult) -> None:
        stats = self._stats.setdefault(agent_name, {})
        today = date.today()
        if stats.get("last_run_date") != today:
            stats["runs_today"] = 0
            stats["last_run_date"] = today
        stats["runs_today"] = int(stats.get("runs_today", 0)) + 1
        stats["last_run_ms"] = int(result.latency_ms or 0)
        stats["last_status"] = "error" if result.error else "ok"

    async def run_agent(self, agent_name: str, context: Dict[str, Any], timeout_s: float = AGENT_TIMEOUT_DEFAULT) -> AgentResult:
        agent = self.get(agent_name)
        if not agent:
            return AgentResult(agent_name=agent_name, data=None, error="agent_not_registered", latency_ms=0)

        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(agent.run(context), timeout=timeout_s)
        except asyncio.TimeoutError:
            result = AgentResult(agent_name=agent.name, data=None, error="timeout", latency_ms=0)
        except Exception as exc:
            result = AgentResult(agent_name=agent.name, data=None, error=str(exc), latency_ms=0)

        result.latency_ms = int((time.perf_counter() - start) * 1000)
        self._update_stats(agent.name, result)
        logger.info("agent=%s status=%s latency_ms=%s", agent.name, "error" if result.error else "ok", result.latency_ms)
        return result

    async def run_parallel(self, agents: List[str], context: Dict[str, Any], timeout_s: float = AGENT_TIMEOUT_DEFAULT) -> List[AgentResult]:
        tasks = [self.run_agent(name, context, timeout_s=timeout_s) for name in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        final_results: List[AgentResult] = []
        for idx, res in enumerate(results):
            if isinstance(res, AgentResult):
                final_results.append(res)
            else:
                agent_name = agents[idx] if idx < len(agents) else "unknown"
                final_results.append(AgentResult(agent_name=agent_name, data=None, error=str(res), latency_ms=0))
        return final_results

    def get_status(self) -> List[Dict[str, Any]]:
        output = []
        for name in sorted(self._agents.keys()):
            stats = self._stats.get(name, {})
            output.append(
                {
                    "name": name,
                    "last_run_ms": int(stats.get("last_run_ms", 0)),
                    "last_status": stats.get("last_status", "skipped"),
                    "runs_today": int(stats.get("runs_today", 0)),
                }
            )
        return output


registry = AgentRegistry()
