import { useEffect, useRef, useState } from "react";
import { streamChat } from "../api.js";
import { toCard } from "../cards.js";
import { ActionCard, EscalationBanner } from "./ActionCard.jsx";

const ROUTE_STATUS = {
  knowledge: "🔍 Searching knowledge base...",
  action: "⚙️ Checking your order...",
  escalate: "🧑‍💼 Escalating to a human agent...",
};

const SUGGESTIONS = [
  "Refund policy kya hai?",
  "Mera order 1001 kahan hai?",
  "Order 1002 ka refund chahiye",
  "Mujhe manager se baat karni hai",
];

const newThreadId = () =>
  crypto.randomUUID ? crypto.randomUUID() : `t-${Date.now()}-${Math.random().toString(16).slice(2)}`;

// Reveals the reply a few characters at a time (typing effect)
function TypingText({ text, animate, onTick }) {
  const [shown, setShown] = useState(animate ? 0 : text.length);

  useEffect(() => {
    if (!animate) return;
    const id = setInterval(() => {
      setShown((n) => {
        if (n >= text.length) {
          clearInterval(id);
          return n;
        }
        return Math.min(n + 2, text.length);
      });
      onTick?.();
    }, 14);
    return () => clearInterval(id);
  }, [text, animate]); // eslint-disable-line react-hooks/exhaustive-deps

  return <span>{text.slice(0, shown)}</span>;
}

export default function ChatWindow() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [threadId, setThreadId] = useState(newThreadId);
  const bottomRef = useRef(null);

  const scrollDown = () => bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    useEffect(() => {
    scrollDown(); // braces on purpose: an effect must not return a value
  }, [messages, status]);

  async function send(text) {
    const message = text.trim();
    if (!message || loading) return;
    setInput("");
    setMessages((m) => [...m, { id: crypto.randomUUID?.() || Date.now() + "u", role: "user", text: message }]);
    setLoading(true);
    setStatus("💭 Thinking...");

    const cards = [];
    let ticketId = null;
    let reply = null;
    let error = null;

    try {
      await streamChat({ message, threadId }, (e) => {
        if (e.type === "route") setStatus(ROUTE_STATUS[e.route] || "💭 Thinking...");
        else if (e.type === "status") setStatus(`⏳ ${e.message}`);
        else if (e.type === "agent" && e.name === "action") setStatus("📝 Finishing up...");
        else if (e.type === "tool") {
          const card = toCard(e);
          if (card) cards.push(card);
        } else if (e.type === "escalation") ticketId = e.ticket_id;
        else if (e.type === "message") reply = e.text;
        else if (e.type === "error") error = e.message;
      });
    } catch (err) {
      error = "Could not reach the server. Please check that the backend is running.";
    }

    setLoading(false);
    setStatus("");
    setMessages((m) => [
      ...m.map((x) => ({ ...x, animate: false })),
      {
        id: crypto.randomUUID?.() || Date.now() + "b",
        role: "bot",
        text: error || reply || "Sorry, I could not generate a reply.",
        error: Boolean(error),
        cards,
        ticketId,
        animate: !error,
      },
    ]);
  }

  function newChat() {
    if (loading) return;
    setMessages([]);
    setThreadId(newThreadId());
  }

  return (
    <div className="chat">
      <div className="chat-top">
        <span>Chat with our assistant</span>
        <button className="ghost" onClick={newChat} disabled={loading}>
          + New chat
        </button>
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome">
            <h2>Hi! How can I help you today?</h2>
            <p>Ask about policies, track an order, request a refund, or talk to a human.</p>
            <div className="chips">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`row ${m.role}`}>
            <div className={`bubble ${m.role}${m.error ? " error" : ""}`}>
              {m.role === "bot" ? <TypingText text={m.text} animate={m.animate} onTick={scrollDown} /> : m.text}
            </div>
            {m.role === "bot" && (
              <div className="extras">
                {m.cards?.map((c, i) => (
                  <ActionCard key={i} card={c} />
                ))}
                {m.ticketId && <EscalationBanner ticketId={m.ticketId} />}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="row bot">
            <div className="bubble bot status">
              <span className="dots">
                <i></i>
                <i></i>
                <i></i>
              </span>
              {status}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="composer">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder="Type your message..."
          disabled={loading}
          maxLength={2000}
        />
        <button onClick={() => send(input)} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
