class JarvisWebSocket {
  constructor(onMessage) {
    this.onMessage = onMessage;
    this.ws = null;
    this.mediaRecorder = null;
    this.audioContext = new AudioContext();
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
  }

  handleMessage(data) {
    if (data.type === "audio_chunk") {
      this.queueAudio(data.data);
    } else {
      this.onMessage(data);
    }
  }

  async queueAudio(base64Data) {
    const binary = atob(base64Data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    
    const buffer = await this.audioContext.decodeAudioData(bytes.buffer);
    this.audioQueue.push(buffer);
    if (!this.isPlaying) this.playNext();
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
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.send({ type: "start_listening" });

    this.mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    this.mediaRecorder.ondataavailable = async (event) => {
      if (event.data.size > 0) {
        const buffer = await event.data.arrayBuffer();
        const base64 = btoa(String.fromCharCode(...new Uint8Array(buffer)));
        this.send({ type: "audio_chunk", data: base64 });
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

  sendText(text) {
    this.send({ type: "text_message", text });
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}

export default JarvisWebSocket;