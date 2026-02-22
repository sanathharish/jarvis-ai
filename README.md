# JARVIS AI — Real-time Voice & Text Assistant

A personal AI assistant inspired by Iron Man's Jarvis, built with modern AI infrastructure.

## Features
- Real-time voice input via Deepgram Nova-3 (streaming STT)
- Multi-model LLM routing — Claude Haiku for speed, Claude Sonnet for reasoning
- Tool use — web search, weather, memory recall
- Persistent memory via Mem0
- Streaming TTS via ElevenLabs
- Beautiful real-time UI with waveform and orb visualization

## Tech Stack
| Layer | Technology |
|---|---|
| STT | Deepgram Nova-3 |
| LLM | Claude Haiku + Sonnet (Anthropic) |
| TTS | ElevenLabs Turbo v2.5 |
| Memory | Mem0 |
| Search | Tavily |
| Backend | FastAPI + WebSockets |
| Frontend | React + Vite + Tailwind |

## Project Structure
\`\`\`
jarvis/
├── backend/        # FastAPI server, agents, tools, voice
├── frontend/       # React UI
├── .env.example    # Copy this to .env and fill in your keys
└── README.md
\`\`\`

## Setup

### 1. Clone the repo
\`\`\`bash
git clone https://github.com/sanathharish/jarvis-ai.git
cd jarvis-ai
\`\`\`

### 2. Set up environment variables
\`\`\`bash
cp .env.example .env
# Fill in your API keys in .env
\`\`\`

### 3. Backend
\`\`\`bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
\`\`\`

### 4. Frontend
\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

### 5. Open
Visit http://localhost:5173 — click the orb and start talking.

## API Keys Required
- Anthropic — claude.ai/api
- Deepgram — deepgram.com
- ElevenLabs — elevenlabs.io
- Tavily — tavily.com
- OpenWeatherMap — openweathermap.org/api
- Mem0 — app.mem0.ai

## Roadmap
- [x] Real-time voice input
- [x] Multi-model routing
- [x] Tool use (search, weather, memory)
- [x] Persistent memory
- [x] Streaming TTS
- [ ] Wake word detection
- [ ] Document writing mode
- [ ] Smart home integration
- [ ] Computer control
\`\`\`