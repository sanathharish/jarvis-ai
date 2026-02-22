import logging
import threading
import asyncio
import time
from typing import Any, Dict, List, Callable, Iterator

import groq
from google import genai
from google.genai import types

from agents.registry import BaseAgent, AgentResult
from config import GROQ_API_KEY, GEMINI_API_KEY, FAST_MODEL, SMART_MODEL

logger = logging.getLogger(__name__)

groq_client = groq.Groq(api_key=GROQ_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = (
    "You are Jarvis, a highly intelligent, concise assistant. "
    "Be direct and helpful. Use provided context when relevant."
)


def _build_system_prompt(memory_context: str, search_context: str, weather_context: str, intent: str) -> str:
    parts = [SYSTEM_PROMPT]
    if intent:
        parts.append(f"Intent: {intent}")
    if memory_context:
        parts.append(memory_context)
    if search_context:
        parts.append(search_context)
    if weather_context:
        parts.append(weather_context)
    return "\n\n".join(parts)

_ERROR_SENTINEL = object()


async def _stream_from_thread(iter_fn: Callable[[], Iterator[str]], on_token) -> str:
    queue: asyncio.Queue[object] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def runner() -> None:
        try:
            for token in iter_fn():
                loop.call_soon_threadsafe(queue.put_nowait, token)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, (_ERROR_SENTINEL, exc))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=runner, daemon=True).start()

    full = ""
    while True:
        item = await queue.get()
        if item is None:
            break
        if isinstance(item, tuple) and item and item[0] is _ERROR_SENTINEL:
            raise RuntimeError(str(item[1]))
        token = item
        full += token
        await on_token(token)
    return full


class ChatAgent(BaseAgent):
    name = "chat"

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        user_message = context.get("user_message", "")
        conversation_history: List[Dict[str, str]] = context.get("conversation_history", [])
        model = context.get("model", "groq")
        memory_context = context.get("memory_context", "")
        search_context = context.get("search_context", "")
        weather_context = context.get("weather_context", "")
        intent = context.get("intent", "")
        stream_callback = context.get("stream_callback")
        start = time.perf_counter()
        status = "ok"

        system_prompt = _build_system_prompt(memory_context, search_context, weather_context, intent)

        if model == "gemini":
            contents = []
            for msg in conversation_history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
            contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

            full_response = ""
            try:
                if stream_callback:
                    def _iter_gemini():
                        stream = gemini_client.models.generate_content_stream(
                            model=SMART_MODEL,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                max_output_tokens=1024,
                            ),
                        )
                        for chunk in stream:
                            if not chunk.candidates:
                                continue
                            for part in chunk.candidates[0].content.parts:
                                if hasattr(part, "text") and part.text:
                                    yield part.text

                    full_response = await _stream_from_thread(_iter_gemini, stream_callback)
                else:
                    def _call_gemini() -> str:
                        response = gemini_client.models.generate_content(
                            model=SMART_MODEL,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                max_output_tokens=1024,
                            ),
                        )
                        return response.candidates[0].content.parts[0].text if response.candidates else ""

                    full_response = await asyncio.to_thread(_call_gemini)
            except Exception as exc:
                status = "error"
                logger.warning("chat_agent gemini error: %s", exc)
                full_response = ""

            tokens = len(full_response.split())
            result = AgentResult(
                agent_name=self.name,
                data={"full_response": full_response, "model_used": SMART_MODEL, "tokens": tokens},
                error=None if status == "ok" else "gemini_stream_failed",
                latency_ms=0,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
            return result

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        full_response = ""
        try:
            if stream_callback:
                def _iter_groq():
                    stream = groq_client.chat.completions.create(
                        model=FAST_MODEL,
                        messages=messages,
                        stream=True,
                        max_tokens=1024,
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if not delta or not delta.content:
                            continue
                        yield delta.content

                full_response = await _stream_from_thread(_iter_groq, stream_callback)
            else:
                def _call_groq() -> str:
                    response = groq_client.chat.completions.create(
                        model=FAST_MODEL,
                        messages=messages,
                        max_tokens=1024,
                    )
                    return response.choices[0].message.content or ""

                full_response = await asyncio.to_thread(_call_groq)
        except Exception as exc:
            status = "error"
            logger.warning("chat_agent groq error: %s", exc)
            full_response = ""

        tokens = len(full_response.split())
        result = AgentResult(
            agent_name=self.name,
            data={"full_response": full_response, "model_used": FAST_MODEL, "tokens": tokens},
            error=None if status == "ok" else "groq_stream_failed",
            latency_ms=0,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info("agent=%s status=%s latency_ms=%s", self.name, status, latency_ms)
        return result
