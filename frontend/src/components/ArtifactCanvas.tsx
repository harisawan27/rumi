"use client";

import { useEffect, useRef } from "react";

export interface CanvasContent {
  title: string;
  body: string;
  type: "text" | "code" | "markdown";
}

interface Props {
  content: CanvasContent | null;
  onDismiss: () => void;
}

// ── Inline renderer — bold + inline code ─────────────────────────────────────
function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={i} style={{ color: "var(--text)", fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={i} style={{
          background: "rgba(34,211,238,0.07)", border: "1px solid rgba(34,211,238,0.18)",
          borderRadius: 4, padding: "1px 5px", fontSize: "0.82em",
          color: "var(--teal)", fontFamily: "monospace",
        }}>{part.slice(1, -1)}</code>
      );
    }
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
      <pre key={`c${k++}`} style={{
        background: "rgba(4,8,15,0.88)", border: "1px solid rgba(34,211,238,0.18)",
        borderRadius: 8, padding: "12px 14px", overflowX: "auto", margin: "10px 0",
        fontSize: "0.78rem", lineHeight: 1.65, color: "var(--teal)", fontFamily: "monospace",
      }}>
        {codeLang && (
          <div style={{ fontSize: "0.56rem", color: "var(--muted)", marginBottom: 7, letterSpacing: "0.12em", textTransform: "uppercase" }}>
            {codeLang}
          </div>
        )}
        <code style={{ whiteSpace: "pre", display: "block" }}>{codeLines.join("\n")}</code>
      </pre>
    );
    codeLines = [];
    codeLang = "";
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCode) { flushCode(); inCode = false; }
      else { inCode = true; codeLang = line.slice(3).trim(); }
      continue;
    }
    if (inCode) { codeLines.push(line); continue; }

    if (line.trim() === "") {
      out.push(<div key={k++} style={{ height: 8 }} />);
    } else if (line.startsWith("### ")) {
      out.push(<h3 key={k++} style={{ fontSize: "0.88rem", color: "var(--text)", fontWeight: 600, margin: "14px 0 5px", letterSpacing: "0.02em" }}>{renderInline(line.slice(4))}</h3>);
    } else if (line.startsWith("## ")) {
      out.push(<h2 key={k++} style={{ fontSize: "1rem", color: "var(--gold)", fontFamily: "var(--font-cormorant),'Cormorant Garamond',serif", fontWeight: 400, letterSpacing: "0.04em", margin: "16px 0 7px", borderBottom: "1px solid rgba(201,168,76,0.15)", paddingBottom: 5 }}>{line.slice(3)}</h2>);
    } else if (line.startsWith("# ")) {
      out.push(<h1 key={k++} style={{ fontSize: "1.15rem", color: "var(--gold)", fontFamily: "var(--font-cormorant),'Cormorant Garamond',serif", fontWeight: 400, letterSpacing: "0.06em", margin: "0 0 12px" }}>{line.slice(2)}</h1>);
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      out.push(
        <div key={k++} style={{ display: "flex", gap: 9, alignItems: "flex-start", margin: "3px 0" }}>
          <span style={{ color: "var(--teal)", fontSize: "0.58rem", marginTop: 5, flexShrink: 0 }}>◆</span>
          <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-2)", lineHeight: 1.68 }}>{renderInline(line.slice(2))}</p>
        </div>
      );
    } else if (/^\d+\.\s/.test(line)) {
      const m = line.match(/^(\d+)\.\s(.+)/);
      if (m) out.push(
        <div key={k++} style={{ display: "flex", gap: 10, alignItems: "flex-start", margin: "3px 0" }}>
          <span style={{ color: "var(--gold)", fontSize: "0.72rem", fontWeight: 700, flexShrink: 0, minWidth: 18 }}>{m[1]}.</span>
          <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-2)", lineHeight: 1.68 }}>{renderInline(m[2])}</p>
        </div>
      );
    } else {
      out.push(<p key={k++} style={{ margin: "3px 0", fontSize: "0.84rem", color: "var(--text-2)", lineHeight: 1.72 }}>{renderInline(line)}</p>);
    }
  }
  if (inCode && codeLines.length > 0) flushCode();
  return out;
}

// ── Component ────────────────────────────────────────────────────────────────
export default function ArtifactCanvas({ content, onDismiss }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (content) scrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content?.title]);

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100%",
      background: "rgba(4,8,15,0.55)", backdropFilter: "blur(28px)",
      WebkitBackdropFilter: "blur(28px)",
      borderLeft: "1px solid rgba(34,211,238,0.1)",
      position: "relative", overflow: "hidden",
    }}>

      {/* Corner accent brackets */}
      <div style={{ position:"absolute", top:0, left:0, width:14, height:14, borderTop:"1.5px solid rgba(34,211,238,0.45)", borderLeft:"1.5px solid rgba(34,211,238,0.45)", borderRadius:"4px 0 0 0" }} />
      <div style={{ position:"absolute", top:0, right:0, width:14, height:14, borderTop:"1.5px solid rgba(34,211,238,0.45)", borderRight:"1.5px solid rgba(34,211,238,0.45)", borderRadius:"0 4px 0 0" }} />
      <div style={{ position:"absolute", bottom:0, left:0, width:14, height:14, borderBottom:"1.5px solid rgba(34,211,238,0.45)", borderLeft:"1.5px solid rgba(34,211,238,0.45)", borderRadius:"0 0 0 4px" }} />
      <div style={{ position:"absolute", bottom:0, right:0, width:14, height:14, borderBottom:"1.5px solid rgba(34,211,238,0.45)", borderRight:"1.5px solid rgba(34,211,238,0.45)", borderRadius:"0 0 4px 0" }} />

      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "11px 16px", borderBottom: "1px solid rgba(34,211,238,0.07)",
        flexShrink: 0, background: "rgba(4,8,15,0.3)",
      }}>
        <div style={{
          width: 5, height: 5, borderRadius: "50%", background: "var(--teal)",
          boxShadow: "0 0 8px var(--teal)", flexShrink: 0,
          animation: "statusPulse 2s ease-in-out infinite",
        }} />
        <span style={{
          fontSize: "0.52rem", letterSpacing: "0.18em", textTransform: "uppercase",
          color: "var(--teal)", fontWeight: 500, flex: 1,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {content ? `[RUMI CORE] :: ${content.title}` : "[RUMI CORE] :: Projecting..."}
        </span>
        <button
          onClick={onDismiss}
          title="Dismiss canvas"
          style={{
            background: "none", border: "none", color: "var(--muted)",
            cursor: "pointer", fontSize: "0.7rem", padding: "2px 5px",
            lineHeight: 1, borderRadius: 3, transition: "color 0.15s",
          }}
          onMouseEnter={e => (e.currentTarget.style.color = "var(--text)")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--muted)")}
        >✕</button>
      </div>

      {/* Scrollable content */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "22px 24px 40px" }}>
        {content ? (
          <div key={content.title} style={{ animation: "typeReveal 3.8s ease-out both" }}>
          {content.type === "code" ? (
            <pre style={{
              margin: 0, background: "rgba(4,8,15,0.9)",
              border: "1px solid rgba(34,211,238,0.18)", borderRadius: 10,
              padding: "16px 18px", overflowX: "auto",
              fontSize: "0.79rem", color: "var(--teal)", lineHeight: 1.65,
              fontFamily: "monospace", whiteSpace: "pre",
            }}>
              <code>{content.body}</code>
            </pre>
          ) : content.type === "markdown" ? (
            <div>{renderMarkdown(content.body)}</div>
          ) : (
            <p style={{ margin: 0, fontSize: "0.87rem", color: "var(--text-2)", lineHeight: 1.78 }}>
              {content.body}
            </p>
          )}
          </div>
        ) : (
          /* Ambient awaiting state */
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", height: "100%", gap: 20, opacity: 0.22,
          }}>
            <div style={{ position: "relative", width: 56, height: 56, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ position:"absolute", inset:0, border:"1px solid rgba(34,211,238,0.6)", borderRadius:"50%", animation:"canvasPing 2.4s ease-out infinite" }} />
              <div style={{ position:"absolute", inset:8, border:"1px solid rgba(34,211,238,0.4)", borderRadius:"50%", animation:"canvasPing 2.4s ease-out 0.7s infinite" }} />
              <div style={{ width:7, height:7, borderRadius:"50%", background:"var(--teal)" }} />
            </div>
            <p style={{ fontSize: "0.58rem", color: "var(--muted)", letterSpacing: "0.2em", textTransform: "uppercase", margin: 0 }}>
              Awaiting projection
            </p>
          </div>
        )}
      </div>

      <style>{`
        @keyframes canvasPing {
          0%   { transform: scale(1);   opacity: 0.8; }
          100% { transform: scale(2.6); opacity: 0;   }
        }
        @keyframes typeReveal {
          0%   { clip-path: inset(0 0 100% 0); opacity: 0.4; }
          8%   { opacity: 1; }
          100% { clip-path: inset(0 0 0% 0);   opacity: 1;   }
        }
      `}</style>
    </div>
  );
}
