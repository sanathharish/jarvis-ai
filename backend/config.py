import os
from dotenv import load_dotenv

load_dotenv("../.env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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