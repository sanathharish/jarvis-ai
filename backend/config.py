import os
from dotenv import load_dotenv

load_dotenv("../.env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
MEM0_API_KEY = os.getenv("MEM0_API_KEY")
USER_ID = os.getenv("USER_ID", "jarvis_user_1")

# Model routing config
FAST_MODEL = "llama-3.3-70b-versatile"   # Groq - fastest inference
SMART_MODEL = "gemini-2.0-flash"          # Gemini - best free reasoning

# Word threshold for routing
FAST_MODEL_WORD_THRESHOLD = 15

# Model registries for future provider expansion
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODELS = {
    "groq_llama33_70b": "llama-3.3-70b-versatile",
    "groq_llama31_8b": "llama-3.1-8b-instant",
    "groq_llama32_90b_vision": "llama-3.2-90b-vision-preview",
    "groq_mixtral_8x7b": "mixtral-8x7b-32768",
    "groq_gemma2_9b": "gemma2-9b-it",
}

GEMINI_MODELS = {
    "gemini_20_flash": "gemini-2.0-flash",
    "gemini_15_flash": "gemini-1.5-flash",
    "gemini_15_flash_8b": "gemini-1.5-flash-8b",
    "gemini_15_pro": "gemini-1.5-pro",
    "gemini_20_thinking": "gemini-2.0-flash-thinking-exp",
}

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS = {
    "openrouter_gemini20": "google/gemini-2.0-flash-exp:free",
    "openrouter_llama33": "meta-llama/llama-3.3-70b-instruct:free",
    "openrouter_deepseek_r1": "deepseek/deepseek-r1:free",
    "openrouter_phi4": "microsoft/phi-4:free",
    "openrouter_qwen25": "qwen/qwen-2.5-72b-instruct:free",
}

CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
CEREBRAS_MODELS = {
    "cerebras_llama33_70b": "llama-3.3-70b",
    "cerebras_llama31_8b": "llama-3.1-8b",
}

MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
MISTRAL_MODELS = {
    "mistral_nemo": "open-mistral-nemo",
    "mistral_small": "mistral-small-latest",
    "mistral_codestral": "open-codestral-mamba",
}

# Agent orchestration config
AGENT_TIMEOUT_DEFAULT = 4.0
AGENT_TIMEOUT_PREFLIGHT = 2.0
AGENT_TIMEOUT_TOOLS = 3.0
AGENT_TIMEOUT_SUMMARY = 1.5
ORCHESTRATOR_VERSION = "2.0"
CONTEXT_LLM_TIMEOUT_S = 0.6
SEARCH_AGENT_TIMEOUT_S = 3.0
