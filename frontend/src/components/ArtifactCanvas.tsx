"use client";

import React, { useEffect, useRef, useState } from "react";

// ── Data model ────────────────────────────────────────────────────────────────
export interface CanvasExchange {
  query: string;
  response: string;
  type: "text" | "code" | "markdown";
  timestamp: string;
  attachment?: { dataUrl: string; name: string };
}

export interface CanvasContent {
  title: string;
  exchanges: CanvasExchange[];
  timestamp: string;
}

interface Props {
  content: CanvasContent | null;
  onDismiss: () => void;
  history?: CanvasContent[];
  historyIndex?: number;
  onNavigate?: (index: number) => void;
  onFollowUp?: (text: string, image?: string | null, attachment?: { dataUrl: string; name: string }) => void;
  isFollowingUp?: boolean;
}

// ── Inline renderer ───────────────────────────────────────────────────────────
function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      return <strong key={i} style={{ color: "var(--text)", fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
      return <code key={i} style={{ background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.18)", borderRadius: 4, padding: "1px 5px", fontSize: "0.82em", color: "var(--teal)", fontFamily: "monospace" }}>{part.slice(1, -1)}</code>;
    return <span key={i}>{part}</span>;
  });
}

// ── Markdown renderer ─────────────────────────────────────────────────────────
function renderMarkdown(body: string): React.ReactNode[] {
  const lines = body.split("\n");
  const out: React.ReactNode[] = [];
  let codeLines: string[] = [];
  let inCode = false;
  let codeLang = "";
  let k = 0;

  const flushCode = () => {
    out.push(
      <pre key={`c${k++}`} style={{ background: "rgba(4,8,15,0.88)", border: "1px solid rgba(34,211,238,0.18)", borderRadius: 8, padding: "12px 14px", overflowX: "auto", margin: "10px 0", fontSize: "0.78rem", lineHeight: 1.65, color: "var(--teal)", fontFamily: "monospace" }}>
        {codeLang && <div style={{ fontSize: "0.56rem", color: "var(--muted)", marginBottom: 7, letterSpacing: "0.12em", textTransform: "uppercase" }}>{codeLang}</div>}
        <code style={{ whiteSpace: "pre", display: "block" }}>{codeLines.join("\n")}</code>
      </pre>
    );
    codeLines = []; codeLang = "";
  };

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) { flushCode(); inCode = false; } else { inCode = true; codeLang = line.slice(3).trim(); }
      continue;
    }
    if (inCode) { codeLines.push(line); continue; }
    if (line.trim() === "") { out.push(<div key={k++} style={{ height: 8 }} />); }
    else if (line.startsWith("### ")) { out.push(<h3 key={k++} style={{ fontSize: "0.88rem", color: "var(--text)", fontWeight: 600, margin: "14px 0 5px" }}>{renderInline(line.slice(4))}</h3>); }
    else if (line.startsWith("## ")) { out.push(<h2 key={k++} style={{ fontSize: "1rem", color: "var(--gold)", fontFamily: "var(--font-cormorant),'Cormorant Garamond',serif", fontWeight: 400, margin: "16px 0 7px", borderBottom: "1px solid rgba(201,168,76,0.15)", paddingBottom: 5 }}>{line.slice(3)}</h2>); }
    else if (line.startsWith("# ")) { out.push(<h1 key={k++} style={{ fontSize: "1.15rem", color: "var(--gold)", fontFamily: "var(--font-cormorant),'Cormorant Garamond',serif", fontWeight: 400, margin: "0 0 12px" }}>{line.slice(2)}</h1>); }
    else if (line.startsWith("- ") || line.startsWith("* ")) {
      out.push(<div key={k++} style={{ display: "flex", gap: 9, alignItems: "flex-start", margin: "3px 0" }}><span style={{ color: "var(--teal)", fontSize: "0.58rem", marginTop: 5, flexShrink: 0 }}>◆</span><p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-2)", lineHeight: 1.68 }}>{renderInline(line.slice(2))}</p></div>);
    } else if (/^\d+\.\s/.test(line)) {
      const m = line.match(/^(\d+)\.\s(.+)/);
      if (m) out.push(<div key={k++} style={{ display: "flex", gap: 10, alignItems: "flex-start", margin: "3px 0" }}><span style={{ color: "var(--gold)", fontSize: "0.72rem", fontWeight: 700, flexShrink: 0, minWidth: 18 }}>{m[1]}.</span><p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-2)", lineHeight: 1.68 }}>{renderInline(m[2])}</p></div>);
    } else {
      out.push(<p key={k++} style={{ margin: "3px 0", fontSize: "0.84rem", color: "var(--text-2)", lineHeight: 1.72 }}>{renderInline(line)}</p>);
    }
  }
  if (inCode && codeLines.length > 0) flushCode();
  return out;
}

// ── Single exchange block ─────────────────────────────────────────────────────
function ExchangeBlock({ ex, isLatest }: { ex: CanvasExchange; isLatest: boolean }) {
  return (
    <div style={{ marginBottom: 28, animation: isLatest ? "typeReveal 3.8s ease-out both" : "none" }}>
      <div style={{ marginBottom: 14, paddingBottom: 10, borderBottom: "1px solid rgba(34,211,238,0.08)" }}>
        {ex.timestamp && (
          <span style={{ fontSize: "0.5rem", color: "var(--muted)", letterSpacing: "0.14em", textTransform: "uppercase", display: "block", marginBottom: 4 }}>
            {ex.timestamp}
          </span>
        )}
        {ex.attachment && (
          <div style={{ marginBottom: 8 }}>
            {ex.attachment.dataUrl.startsWith("data:image") ? (
              <img src={ex.attachment.dataUrl} alt={ex.attachment.name} style={{ maxHeight: 100, maxWidth: "100%", borderRadius: 6, border: "1px solid rgba(34,211,238,0.2)", objectFit: "cover" }} />
            ) : (
              <div style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.18)", borderRadius: 6, padding: "4px 10px" }}>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
                <span style={{ fontSize: "0.68rem", color: "var(--teal)" }}>{ex.attachment.name}</span>
              </div>
            )}
          </div>
        )}
        <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--teal)", lineHeight: 1.65, opacity: 0.85, fontStyle: "italic" }}>
          &ldquo;{ex.query}&rdquo;
        </p>
      </div>
      {ex.type === "code" ? (
        <pre style={{ margin: 0, background: "rgba(4,8,15,0.9)", border: "1px solid rgba(34,211,238,0.18)", borderRadius: 10, padding: "16px 18px", overflowX: "auto", fontSize: "0.79rem", color: "var(--teal)", lineHeight: 1.65, fontFamily: "monospace", whiteSpace: "pre" }}>
          <code>{ex.response}</code>
        </pre>
      ) : ex.type === "markdown" ? (
        <div>{renderMarkdown(ex.response)}</div>
      ) : (
        <p style={{ margin: 0, fontSize: "0.87rem", color: "var(--text-2)", lineHeight: 1.78 }}>{ex.response}</p>
      )}
    </div>
  );
}

// ── Follow-up input bar ───────────────────────────────────────────────────────
function FollowUpBar({ onFollowUp, isFollowingUp }: {
  onFollowUp: (text: string, image?: string | null, attachment?: { dataUrl: string; name: string }) => void;
  isFollowingUp?: boolean;
}) {
  const [text, setText] = useState("");
  const [attachment, setAttachment] = useState<{ dataUrl: string; name: string } | null>(null);
  const [listening, setListening] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function send(t: string) {
    const trimmed = t.trim();
    if (!trimmed) return;
    const imgB64 = attachment?.dataUrl.startsWith("data:image") ? attachment.dataUrl.split(",")[1] : null;
    onFollowUp(trimmed, imgB64, attachment ?? undefined);
    setText("");
    setAttachment(null);
  }

  function startVoice() {
    const SR =
      (window as unknown as { SpeechRecognition?: typeof SpeechRecognition }).SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-US";
    rec.onstart = () => setListening(true);
    rec.onend = () => setListening(false);
    rec.onresult = (e: SpeechRecognitionEvent) => {
      const t = e.results[0]?.[0]?.transcript?.trim();
      if (t) send(t);
    };
    rec.onerror = () => setListening(false);
    rec.start();
  }

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    if (file.type.startsWith("image/")) {
      reader.onload = () => setAttachment({ dataUrl: reader.result as string, name: file.name });
      reader.readAsDataURL(file);
    } else {
      reader.onload = () => setAttachment({ dataUrl: `data:text/plain,${encodeURIComponent(reader.result as string)}`, name: file.name });
      reader.readAsText(file);
    }
    e.target.value = "";
  }

  return (
    <div style={{ borderTop: "1px solid rgba(34,211,238,0.1)", background: "rgba(4,8,15,0.5)", padding: "10px 12px", flexShrink: 0 }}>
      {attachment && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          {attachment.dataUrl.startsWith("data:image") ? (
            <img src={attachment.dataUrl} alt={attachment.name} style={{ height: 44, width: 44, objectFit: "cover", borderRadius: 5, border: "1px solid rgba(34,211,238,0.25)" }} />
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 5, background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.18)", borderRadius: 5, padding: "3px 9px" }}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
              <span style={{ fontSize: "0.66rem", color: "var(--teal)", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{attachment.name}</span>
            </div>
          )}
          <button onClick={() => setAttachment(null)} style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: "0.75rem", padding: 0 }}>✕</button>
        </div>
      )}
      <div style={{ display: "flex", gap: 7, alignItems: "center" }}>
        <input ref={fileRef} type="file" accept="image/*,.txt,.md,.py,.js,.ts,.json,.csv" style={{ display: "none" }} onChange={handleFile} />
        <button
          onClick={() => fileRef.current?.click()}
          title="Attach file or image"
          style={{ background: "none", border: "1px solid rgba(34,211,238,0.18)", borderRadius: 7, padding: "6px 7px", cursor: "pointer", color: "var(--muted)", flexShrink: 0, display: "flex", alignItems: "center", transition: "all 0.15s" }}
          onMouseEnter={e => { e.currentTarget.style.color = "var(--teal)"; e.currentTarget.style.borderColor = "rgba(34,211,238,0.4)"; }}
          onMouseLeave={e => { e.currentTarget.style.color = "var(--muted)"; e.currentTarget.style.borderColor = "rgba(34,211,238,0.18)"; }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>
        </button>
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text); } }}
          placeholder={listening ? "Listening…" : "Ask a follow-up…"}
          disabled={isFollowingUp || listening}
          style={{ flex: 1, background: "rgba(34,211,238,0.04)", border: "1px solid rgba(34,211,238,0.15)", borderRadius: 8, padding: "7px 11px", fontSize: "0.8rem", color: "var(--text)", outline: "none", transition: "border-color 0.15s" }}
          onFocus={e => (e.target.style.borderColor = "rgba(34,211,238,0.4)")}
          onBlur={e => (e.target.style.borderColor = "rgba(34,211,238,0.15)")}
        />
        <button
          onClick={() => send(text)}
          disabled={!text.trim() || isFollowingUp}
          style={{ background: text.trim() ? "rgba(34,211,238,0.12)" : "none", border: "1px solid rgba(34,211,238,0.2)", borderRadius: 7, padding: "6px 10px", cursor: text.trim() ? "pointer" : "default", color: text.trim() ? "var(--teal)" : "var(--muted)", flexShrink: 0, display: "flex", alignItems: "center", transition: "all 0.15s" }}
        >
          {isFollowingUp ? (
            <span style={{ width: 13, height: 13, border: "2px solid rgba(201,168,76,0.3)", borderTopColor: "var(--gold)", borderRadius: "50%", display: "inline-block", animation: "spin 0.8s linear infinite" }} />
          ) : (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          )}
        </button>
        <button
          onClick={startVoice}
          disabled={isFollowingUp}
          title="Voice follow-up"
          style={{ background: listening ? "rgba(34,211,238,0.15)" : "none", border: `1px solid ${listening ? "rgba(34,211,238,0.5)" : "rgba(34,211,238,0.18)"}`, borderRadius: 7, padding: "6px 7px", cursor: "pointer", color: listening ? "var(--teal)" : "var(--muted)", flexShrink: 0, display: "flex", alignItems: "center", transition: "all 0.15s", boxShadow: listening ? "0 0 12px rgba(34,211,238,0.25)" : "none" }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 1a4 4 0 014 4v6a4 4 0 01-8 0V5a4 4 0 014-4z"/>
            <path d="M19 10a1 1 0 00-2 0 5 5 0 01-10 0 1 1 0 00-2 0 7 7 0 006 6.92V19H9a1 1 0 000 2h6a1 1 0 000-2h-2v-2.08A7 7 0 0019 10z"/>
          </svg>
        </button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ArtifactCanvas({ content, onDismiss, history = [], historyIndex = 0, onNavigate, onFollowUp, isFollowingUp }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const total = history.length;
  const isLatest = historyIndex === total - 1;

  useEffect(() => {
    if (content) setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }), 80);
  }, [content?.exchanges.length]);

  useEffect(() => {
    if (content) scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content?.title]);

  const corners = [
    { style: { top: 0, left: 0, borderTop: "1.5px solid rgba(34,211,238,0.45)", borderLeft: "1.5px solid rgba(34,211,238,0.45)", borderRadius: "4px 0 0 0" } },
    { style: { top: 0, right: 0, borderTop: "1.5px solid rgba(34,211,238,0.45)", borderRight: "1.5px solid rgba(34,211,238,0.45)", borderRadius: "0 4px 0 0" } },
    { style: { bottom: 0, left: 0, borderBottom: "1.5px solid rgba(34,211,238,0.45)", borderLeft: "1.5px solid rgba(34,211,238,0.45)", borderRadius: "0 0 0 4px" } },
    { style: { bottom: 0, right: 0, borderBottom: "1.5px solid rgba(34,211,238,0.45)", borderRight: "1.5px solid rgba(34,211,238,0.45)", borderRadius: "0 0 4px 0" } },
  ] as const;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "rgba(4,8,15,0.55)", backdropFilter: "blur(28px)", WebkitBackdropFilter: "blur(28px)", borderLeft: "1px solid rgba(34,211,238,0.1)", position: "relative", overflow: "hidden" }}>

      {corners.map((c, i) => <div key={i} style={{ position: "absolute", width: 14, height: 14, ...c.style }} />)}

      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "11px 16px", borderBottom: "1px solid rgba(34,211,238,0.07)", flexShrink: 0, background: "rgba(4,8,15,0.3)" }}>
        <div style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--teal)", boxShadow: "0 0 8px var(--teal)", flexShrink: 0, animation: "statusPulse 2s ease-in-out infinite" }} />
        <span style={{ fontSize: "0.52rem", letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--teal)", fontWeight: 500, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {content ? `[RUMI CORE] :: ${content.title}` : "[RUMI CORE] :: Projecting..."}
        </span>
        {content && content.exchanges.length > 1 && (
          <span style={{ fontSize: "0.48rem", color: "var(--muted)", background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.15)", borderRadius: 99, padding: "2px 7px" }}>
            {content.exchanges.length} exchanges
          </span>
        )}
        <button onClick={onDismiss} style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: "0.7rem", padding: "2px 5px", lineHeight: 1, borderRadius: 3, transition: "color 0.15s" }} onMouseEnter={e => (e.currentTarget.style.color = "var(--text)")} onMouseLeave={e => (e.currentTarget.style.color = "var(--muted)")}>✕</button>
      </div>

      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "clamp(12px,3vw,22px) clamp(14px,3vw,24px) 16px" }}>
        {content ? (
          content.exchanges.map((ex, idx) => (
            <ExchangeBlock key={idx} ex={ex} isLatest={isLatest && idx === content.exchanges.length - 1} />
          ))
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 20, opacity: 0.22 }}>
            <div style={{ position: "relative", width: 56, height: 56, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ position: "absolute", inset: 0, border: "1px solid rgba(34,211,238,0.6)", borderRadius: "50%", animation: "canvasPing 2.4s ease-out infinite" }} />
              <div style={{ position: "absolute", inset: 8, border: "1px solid rgba(34,211,238,0.4)", borderRadius: "50%", animation: "canvasPing 2.4s ease-out 0.7s infinite" }} />
              <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--teal)" }} />
            </div>
            <p style={{ fontSize: "0.58rem", color: "var(--muted)", letterSpacing: "0.2em", textTransform: "uppercase", margin: 0 }}>Awaiting projection</p>
          </div>
        )}
      </div>

      {content && onFollowUp && <FollowUpBar onFollowUp={onFollowUp} isFollowingUp={isFollowingUp} />}

      {total > 1 && onNavigate && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 14px", borderTop: "1px solid rgba(34,211,238,0.07)", flexShrink: 0, background: "rgba(4,8,15,0.3)" }}>
          <button onClick={() => onNavigate(historyIndex - 1)} disabled={historyIndex === 0} style={{ background: "none", border: "1px solid rgba(34,211,238,0.2)", borderRadius: 5, color: historyIndex === 0 ? "var(--muted)" : "var(--teal)", cursor: historyIndex === 0 ? "default" : "pointer", padding: "3px 8px", fontSize: "0.72rem", opacity: historyIndex === 0 ? 0.35 : 1 }}>←</button>
          <p style={{ flex: 1, margin: 0, fontSize: "0.5rem", color: "var(--muted)", letterSpacing: "0.12em", textAlign: "center" }}>{historyIndex + 1} / {total}</p>
          <button onClick={() => onNavigate(historyIndex + 1)} disabled={isLatest} style={{ background: "none", border: "1px solid rgba(34,211,238,0.2)", borderRadius: 5, color: isLatest ? "var(--muted)" : "var(--teal)", cursor: isLatest ? "default" : "pointer", padding: "3px 8px", fontSize: "0.72rem", opacity: isLatest ? 0.35 : 1 }}>→</button>
        </div>
      )}

      <style>{`
        @keyframes canvasPing { 0% { transform:scale(1); opacity:0.8; } 100% { transform:scale(2.6); opacity:0; } }
        @keyframes typeReveal { 0% { clip-path:inset(0 0 100% 0); opacity:0.4; } 8% { opacity:1; } 100% { clip-path:inset(0 0 0% 0); opacity:1; } }
      `}</style>
    </div>
  );
}
