import httpx
from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

async def text_to_speech_stream(text: str):
    """Stream audio chunks from ElevenLabs."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
    
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",   # Lowest latency model
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        },
        "output_format": "mp3_44100_128"
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk
