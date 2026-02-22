# JARVIS AI — Multi-Agent Architecture Expansion
## Chain-Shot Prompt for OpenAI Codex / Claude Code

---

## CONTEXT — What Already Exists

The Jarvis AI project is a real-time voice + text assistant with the following stack:

```
backend/
├── main.py                  # FastAPI + WebSocket server
├── config.py                # API keys, model routing config
├── agents/
│   └── jarvis_agent.py      # Monolithic agent — handles ALL logic
├── tools/
│   ├── search.py            # Tavily web search
│   ├── weather.py           # OpenWeatherMap
│   └── memory.py            # Mem0 memory read
├── voice/
│   ├── stt.py               # Deepgram Nova-2 streaming STT
│   └── tts.py               # ElevenLabs streaming TTS
└── memory/
    └── mem0_client.py       # Mem0 persistent memory client
```

**Current problem:** `jarvis_agent.py` is a single monolithic function that does everything sequentially — route model, search memory, call tools, generate response. This blocks the event loop, creates latency, and does not scale.

**LLM Stack:** Groq (Llama 3.3 70B) for fast queries, Gemini 2.0 Flash for complex reasoning. Both are already configured in `config.py`.

---

## MISSION

Refactor `jarvis_agent.py` into a **modular, parallel multi-agent system** where specialized agents run concurrently and feed their results into a central Chat Agent that synthesizes the final response.

The architecture must be non-blocking, use `asyncio` for parallelism, and integrate cleanly with the existing FastAPI WebSocket server in `main.py`.

---

## PROMPT 1 — Design the Agent Registry

```
Create backend/agents/registry.py

This is the central registry and message bus for all Jarvis agents.

Requirements:
- Define an AgentResult dataclass with fields: agent_name, data, error, latency_ms
- Define an AgentRegistry class that:
  - Holds references to all registered agent instances
  - Has a method run_parallel(agents: list, context: dict) -> list[AgentResult]
    that runs all given agents concurrently using asyncio.gather()
    with a configurable timeout (default 4 seconds)
    and returns results even if some agents fail (return_exceptions=True)
  - Has a method run_agent(agent_name: str, context: dict) -> AgentResult
  - Tracks agent execution times
- Each agent must implement a base class BaseAgent with:
  - name: str property
  - async def run(context: dict) -> AgentResult method
- The registry must be instantiated as a singleton at module level
- All agent failures must be caught and returned as AgentResult with error field set,
  never crashing the main response pipeline
```

---

## PROMPT 2 — Memory Agent

```
Create backend/agents/memory_agent.py

This agent runs in parallel at the START of every conversation turn.
Its job is to proactively fetch everything Mem0 knows that is relevant
to the current user message BEFORE the chat agent generates a response.

Requirements:
- Extend BaseAgent from registry.py
- name = "memory"
- run(context) receives: { "user_message": str, "user_id": str }
- Perform TWO parallel Mem0 queries:
  1. Semantic search for memories relevant to the current message
  2. Fetch the 3 most recent memories regardless of relevance
- Merge and deduplicate results
- Return AgentResult with data = {
    "relevant_memories": list[str],
    "recent_memories": list[str],
    "formatted": str   # ready-to-inject string for system prompt
  }
- Cap total memory injection at 800 tokens worth of content
- If Mem0 is unavailable, return empty result gracefully
```

---

## PROMPT 3 — Context Agent

```
Create backend/agents/context_agent.py

This agent runs in parallel and decides WHAT the user is asking for
and what supporting information might be needed — before the chat agent runs.

Requirements:
- Extend BaseAgent from registry.py
- name = "context"
- run(context) receives: { "user_message": str, "conversation_history": list }
- Use Groq (fast model) to classify the message into:
  intent: one of [greeting, question_factual, question_reasoning, task_request,
                  weather_query, memory_query, search_needed, casual_chat, followup]
  needs_tools: list of tool names that will likely be needed
  complexity: "simple" | "complex"
  entities: list of key entities extracted (city names, topics, dates, etc.)
  suggested_model: "groq" | "gemini"
- The LLM call must complete in under 600ms — use a very short prompt
- Return AgentResult with data = { intent, needs_tools, complexity, entities, suggested_model }
- This result is used by the Orchestrator to decide which other agents to trigger
```

---

## PROMPT 4 — Search Agent

```
Create backend/agents/search_agent.py

This agent handles all web search operations asynchronously.
It only activates when the Context Agent signals search_needed.

Requirements:
- Extend BaseAgent from registry.py
- name = "search"
- run(context) receives: { "user_message": str, "entities": list, "query_override": str | None }
- Build an optimal search query from the message and entities
- Run search via Tavily (already in tools/search.py)
- If entities contain multiple distinct topics, run UP TO 2 parallel searches
  using asyncio.gather()
- Post-process results: extract only the most relevant 3 snippets,
  trim each to 200 words max
- Return AgentResult with data = {
    "results": list[{ title, snippet, url }],
    "formatted": str  # ready-to-inject string
  }
- Timeout individual searches at 3 seconds
- On failure return empty results, never block the pipeline
```

---

## PROMPT 5 — Weather Agent

```
Create backend/agents/weather_agent.py

Dedicated agent for weather queries. Only activates when Context Agent
detects weather_query intent or a city entity is found.

Requirements:
- Extend BaseAgent from registry.py
- name = "weather"
- run(context) receives: { "entities": list, "user_message": str }
- Extract city name from entities or fallback to parsing user_message
- If no city found, attempt to use a default location from memory context
- Fetch weather from OpenWeatherMap (already in tools/weather.py)
- Enrich the response with:
  - A natural language summary ("feels like a warm afternoon")
  - A recommendation ("umbrella advised after 4 PM")
- Return AgentResult with data = {
    "city": str,
    "raw": dict,       # raw API response
    "summary": str,    # natural language
    "recommendation": str
  }
```

---

## PROMPT 6 — Memory Writer Agent

```
Create backend/agents/memory_writer_agent.py

This agent runs AFTER the chat agent responds.
Its job is to extract and store meaningful information from the conversation
into Mem0 — automatically and asynchronously, without blocking the response.

Requirements:
- Extend BaseAgent from registry.py
- name = "memory_writer"
- run(context) receives: {
    "user_message": str,
    "assistant_response": str,
    "conversation_history": list,
    "user_id": str
  }
- Use Groq (fast model) to decide what is worth remembering:
  - User preferences stated explicitly
  - Facts about the user (name, location, job, habits)
  - Project-specific context
  - DO NOT store: questions, greetings, generic chit-chat
- Only store if the extraction yields something meaningful
- Write to Mem0 asynchronously — this agent must NEVER block or delay
  the response being sent to the user
- It should be fire-and-forget, triggered via asyncio.create_task()
- Return AgentResult with data = { "stored": bool, "memory_summary": str }
```

---

## PROMPT 7 — Summarization Agent

```
Create backend/agents/summarization_agent.py

This agent maintains conversation health by compressing old history
when it grows too long, preventing context window overflow.

Requirements:
- Extend BaseAgent from registry.py
- name = "summarizer"
- run(context) receives: { "conversation_history": list, "max_turns": int }
- Only activates when conversation_history exceeds max_turns (default: 16 messages)
- When triggered:
  - Take the oldest 8 messages
  - Use Groq to compress them into a single "Summary so far:" paragraph (max 150 words)
  - Replace those 8 messages with a single system-style summary message
  - Return the trimmed history
- Return AgentResult with data = {
    "was_compressed": bool,
    "new_history": list,
    "summary": str
  }
- This must be synchronous-safe — it runs before the main LLM call
```

---

## PROMPT 8 — Chat Agent (Refactored Core)

```
Refactor backend/agents/jarvis_agent.py into backend/agents/chat_agent.py

This is the central synthesis agent. It receives pre-fetched results
from all parallel agents and generates the final response.
It no longer fetches anything itself — it only synthesizes.

Requirements:
- Extend BaseAgent from registry.py
- name = "chat"
- run(context) receives: {
    "user_message": str,
    "conversation_history": list,
    "model": str,                    # decided by Context Agent
    "memory_context": str,           # from Memory Agent
    "search_context": str,           # from Search Agent (if ran)
    "weather_context": str,          # from Weather Agent (if ran)
    "intent": str,                   # from Context Agent
  }
- Build a rich system prompt by injecting all context strings
- Call the appropriate model (Groq or Gemini) based on model field
- Stream response tokens via the stream_callback passed in context
- Apply sentence buffering for TTS (same pattern as current main.py)
- Return AgentResult with data = { "full_response": str, "model_used": str, "tokens": int }
- Keep the same streaming interface so main.py needs minimal changes
```

---

## PROMPT 9 — Orchestrator (The Brain)

```
Create backend/agents/orchestrator.py

This is the top-level controller that coordinates all agents.
It replaces the direct call to get_jarvis_response() in main.py.

Requirements:
- Create class JarvisOrchestrator
- Main method: async def process(user_message, conversation_history, stream_callback) -> str

EXECUTION FLOW — implement exactly this:

  PHASE 1 — PRE-FLIGHT (parallel, before LLM call):
    Run simultaneously using asyncio.gather():
    - MemoryAgent.run()
    - ContextAgent.run()
    Both have a hard timeout of 2 seconds.
    If either fails, continue with empty results.

  PHASE 2 — CONDITIONAL AGENTS (parallel, based on Context Agent output):
    Based on context_result.data.needs_tools, trigger in parallel:
    - SearchAgent  → if "web_search" in needs_tools
    - WeatherAgent → if "weather" in needs_tools OR intent == "weather_query"
    All have a hard timeout of 3 seconds.

  PHASE 3 — SUMMARIZATION CHECK (sync, fast):
    If conversation_history > 16 messages:
      Run SummarizationAgent, update conversation_history

  PHASE 4 — CHAT SYNTHESIS:
    Run ChatAgent with all collected context from phases 1-3
    Stream tokens in real time via stream_callback

  PHASE 5 — POST-RESPONSE (fire and forget):
    asyncio.create_task(MemoryWriterAgent.run()) — non-blocking
    Log agent execution times to console

- Expose a get_orchestrator() singleton factory function
- Update main.py to import and use JarvisOrchestrator instead of get_jarvis_response()
- The WebSocket interface in main.py must not change — only the internal call changes
- Add a /agents/status HTTP endpoint to main.py that returns the health
  and last execution time of each registered agent
```

---

## PROMPT 10 — Agent Status UI Integration

```
Update backend/main.py to add:

1. GET /agents/status endpoint that returns:
   {
     "agents": [
       { "name": str, "last_run_ms": int, "last_status": "ok"|"error"|"skipped", "runs_today": int }
     ],
     "orchestrator_version": "2.0",
     "uptime_seconds": int
   }

2. In the WebSocket handler, after each orchestration cycle,
   emit a new WebSocket message type:
   { "type": "agent_trace", "trace": [
       { "agent": str, "duration_ms": int, "status": str, "skipped": bool }
   ]}
   This lets the frontend show which agents ran for each response.

3. Update frontend/src/App.jsx to:
   - Listen for "agent_trace" WebSocket messages
   - Display a small trace row below each Jarvis message showing
     which agents ran, their latency, and whether they were skipped
     Format: [MEMORY 45ms] [CONTEXT 280ms] [SEARCH skipped] [CHAT 820ms]
   - Use the existing monospace Share Tech Mono font and cyan color scheme
```

---

## ARCHITECTURAL CONSTRAINTS FOR CODEX

These are non-negotiable. Apply to all generated code:

1. **No agent blocks another.** Every agent uses `async/await`. No `time.sleep()`, no synchronous HTTP calls inside agents. Use `httpx.AsyncClient` for any HTTP.

2. **Graceful degradation.** If any agent fails or times out, the pipeline continues. The Chat Agent always gets called, even with empty context.

3. **Single source of truth for config.** All model names, timeouts, and API keys come from `config.py`. No hardcoded strings in agent files.

4. **Timeout discipline.** Every `asyncio.gather()` call wraps agents in `asyncio.wait_for()` with explicit timeouts. Never let a slow external API stall the whole response.

5. **Fire-and-forget post-processing.** MemoryWriter always uses `asyncio.create_task()` — it must never add latency to the user-facing response.

6. **Preserve the WebSocket interface.** `main.py` changes must be minimal. The frontend should work without modification except for the optional agent trace display.

7. **Logging.** Every agent logs its execution time and outcome using Python's `logging` module. Use `logging.getLogger(__name__)` per file.

8. **No circular imports.** Agent files import from `registry.py`, `config.py`, and `tools/`. They never import from each other or from `main.py`.

---

## EXPECTED FINAL STRUCTURE

```
backend/
├── main.py                          # Updated: uses Orchestrator, adds /agents/status
├── config.py                        # Unchanged
├── agents/
│   ├── registry.py                  # NEW: BaseAgent, AgentResult, AgentRegistry
│   ├── orchestrator.py              # NEW: JarvisOrchestrator — coordinates all agents
│   ├── chat_agent.py                # REFACTORED from jarvis_agent.py
│   ├── context_agent.py             # NEW: intent + routing decisions
│   ├── memory_agent.py              # NEW: parallel memory fetch
│   ├── memory_writer_agent.py       # NEW: async post-response memory storage
│   ├── search_agent.py              # NEW: parallel web search
│   ├── weather_agent.py             # NEW: dedicated weather fetching
│   └── summarization_agent.py      # NEW: conversation compression
├── tools/                           # Unchanged
├── voice/                           # Unchanged
└── memory/                          # Unchanged
```

---

## LATENCY TARGET

The full pipeline should add no more than 300ms overhead vs the current monolithic approach for simple queries, because Phase 1 agents run in parallel and are typically faster than the LLM call itself.

For complex queries with search, the search runs in parallel with context classification — so search results are ready by the time the Chat Agent needs them.

**Target latency budget:**
```
Phase 1 (Memory + Context parallel):  ~300ms
Phase 2 (Search/Weather if needed):   ~800ms  [overlaps with Phase 1 tail]
Phase 3 (Summarization if needed):    ~50ms
Phase 4 (Chat LLM — first token):     ~400ms
──────────────────────────────────────────────
Total to first streamed token:         ~750ms
```
