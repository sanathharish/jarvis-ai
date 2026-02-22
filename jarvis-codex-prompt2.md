# JARVIS AI — Intelligent Model Router & Learning System
## Codex Implementation Prompt

---

## CONTEXT

Jarvis AI has a multi-agent backend where agents run in parallel.
Currently model routing is static — fast queries go to Groq Llama 3.3,
complex queries go to Gemini 2.0 Flash.

The problem:
1. Models hit rate limits and the system crashes instead of falling back
2. No way to manually choose which model to use
3. No learning — the system doesn't know which models perform better
   for which task types
4. Not extensible — adding a new model requires code changes everywhere

---

## MISSION

Build a Model Router & Intelligence Layer that:
- Maintains a registry of ALL available models across ALL providers
- Handles rate limits and failures with automatic fallback chains
- Lets users manually select a model or enable auto-selection
- Tracks performance metrics per model per task type
- Stores metrics in a knowledge base and learns over time
- Exposes a selection API the Orchestrator and any agent can call
- Is designed to be extended with computer automation models in future

---

## PROMPT 1 — Model Registry

Create backend/models/registry.py

Define a complete model registry as a Python dict MODEL_REGISTRY.
Each entry represents one callable model with this schema:

{
  "model_id": str,              # unique internal ID e.g. "groq_llama33_70b"
  "provider": str,              # "groq" | "gemini" | "openrouter" | "mistral"
                                #  | "cerebras" | "together" | "cohere" | "huggingface"
  "model_name": str,            # exact API model name string
  "api_key_env": str,           # env var name e.g. "GROQ_API_KEY"
  "base_url": str,              # API endpoint base URL
  "strengths": list[str],       # e.g. ["reasoning", "tool_use", "code", "speed",
                                #  "long_context", "web_research", "summarization",
                                #  "classification", "vision", "rag"]
  "context_window": int,        # max tokens
  "is_free": bool,
  "supports_streaming": bool,
  "supports_tools": bool,
  "supports_vision": bool,      # for future computer screenshot analysis
  "tier": str,                  # "fast" | "balanced" | "powerful"
  "daily_limit": int | None,    # None = unknown/unlimited
  "rpm_limit": int | None,      # requests per minute
  "priority": int,              # lower = try first within same tier (1-10)
  "enabled": bool,              # can be toggled at runtime
  "notes": str                  # human-readable notes
}

Populate with ALL of these models:

GROQ (base_url: https://api.groq.com/openai/v1):
- llama-3.3-70b-versatile       → groq_llama33_70b
- llama-3.1-8b-instant          → groq_llama31_8b
- llama-3.2-90b-vision-preview  → groq_llama32_90b_vision
- mixtral-8x7b-32768            → groq_mixtral_8x7b
- gemma2-9b-it                  → groq_gemma2_9b

GEMINI (use google-genai SDK):
- gemini-2.0-flash              → gemini_20_flash
- gemini-1.5-flash              → gemini_15_flash
- gemini-1.5-flash-8b           → gemini_15_flash_8b
- gemini-1.5-pro                → gemini_15_pro
- gemini-2.0-flash-thinking-exp → gemini_20_thinking

OPENROUTER (base_url: https://openrouter.ai/api/v1, OpenAI-compatible):
- google/gemini-2.0-flash-exp:free      → openrouter_gemini20
- meta-llama/llama-3.3-70b-instruct:free → openrouter_llama33
- deepseek/deepseek-r1:free             → openrouter_deepseek_r1
- microsoft/phi-4:free                  → openrouter_phi4
- qwen/qwen-2.5-72b-instruct:free       → openrouter_qwen25

CEREBRAS (base_url: https://api.cerebras.ai/v1, OpenAI-compatible):
- llama-3.3-70b   → cerebras_llama33_70b
- llama-3.1-8b    → cerebras_llama31_8b

MISTRAL (base_url: https://api.mistral.ai/v1):
- open-mistral-nemo       → mistral_nemo
- mistral-small-latest    → mistral_small
- open-codestral-mamba    → mistral_codestral

---

## PROMPT 2 — Model Client Adapter

Create backend/models/client.py

This is a unified async interface that can call ANY model in the registry
using a consistent interface, regardless of provider.

Requirements:
- class ModelClient with:
  - async def complete(model_id, messages, system, stream_callback, tools) -> str
  - async def complete_fast(model_id, messages, system) -> str  # no streaming, no tools
  - Internally routes to the correct provider SDK:
    - Groq, Cerebras, OpenRouter, Together, Mistral → use openai-compatible
      httpx calls with the correct base_url and api_key
    - Gemini → use google-genai SDK
    - Cohere → use cohere SDK
  - All calls are async, non-blocking
  - All calls have a configurable timeout (default from config)
  - Catches and re-raises provider-specific errors as unified:
    ModelRateLimitError, ModelTimeoutError, ModelUnavailableError

- Do NOT import any specific provider SDK at module level.
  Use lazy imports inside the routing logic so missing SDKs don't
  crash the whole system.

---

## PROMPT 3 — Rate Limit Tracker

Create backend/models/rate_tracker.py

Tracks usage and rate limit state for every model in real time.
Stored in memory (dict) for now — no database needed yet.

Requirements:
- class RateLimitTracker (singleton):
  - record_request(model_id)          # call before every API request
  - record_success(model_id)
  - record_rate_limit_hit(model_id)   # call when 429 received
  - record_failure(model_id, error)
  - is_available(model_id) -> bool    # False if recently 429'd
  - get_cooldown_remaining(model_id) -> int  # seconds until retry

- When a model hits a 429:
  - Mark it as cooling down for the retry_after duration from the error
    (parse from error message if present, default to 60 seconds)
  - is_available() returns False during cooldown
  - Automatically clears after cooldown expires

- Track per model:
  - requests_this_minute (rolling window)
  - requests_today (resets at midnight)
  - consecutive_failures
  - last_429_at
  - total_successes
  - total_failures

- Expose get_status_all() -> dict for the /models/status endpoint

---

## PROMPT 4 — Fallback Chain Router

Create backend/models/router.py

This is the intelligent model selector. When any agent needs a model,
it asks this router — never hardcoding a model name directly.

Requirements:
- class ModelRouter (singleton):

  async def select_model(
    task_type: str,           # "fast_chat" | "reasoning" | "web_research" |
                              #  "summarization" | "classification" | "code" |
                              #  "vision" | "rag" | "tool_use"
    preferred_model_id: str | None,   # explicit user choice, override everything
    require_tools: bool,
    require_vision: bool,
    require_streaming: bool,
    min_context_window: int,
  ) -> str                    # returns model_id to use

  Logic:
  1. If preferred_model_id is set AND model is available → use it
  2. If preferred_model_id is set but rate-limited → notify but use fallback
  3. Otherwise, build a candidate list:
     a. Filter MODEL_REGISTRY by: enabled=True, supports required capabilities
     b. Filter out models where RateLimitTracker.is_available() == False
     c. Sort candidates by: task performance score (from MetricsStore),
        then by priority field, then by tier match
  4. Return the top candidate's model_id
  5. If NO candidates available → raise AllModelsExhaustedError

  async def get_fallback_chain(model_id, task_type) -> list[str]
  # Returns ordered list of fallbacks for a given model + task

  async def execute_with_fallback(
    task_type, messages, system,
    stream_callback, tools,
    preferred_model_id, **kwargs
  ) -> tuple[str, str]  # (response_text, model_id_used)
  # Tries primary model, falls back automatically on rate limit / failure
  # Emits a "model_switched" event when fallback occurs

---

## PROMPT 5 — Metrics Store (Learning System)

Create backend/models/metrics_store.py

This is the long-term learning brain. It records how every model
performs on every task type and builds a knowledge base over time.
The system uses this data to improve routing decisions automatically.

Requirements:
- Uses SQLite (built into Python, no extra install) stored at
  backend/data/model_metrics.db

- Schema — table model_performance:
  id, model_id, task_type, timestamp,
  latency_ms, tokens_generated, success (bool),
  user_rating (int | None),   # 1-5, from future thumbs up/down UI
  was_fallback (bool),        # was this model a fallback choice?
  context_length_used (int),
  error_type (str | None)

- Schema — table model_task_scores:
  model_id, task_type,
  avg_latency_ms, success_rate, sample_count,
  composite_score,            # weighted: 40% speed, 40% success, 20% user_rating
  last_updated, is_recommended (bool)

- class MetricsStore:
  - record(model_id, task_type, latency_ms, tokens, success, error_type, was_fallback)
  - get_best_model_for_task(task_type) -> str | None
    # Returns model_id with highest composite_score and sample_count >= 10
  - get_leaderboard(task_type) -> list[dict]
    # Ranked list for a given task type
  - get_model_report(model_id) -> dict
    # Full stats for one model across all task types
  - recompute_scores()
    # Recalculates composite_score for all model+task combos
    # Called automatically every 50 requests or on demand
  - export_insights() -> dict
    # Human-readable summary: "For web_research, groq_llama33_70b
    #  outperforms gemini_20_flash by 23% in speed with equal accuracy"

- Create backend/data/ directory and .gitkeep file
- Add backend/data/*.db to .gitignore

---

## PROMPT 6 — User Model Preference API

Create backend/models/preferences.py

Manages per-user model preferences, persisted in Mem0 AND locally.

Requirements:
- class UserPreferences:
  - get_preferred_model(user_id, task_type) -> str | None
  - set_preferred_model(user_id, task_type, model_id)
  - set_global_preferred_model(user_id, model_id)
    # overrides ALL task types with one model
  - enable_auto_mode(user_id)
    # clears preferences, lets MetricsStore decide
  - is_auto_mode(user_id) -> bool
  - get_all_preferences(user_id) -> dict

- Persist in a local JSON file at backend/data/user_preferences.json
- Also sync meaningful preferences to Mem0 as a memory so the
  conversational agent is aware ("User prefers DeepSeek R1 for reasoning")

---

## PROMPT 7 — Update All Agents to Use Router

Update ALL agent files to remove hardcoded model names.

For each agent file (context_agent.py, chat_agent.py,
memory_writer_agent.py, summarization_agent.py):

1. Import ModelRouter from backend/models/router.py
2. Replace every direct groq_client.chat.completions.create() or
   gemini_client.models.generate_content() call with:
   ModelRouter.execute_with_fallback(
     task_type=<appropriate_task_type>,
     messages=messages,
     system=system_prompt,
     stream_callback=stream_callback,  # None for non-streaming
     tools=tools,
     preferred_model_id=context.get("preferred_model_id")
   )

3. Task type mapping to use per agent:
   - ContextAgent      → "classification"
   - ChatAgent         → "reasoning" | "fast_chat" (based on complexity)
   - MemoryWriterAgent → "classification"
   - SummarizationAgent → "summarization"
   - SearchAgent       → "web_research"
   - WeatherAgent      → "fast_chat"

4. Every agent must pass the model_id_used from execute_with_fallback
   back in its AgentResult.data so the Orchestrator can log it

5. After every successful agent run, call:
   MetricsStore.record(model_id, task_type, latency_ms, ...)

---

## PROMPT 8 — WebSocket Model Control Messages

Update backend/main.py to handle new WebSocket message types:

New message types FROM frontend:
- { type: "set_model", model_id: "groq_llama33_70b" }
  → sets preferred model for this session
- { type: "set_model_auto" }
  → enables auto mode, clears session preference
- { type: "get_models" }
  → returns full model list with availability status
- { type: "get_metrics", task_type: "reasoning" }
  → returns leaderboard for that task type

New message types TO frontend:
- { type: "model_switched", from: str, to: str, reason: str }
  → emitted when fallback occurs mid-conversation
- { type: "models_list", models: [...], current: str, auto_mode: bool }
- { type: "metrics_report", leaderboard: [...] }

New HTTP endpoints:
- GET  /models              → list all models with status
- GET  /models/{model_id}   → single model stats
- GET  /models/leaderboard/{task_type}  → ranked models for task
- POST /models/prefer       → body: { model_id, task_type }
- POST /models/auto         → enable auto mode
- GET  /models/insights     → MetricsStore.export_insights()

---

## PROMPT 9 — Frontend Model Selector Component

Create frontend/src/components/ModelSelector.jsx

Requirements:
- A compact UI component that fits in the existing HUD aesthetic
- Shows currently active model name and provider
- Dropdown/panel with all available models grouped by provider
- Each model shows:
  - Name, provider badge
  - Availability indicator (green = ready, yellow = rate limited with
    cooldown timer, grey = disabled)
  - Performance badge for current task (⚡ fast / 🧠 smart / ⭐ best)
  - "Best for: reasoning, code..." tags
- An "AUTO" toggle switch at the top — when on, system chooses
- When a model is rate-limited mid-conversation, show a toast:
  "Switched from Gemini to Groq (rate limit reached)"
- When in auto mode, show which model was actually used per message
  (already in the agent trace row)
- Use the existing Share Tech Mono font, cyan/dark HUD aesthetic

---

## PROMPT 10 — Future-Proof Extension Points

Add the following as empty, documented stub files that signal
where future features plug in. Do not implement logic — just
define the interfaces with docstrings.

Create backend/models/computer_automation_router.py:
  # Future: routes tasks to models with computer-use capability
  # Candidates: Anthropic computer-use, GPT-4o with computer-use,
  #   gemini-2.0-flash with screen understanding
  # Will receive: task_type="screen_analysis"|"dom_interaction"|
  #   "file_operation"|"browser_control"|"code_execution"
  # The ModelRegistry already has supports_vision=True on relevant models
  # This router will filter for models where
  #   "computer_use" in strengths (add this strength to registry entries
  #   for: groq_llama32_90b_vision, gemini_20_flash, openrouter_phi4)

Create backend/agents/computer_agent.py:
  # Future: agent that executes actions on the host computer
  # Will use PyAutoGUI, Playwright, or computer-use API
  # Receives: { action_type, target, parameters, screenshot_b64 }
  # Returns: { success, result, screenshot_after_b64 }
  # Already integrated into AgentRegistry — just needs implementation

Create backend/models/fine_tune_tracker.py:
  # Future: when a local model is fine-tuned on Jarvis-specific tasks,
  # track its performance separately from the base model
  # Will plug into MetricsStore with is_local=True flag

Create backend/agents/knowledge_agent.py:
  # Future: dedicated RAG agent that searches a local vector store
  # (Chroma or Qdrant) built from user's documents, notes, PDFs
  # Already has a slot in the Orchestrator's Phase 2 conditional agents
  # Activate by adding "knowledge_search" to needs_tools in ContextAgent

---

## ARCHITECTURAL CONSTRAINTS

1. MetricsStore learns passively — no extra LLM calls for evaluation.
   Metrics are collected from existing calls: latency, success/fail,
   and optional future user ratings.

2. The router must NEVER block. If MetricsStore is slow, use
   cached scores (recomputed async in background every 50 requests).

3. All new files go in backend/models/ — clean separation from agents/.

4. config.py gets new entries:
   DEFAULT_TASK_MODEL_MAP: dict mapping task_type → preferred model_id
   These are the startup defaults before MetricsStore has enough data.
   After 10+ samples per task, MetricsStore recommendations override these.

5. The learning system is additive — it never removes a model from the
   rotation automatically. Low-scoring models just get lower priority.
   Humans disable models explicitly via the /models endpoint.

6. Every new API key goes in .env and .env.example immediately.
   Never hardcode credentials anywhere.

7. SQLite file is in backend/data/ which is gitignored.
   On first run, the DB is created automatically if it doesn't exist.

---

## EXPECTED NEW STRUCTURE

backend/
├── models/                          # NEW directory — entire model layer
│   ├── registry.py                  # All models, all providers
│   ├── client.py                    # Unified async model caller
│   ├── router.py                    # Intelligent selection + fallback
│   ├── rate_tracker.py              # Real-time rate limit state
│   ├── metrics_store.py             # SQLite learning system
│   ├── preferences.py               # Per-user model preferences
│   ├── computer_automation_router.py # STUB — future computer use
│   └── fine_tune_tracker.py         # STUB — future fine-tuning
├── agents/
│   ├── registry.py                  # Unchanged
│   ├── orchestrator.py              # Updated: passes preferred_model_id
│   ├── chat_agent.py                # Updated: uses ModelRouter
│   ├── context_agent.py             # Updated: uses ModelRouter
│   ├── memory_writer_agent.py       # Updated: uses ModelRouter
│   ├── summarization_agent.py       # Updated: uses ModelRouter
│   ├── search_agent.py              # Updated: uses ModelRouter
│   ├── weather_agent.py             # Updated: uses ModelRouter
│   ├── computer_agent.py            # STUB — future computer use
│   └── knowledge_agent.py           # STUB — future RAG/docs
├── data/
│   ├── .gitkeep
│   ├── model_metrics.db             # gitignored, auto-created
│   └── user_preferences.json        # gitignored, auto-created
├── main.py                          # Updated: new WS messages + endpoints
└── config.py                        # Updated: DEFAULT_TASK_MODEL_MAP

frontend/src/components/
└── ModelSelector.jsx                # NEW: model picker HUD component

---

## LEARNING SYSTEM LIFECYCLE

How the system gets smarter over time:

Day 1:   Uses DEFAULT_TASK_MODEL_MAP from config (your manual defaults)
Week 1:  MetricsStore accumulates data, composite_scores start forming
Week 2:  get_best_model_for_task() returns data-driven recommendations
         Router starts using these instead of config defaults
Month 1: System has strong opinions — "For web_research, Groq Llama33
         is 40% faster than Gemini with 96% success rate"
Future:  User ratings from thumbs up/down UI further refine scores
         Fine-tuned local models get tracked separately
         Computer automation tasks get their own model leaderboard