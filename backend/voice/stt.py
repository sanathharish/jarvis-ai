import asyncio
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from config import DEEPGRAM_API_KEY

deepgram = DeepgramClient(DEEPGRAM_API_KEY)

def create_deepgram_connection(on_transcript, on_final, loop):
    try:
        dg_connection = deepgram.listen.live.v("1")

        def on_message(self, result, **kwargs):
            try:
                transcript = result.channel.alternatives[0].transcript
                if not transcript:
                    return
                if result.is_final:
                    asyncio.run_coroutine_threadsafe(on_final(transcript), loop)
                else:
                    asyncio.run_coroutine_threadsafe(on_transcript(transcript), loop)
            except Exception as e:
                print(f"STT message error: {e}")

        def on_error(self, error, **kwargs):
            print(f"Deepgram error: {error}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(
            model="nova-2",        # Changed from nova-3 — more stable
            language="en-US",
            smart_format=True,
            interim_results=True,
            endpointing=300,
            utterance_end_ms=1000
        )

        started = dg_connection.start(options)
        if not started:
            print("Deepgram connection failed to start")
            return None

        return dg_connection

    except Exception as e:
        print(f"Failed to create Deepgram connection: {e}")
        return None