import { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import JarvisWebSocket from "./services/websocket";

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
          setMessages((prev) => [...prev, { role: "assistant", content: data.full_text }]);
          setCurrentResponse("");
          setStatus("idle");
          break;
      }
    });
    jarvisRef.current.connect();
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
    <div className="min-h-screen bg-gray-950 text-white flex flex-col items-center">
      {/* Header */}
      <div className="w-full max-w-3xl px-4 py-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-widest text-blue-400">JARVIS</h1>
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${statusColors[status]}`} />
          <span className="text-sm text-gray-400">{statusLabels[status]}</span>
        </div>
      </div>

      {/* Orb */}
      <div className="my-8">
        <button
          onClick={toggleListening}
          className={`w-32 h-32 rounded-full flex items-center justify-center transition-all duration-300 ${
            isListening
              ? "bg-blue-600 shadow-[0_0_60px_rgba(59,130,246,0.8)] scale-110"
              : "bg-gray-800 hover:bg-gray-700 shadow-[0_0_30px_rgba(59,130,246,0.3)]"
          }`}
        >
          {isListening ? <MicOff size={40} /> : <Mic size={40} />}
        </button>
        {interimText && (
          <p className="text-center text-gray-400 mt-4 italic text-sm">{interimText}</p>
        )}
      </div>

      {/* Chat Feed */}
      <div className="w-full max-w-3xl flex-1 px-4 space-y-4 overflow-y-auto max-h-[50vh]">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-100"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {currentResponse && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed bg-gray-800 text-gray-100">
              {currentResponse}
              <span className="inline-block w-2 h-4 bg-blue-400 ml-1 animate-pulse" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Text Input */}
      <div className="w-full max-w-3xl px-4 py-6">
        <div className="flex gap-2">
          <input
            className="flex-1 bg-gray-800 rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Or type a message..."
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendText()}
          />
          <button
            onClick={sendText}
            className="bg-blue-600 hover:bg-blue-500 rounded-xl px-4 py-3 transition-colors"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}