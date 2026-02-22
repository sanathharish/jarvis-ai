import { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import JarvisWebSocket from "./services/websocket";
import "./App.css";

const statusColors = {
  idle: "bg-blue-500",
  listening: "bg-green-500 animate-pulse",
  thinking: "bg-yellow-500 animate-pulse",
  speaking: "bg-purple-500 animate-pulse",
};

const statusLabels = {
  idle: "Idle",
  listening: "Listening...",
  thinking: "Thinking...",
  speaking: "Speaking...",
};

export default function App() {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("idle");
  const [isListening, setIsListening] = useState(false);
  const [interimText, setInterimText] = useState("");
  const [textInput, setTextInput] = useState("");
  const [currentResponse, setCurrentResponse] = useState("");
  const jarvisRef = useRef(null);
  const bottomRef = useRef(null);
  const pendingTraceRef = useRef(null);

  useEffect(() => {
    jarvisRef.current = new JarvisWebSocket((data) => {
      switch (data.type) {
        case "status":
          setStatus(data.status);
          break;
        case "interim_transcript":
          setInterimText(data.text);
          break;
        case "final_transcript":
          setInterimText("");
          setMessages((prev) => [...prev, { role: "user", content: data.text }]);
          break;
        case "llm_token":
          setCurrentResponse((prev) => prev + data.token);
          break;
        case "response_complete":
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: data.full_text, trace: pendingTraceRef.current },
          ]);
          pendingTraceRef.current = null;
          setCurrentResponse("");
          setStatus("idle");
          break;
        case "error":
          setMessages((prev) => [...prev, { role: "system", content: `Error: ${data.message}` }]);
          setStatus("idle");
          break;
        case "agent_trace": {
          let attached = false;
          setMessages((prev) => {
            const next = [...prev];
            for (let i = next.length - 1; i >= 0; i -= 1) {
              if (next[i].role === "assistant") {
                next[i] = { ...next[i], trace: data.trace };
                attached = true;
                break;
              }
            }
            return next;
          });
          if (!attached) {
            pendingTraceRef.current = data.trace;
          }
          break;
        }
      }
    });
    jarvisRef.current.connect();
    return () => {
      jarvisRef.current?.close();
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentResponse]);

  const toggleListening = async () => {
    if (isListening) {
      jarvisRef.current.stopListening();
      setIsListening(false);
    } else {
      await jarvisRef.current.startListening();
      setIsListening(true);
    }
  };

  const sendText = () => {
    if (!textInput.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: textInput }]);
    jarvisRef.current.sendText(textInput);
    setTextInput("");
  };

  return (
    <div className="min-h-screen text-white bg-slate-950 app-grid">
      <div className="bg-orb bg-orb-1" />
      <div className="bg-orb bg-orb-2" />
      <div className="bg-orb bg-orb-3" />

      <div className="mx-auto w-full max-w-6xl px-4 pb-10">
        <header className="pt-8 pb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="brand-mark">J</div>
            <div>
              <div className="text-2xl font-semibold tracking-[0.35em] text-cyan-300">JARVIS</div>
              <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Voice Assistant Console</div>
            </div>
          </div>
          <div className="status-pill">
            <span className={`status-dot ${statusColors[status]}`} />
            <span>{statusLabels[status]}</span>
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <section className="panel">
            <div className="panel-title">Voice Control</div>
            <div className="panel-subtitle">Tap to start or stop capture.</div>

            <div className="orb-wrap">
              <button
                type="button"
                onClick={toggleListening}
                className={`orb ${isListening ? "orb-active" : ""}`}
              >
                {isListening ? <MicOff size={34} /> : <Mic size={34} />}
              </button>
              <div className="orb-ring" />
              <div className="orb-ring orb-ring-secondary" />
            </div>

            <div className="transcript-card">
              <div className="transcript-title">Live Transcript</div>
              <div className="transcript-body">
                {interimText ? (
                  <span className="italic text-slate-200">{interimText}</span>
                ) : (
                  <span className="text-slate-500">Waiting for audio…</span>
                )}
              </div>
            </div>

            <div className="panel-footer">
              <span className="text-xs text-slate-400">Tip: keep the mic close for best accuracy.</span>
            </div>
          </section>

          <section className="panel panel-chat">
            <div className="panel-title">Conversation</div>
            <div className="panel-subtitle">Text or voice replies appear here.</div>

            <div className="chat-feed">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`chat-row ${msg.role === "user" ? "chat-right" : "chat-left"} ${
                    msg.role === "system" ? "chat-system" : ""
                  }`}
                >
                  <div
                    className={`chat-bubble ${
                      msg.role === "user"
                        ? "bubble-user"
                        : msg.role === "system"
                        ? "bubble-system"
                        : "bubble-assistant"
                    }`}
                  >
                    {msg.content}
                    {msg.role === "assistant" && msg.trace && (
                      <div className="trace-row">
                        {msg.trace.map((t, idx) => (
                          <span key={`${t.agent}-${idx}`} className={`trace-pill ${t.skipped ? "trace-skip" : ""}`}>
                            {t.agent.toUpperCase()} {t.skipped ? "skipped" : `${t.duration_ms}ms`}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {currentResponse && (
                <div className="chat-row chat-left">
                  <div className="chat-bubble bubble-assistant">
                    {currentResponse}
                    <span className="inline-block w-2 h-4 bg-cyan-300 ml-1 animate-pulse" />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            <div className="input-shell">
              <input
                className="input-field"
                placeholder="Type a message…"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendText()}
              />
              <button onClick={sendText} className="input-send">
                <Send size={18} />
                <span className="hidden sm:inline">Send</span>
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
