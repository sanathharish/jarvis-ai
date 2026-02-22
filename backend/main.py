import asyncio
import base64
import json
import logging
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from agents.orchestrator import get_orchestrator
from agents.registry import registry
from config import ORCHESTRATOR_VERSION
from voice.stt import create_deepgram_connection
from voice.tts import text_to_speech_stream

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
start_time = time.monotonic()
orchestrator = get_orchestrator()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/agents/status")
async def agents_status():
    uptime_seconds = int(time.monotonic() - start_time)
    return {
        "agents": registry.get_status(),
        "orchestrator_version": ORCHESTRATOR_VERSION,
        "uptime_seconds": uptime_seconds,
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    conversation_history = []
    dg_connection = None
    send_lock = asyncio.Lock()

    # Audio queue to prevent overlap
    audio_queue = asyncio.Queue()
    audio_worker_task = None

    async def send_json(data: dict):
        async with send_lock:
            try:
                await websocket.send_text(json.dumps(data))
            except Exception:
                pass

    async def audio_worker():
        """Processes speech queue one sentence at a time — no overlap."""
        while True:
            text = await audio_queue.get()
            if text is None:
                break
            try:
                await send_json({"type": "status", "status": "speaking"})
                async for audio_chunk in text_to_speech_stream(text):
                    encoded = base64.b64encode(audio_chunk).decode("utf-8")
                    await send_json({"type": "audio_chunk", "data": encoded})
                await send_json({"type": "audio_done"})
            except Exception as e:
                print(f"TTS error: {e}")
                await send_json({"type": "error", "message": f"TTS error: {e}"})
            finally:
                audio_queue.task_done()

    async def enqueue_speech(text: str):
        await audio_queue.put(text)

    async def on_interim_transcript(text: str):
        await send_json({"type": "interim_transcript", "text": text})

    async def on_final_transcript(text: str):
        await send_json({"type": "final_transcript", "text": text})
        await process_message(text)

    async def process_message(user_message: str):
        await send_json({"type": "status", "status": "thinking"})

        llm_buffer = ""

        async def stream_token(token: str):
            nonlocal llm_buffer
            await send_json({"type": "llm_token", "token": token})
            llm_buffer += token

            # Queue complete sentences for TTS one at a time
            if any(llm_buffer.rstrip().endswith(p) for p in [".", "!", "?", "\n"]) and len(llm_buffer.strip()) > 20:
                await enqueue_speech(llm_buffer.strip())
                llm_buffer = ""

        full_response, trace, new_history = await orchestrator.process(
            user_message,
            conversation_history,
            stream_callback=stream_token
        )

        # Speak any remaining text
        if llm_buffer.strip():
            await enqueue_speech(llm_buffer.strip())

        # Wait for all speech to finish (avoid hanging forever)
        try:
            await asyncio.wait_for(audio_queue.join(), timeout=30)
        except asyncio.TimeoutError:
            await send_json({"type": "error", "message": "TTS timed out. Continuing."})

        conversation_history.clear()
        conversation_history.extend(new_history)
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "assistant", "content": full_response})

        await send_json({"type": "response_complete", "full_text": full_response})
        await send_json({"type": "agent_trace", "trace": trace})
        await send_json({"type": "status", "status": "idle"})

    # Start audio worker
    audio_worker_task = asyncio.create_task(audio_worker())

    try:
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await send_json({"type": "error", "message": "Invalid JSON from client."})
                continue
            msg_type = data.get("type")

            if msg_type == "start_listening":
                loop = asyncio.get_event_loop()
                try:
                    dg_connection = create_deepgram_connection(
                        on_interim_transcript, on_final_transcript, loop
                    )
                    if dg_connection:
                        await send_json({"type": "status", "status": "listening"})
                    else:
                        await send_json({"type": "status", "status": "idle"})
                        await send_json({"type": "error", "message": "Microphone connection failed. Check Deepgram key."})
                except Exception as e:
                    await send_json({"type": "status", "status": "idle"})
                    await send_json({"type": "error", "message": f"STT setup error: {e}"})

            elif msg_type == "audio_chunk":
                if dg_connection and dg_connection.is_connected():
                    try:
                        audio_bytes = base64.b64decode(data["data"])
                        dg_connection.send(audio_bytes)
                    except Exception as e:
                        print(f"Audio send error: {e}")
                        await send_json({"type": "error", "message": f"Audio send error: {e}"})
                else:
                    await send_json({"type": "error", "message": "Audio received while STT is not connected."})

            elif msg_type == "stop_listening":
                if dg_connection:
                    try:
                        dg_connection.finish()
                    except Exception:
                        pass
                    dg_connection = None
                await send_json({"type": "status", "status": "idle"})

            elif msg_type == "text_message":
                if "text" not in data:
                    await send_json({"type": "error", "message": "Missing text in text_message."})
                else:
                    await process_message(data["text"])
            else:
                await send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if dg_connection:
            try:
                dg_connection.finish()
            except Exception:
                pass
        # Stop audio worker
        await audio_queue.put(None)
        if audio_worker_task:
            await audio_worker_task

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
