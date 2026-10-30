import React, { useState } from "react";
import { AskResponse, Citation } from "../types";

export const AssistantChat: React.FC = () => {
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<{ query: string; response: AskResponse }[]>([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const q = query.trim();
    setQuery("");
    setLoading(true);

    try {
      const res = await fetch("/api/v1/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, departureSec: 32400 }),
      });
      if (res.ok) {
        const data: AskResponse = await res.json();
        setHistory((prev) => [...prev, { query: q, response: data }]);
      } else {
        const errData = await res.json().catch(() => ({}));
        setHistory((prev) => [
          ...prev,
          {
            query: q,
            response: {
              answer: errData.message || "Failed to contact transit assistant.",
              citations: [],
              warnings: ["Service error"],
            },
          },
        ]);
      }
    } catch (err: any) {
      setHistory((prev) => [
        ...prev,
        {
          query: q,
          response: {
            answer: "Network error reaching gateway.",
            citations: [],
            warnings: [String(err)],
          },
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel card assistant-chat">
      <div className="chat-header">
        <h3>Transit Policy Copilot</h3>
        <span className="rag-badge">LlamaIndex + LangGraph RAG</span>
      </div>

      <div className="chat-messages">
        {history.length === 0 && (
          <div className="chat-placeholder">
            <p>Ask anything about Bengaluru transit policies, fares, or routes:</p>
            <ul>
              <li>"What is the maximum fare on Namma Metro?"</li>
              <li>"What are the rules for smart cards?"</li>
              <li>"Are there direct buses from Silk Board to Manyata?"</li>
            </ul>
          </div>
        )}

        {history.map((item, idx) => (
          <div key={idx} className="message-block">
            <div className="user-bubble">
              <strong>You:</strong> {item.query}
            </div>
            <div className="assistant-bubble">
              <div className="answer-text">{item.response.answer}</div>

              {item.response.citations && item.response.citations.length > 0 && (
                <div className="citations-tray">
                  <span className="tray-title">Ground Truth Sources:</span>
                  <div className="citation-chips">
                    {item.response.citations.map((c: Citation) => {
                      const isVerified = c.trust_tier === "VERIFIED";
                      return (
                        <span
                          key={c.id}
                          className={`citation-chip ${isVerified ? "chip-verified" : "chip-unverified"}`}
                          title={c.url}
                        >
                          <span className="badge-tag">
                            {isVerified ? "✓ Verified" : "⚠ Unverified"}
                          </span>
                          <span className="badge-title">[{c.id}] {c.title}</span>
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

              {item.response.warnings && item.response.warnings.length > 0 && (
                <div className="warnings-tray">
                  {item.response.warnings.map((w, wIdx) => (
                    <div key={wIdx} className="warning-item">
                      ⚠ {w}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && <div className="chat-loading">Searching documents & synthesizing answer...</div>}
      </div>

      <form onSubmit={handleAsk} className="chat-input-form">
        <input
          type="text"
          className="chat-input"
          placeholder="Ask about fares, passes, schedules, or guidelines..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
};
