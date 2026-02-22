class JarvisWebSocket {
  constructor(onMessage) {
    this.onMessage = onMessage;
    this.ws = null;
    this.mediaRecorder = null;
    this.audioContext = null;
    this.audioQueue = [];
    this.isPlaying = false;
  }

  connect() {
    this.ws = new WebSocket("ws://localhost:8000/ws");
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };
    this.ws.onopen = () => this.onMessage({ type: "connected" });
    this.ws.onclose = () => this.onMessage({ type: "disconnected" });
    this.ws.onerror = () => this.onMessage({ type: "error", message: "WebSocket connection error." });
  }

  handleMessage(data) {
    if (data.type === "audio_chunk") {
      this.queueAudio(data.data);
    } else {
      this.onMessage(data);
    }
  }

  async ensureAudioContext() {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
  }

  async queueAudio(base64Data) {
    await this.ensureAudioContext();
    try {
      const binary = atob(base64Data);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      
      const buffer = await this.audioContext.decodeAudioData(bytes.buffer);
      this.audioQueue.push(buffer);
      if (!this.isPlaying) this.playNext();
    } catch (err) {
      this.onMessage({ type: "error", message: `Audio decode error: ${err?.message || err}` });
    }
  }

  playNext() {
    if (this.audioQueue.length === 0) {
      this.isPlaying = false;
      return;
    }
    this.isPlaying = true;
    const source = this.audioContext.createBufferSource();
    source.buffer = this.audioQueue.shift();
    source.connect(this.audioContext.destination);
    source.onended = () => this.playNext();
    source.start();
  }

  async startListening() {
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      this.onMessage({ type: "error", message: `Microphone access denied: ${err?.message || err}` });
      return;
    }
    this.send({ type: "start_listening" });

    const preferredTypes = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
    ];
    const supportedType = preferredTypes.find((t) => MediaRecorder.isTypeSupported(t));
    const options = supportedType ? { mimeType: supportedType } : undefined;
    try {
      this.mediaRecorder = options ? new MediaRecorder(stream, options) : new MediaRecorder(stream);
    } catch (err) {
      console.error("MediaRecorder init failed, retrying with default:", err);
      this.mediaRecorder = new MediaRecorder(stream);
    }
    this.mediaRecorder.onerror = (event) => {
      const err = event?.error || event;
      this.onMessage({ type: "error", message: `MediaRecorder error: ${err?.message || err}` });
    };
    this.mediaRecorder.ondataavailable = async (event) => {
      if (event.data.size > 0) {
        try {
          const buffer = await event.data.arrayBuffer();
          const base64 = btoa(String.fromCharCode(...new Uint8Array(buffer)));
          this.send({ type: "audio_chunk", data: base64 });
        } catch (err) {
          this.onMessage({ type: "error", message: `Audio encode error: ${err?.message || err}` });
        }
      }
    };
    this.mediaRecorder.start(100); // Send chunks every 100ms
  }

  stopListening() {
    if (this.mediaRecorder) {
      this.mediaRecorder.stop();
      this.mediaRecorder = null;
    }
    this.send({ type: "stop_listening" });
  }

  close() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  sendText(text) {
    this.send({ type: "text_message", text });
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      this.onMessage({ type: "error", message: "WebSocket not connected." });
    }
  }
}

export default JarvisWebSocket;
