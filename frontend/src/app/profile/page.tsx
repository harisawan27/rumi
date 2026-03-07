"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getIdentity, saveIdentity, verifyAuth } from "@/services/session";

type Identity = Record<string, unknown>;

interface Project {
  name: string;
  status: string;
  context: string;
}

// ── Reusable components ───────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rumi-card">
      <p className="uppercase-label mb-4" style={{ color: "var(--gold)" }}>{title}</p>
      {children}
    </div>
  );
}

function EditableText({
  label, value, onSave, multiline = false,
}: { label: string; value: string; onSave: (v: string) => Promise<void>; multiline?: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    await onSave(draft);
    setSaving(false);
    setEditing(false);
  }

  return (
    <div className="flex flex-col gap-1">
      <span className="uppercase-label" style={{ fontSize: "0.6rem" }}>{label}</span>
      {editing ? (
        <div className="flex flex-col gap-2">
          {multiline ? (
            <textarea
              rows={3}
              className="rumi-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
          ) : (
            <input
              className="rumi-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
          )}
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="btn-primary"
              style={{ fontSize: "0.75rem", padding: "0.375rem 0.875rem" }}
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={() => { setDraft(value); setEditing(false); }}
              className="btn-ghost"
              style={{ fontSize: "0.75rem", padding: "0.375rem 0.875rem" }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm" style={{ color: value ? "var(--text)" : "var(--muted)", fontStyle: value ? "normal" : "italic" }}>
            {value || "Not set"}
          </p>
          <button
            onClick={() => { setDraft(value); setEditing(true); }}
            className="btn-icon flex-shrink-0"
            style={{ width: 28, height: 28, borderRadius: 6 }}
            title={`Edit ${label}`}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}

function TagsEditor({
  label, tags, onSave,
}: { label: string; tags: string[]; onSave: (tags: string[]) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>(tags);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

  function add() {
    const v = input.trim();
    if (v && !draft.includes(v)) setDraft((d) => [...d, v]);
    setInput("");
  }

  async function save() {
    setSaving(true);
    await onSave(draft);
    setSaving(false);
    setEditing(false);
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="uppercase-label" style={{ fontSize: "0.6rem" }}>{label}</span>
      <div className="flex gap-2 flex-wrap min-h-[24px]">
        {(editing ? draft : tags).map((t) => (
          <span key={t} className="rumi-tag">
            {t}
            {editing && (
              <button
                onClick={() => setDraft((d) => d.filter((x) => x !== t))}
                style={{ color: "var(--gold-dim)", marginLeft: 2 }}
              >
                &times;
              </button>
            )}
          </span>
        ))}
        {!editing && tags.length === 0 && (
          <span className="text-sm italic" style={{ color: "var(--muted)" }}>Not set</span>
        )}
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <input
              className="rumi-input flex-1"
              placeholder="Add tag, press Enter"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
            />
            <button
              onClick={add}
              className="btn-ghost"
              style={{ padding: "0.5rem 0.875rem", fontSize: "0.8125rem" }}
            >
              Add
            </button>
          </div>
          <div className="flex gap-2">
            <button
              onClick={save}
              disabled={saving}
              className="btn-primary"
              style={{ fontSize: "0.75rem", padding: "0.375rem 0.875rem" }}
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={() => { setDraft(tags); setEditing(false); }}
              className="btn-ghost"
              style={{ fontSize: "0.75rem", padding: "0.375rem 0.875rem" }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => { setDraft(tags); setEditing(true); }}
          className="btn-icon self-start"
          style={{ width: 28, height: 28, borderRadius: 6 }}
          title={`Edit ${label}`}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        </button>
      )}
    </div>
  );
}

function ProjectCard({
  index, project, onRemove, onSaveName, onSaveStatus, onSaveContext,
}: {
  index: number;
  project: Project;
  onRemove: () => void;
  onSaveName: (v: string) => Promise<void>;
  onSaveStatus: (v: string) => Promise<void>;
  onSaveContext: (v: string) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div
      className="flex flex-col gap-3 rounded-xl p-4"
      style={{ background: "var(--surface-2)", border: `1px solid ${confirming ? "var(--error)" : "var(--border)"}`, transition: "border-color 0.2s" }}
    >
      <div className="flex items-center justify-between">
        <span className="uppercase-label" style={{ color: "var(--gold)" }}>Project {index + 1}</span>

        {confirming ? (
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: "var(--error)" }}>Remove?</span>
            <button
              onClick={onRemove}
              className="btn-primary"
              style={{ fontSize: "0.72rem", padding: "0.25rem 0.75rem", background: "var(--error)", color: "#fff" }}
            >
              Yes, remove
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="btn-ghost"
              style={{ fontSize: "0.72rem", padding: "0.25rem 0.75rem" }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="btn-icon"
            style={{ width: 28, height: 28, borderRadius: 6, color: "var(--error)", borderColor: "rgba(248,113,113,0.2)" }}
            title="Remove project"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
              <path d="M10 11v6M14 11v6" />
              <path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" />
            </svg>
          </button>
        )}
      </div>

      <EditableText label="Name" value={project.name} onSave={onSaveName} />
      <EditableText label="Status" value={project.status} onSave={onSaveStatus} />
      <EditableText label="Pain point / context" value={project.context} onSave={onSaveContext} multiline />
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    verifyAuth()
      .then(() => getIdentity())
      .then((id) => {
        if (!id) { router.push("/onboarding"); return; }
        setIdentity(id);
      })
      .catch(() => router.push("/"))
      .finally(() => setLoading(false));
  }, [router]);

  async function patch(updates: Partial<Identity>) {
    if (!identity) return;
    const merged = { ...identity, ...updates };
    const { last_updated, user_id, ...payload } = merged as Record<string, unknown>;
    void last_updated; void user_id;
    await saveIdentity(payload);
    setIdentity(merged);
  }

  if (loading) {
    return (
      <main
        className="min-h-screen flex items-center justify-center"
        style={{ background: "var(--bg)" }}
      >
        <div
          style={{
            width: 28, height: 28,
            borderRadius: "50%",
            border: "2px solid var(--gold)",
            borderTopColor: "transparent",
            animation: "spin 0.8s linear infinite",
          }}
        />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </main>
    );
  }

  if (!identity) return null;

  const projects = (identity.projects as Project[] | undefined) ?? [];
  const interests = (identity.interests as string[] | undefined) ?? [];
  const roles = (identity.roles as string[] | undefined) ?? [];
  const focusBreakers = (identity.focus_breakers as string[] | undefined) ?? [];

  return (
    <main
      className="dot-grid noise-overlay min-h-screen"
      style={{ background: "var(--bg)", color: "var(--text)" }}
    >
      <div className="max-w-2xl mx-auto px-4 py-10">

        {/* Header */}
        <div className="flex items-center justify-between mb-8 animate-fade-up">
          <div>
            <h1
              className="font-display text-gold"
              style={{ fontSize: "2rem", fontWeight: 300, letterSpacing: "0.04em" }}
            >
              Your Memory
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
              Everything Rumi knows about you.
            </p>
          </div>
          <a href="/dashboard" className="btn-ghost" style={{ fontSize: "0.8125rem" }}>
            ← Dashboard
          </a>
        </div>

        <div className="flex flex-col gap-4">

          {/* Personal */}
          <div className="animate-fade-up delay-100">
            <Section title="Personal">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <EditableText label="First name" value={String(identity.name ?? "")} onSave={(v) => patch({ name: v })} />
                <EditableText label="Full name" value={String(identity.full_name ?? "")} onSave={(v) => patch({ full_name: v })} />
                <EditableText label="Age" value={String(identity.age ?? "")} onSave={(v) => patch({ age: Number(v) })} />
                <EditableText label="Location" value={String(identity.location ?? "")} onSave={(v) => patch({ location: v })} />
              </div>
              <div className="mt-4">
                <EditableText label="Background / context" value={String(identity.student_context ?? "")} onSave={(v) => patch({ student_context: v })} multiline />
              </div>
              <div className="mt-4">
                <TagsEditor label="Roles" tags={roles} onSave={(v) => patch({ roles: v })} />
              </div>
            </Section>
          </div>

          {/* Projects */}
          <div className="animate-fade-up delay-200">
            <Section title="Active Projects">
              <div className="flex flex-col gap-4">
                {projects.map((p, i) => (
                  <ProjectCard
                    key={i}
                    index={i}
                    project={p}
                    onRemove={() => patch({ projects: projects.filter((_, j) => j !== i) })}
                    onSaveName={(v) => { const u = [...projects]; u[i] = { ...p, name: v }; return patch({ projects: u }); }}
                    onSaveStatus={(v) => { const u = [...projects]; u[i] = { ...p, status: v }; return patch({ projects: u }); }}
                    onSaveContext={(v) => { const u = [...projects]; u[i] = { ...p, context: v }; return patch({ projects: u }); }}
                  />
                ))}
                {projects.length < 5 && (
                  <button
                    onClick={() => patch({ projects: [...projects, { name: "", status: "", context: "" }] })}
                    className="btn-ghost w-full"
                    style={{ borderStyle: "dashed" }}
                  >
                    + Add project
                  </button>
                )}
              </div>
            </Section>
          </div>

          {/* Interests & Goals */}
          <div className="animate-fade-up delay-200">
            <Section title="Interests & Goals">
              <div className="flex flex-col gap-4">
                <TagsEditor label="Interests & passions" tags={interests} onSave={(v) => patch({ interests: v })} />
                <EditableText label="Immediate goal" value={String(identity.immediate_goal ?? "")} onSave={(v) => patch({ immediate_goal: v })} multiline />
                <EditableText label="Long-term goal" value={String(identity.long_term_goal ?? "")} onSave={(v) => patch({ long_term_goal: v })} multiline />
                <EditableText label="Driving fear" value={String(identity.driving_fear ?? "")} onSave={(v) => patch({ driving_fear: v })} multiline />
              </div>
            </Section>
          </div>

          {/* Work style */}
          <div className="animate-fade-up delay-300">
            <Section title="How You Work">
              <div className="flex flex-col gap-4">
                <EditableText label="Work style" value={String(identity.work_style ?? "")} onSave={(v) => patch({ work_style: v })} multiline />
                <TagsEditor label="Focus breakers" tags={focusBreakers} onSave={(v) => patch({ focus_breakers: v })} />
                <EditableText label="How Rumi should talk to you" value={String(identity.communication_preference ?? "")} onSave={(v) => patch({ communication_preference: v })} multiline />
                <EditableText label="Preferred break" value={String(identity.wellness_trigger ?? "")} onSave={(v) => patch({ wellness_trigger: v })} multiline />
              </div>
            </Section>
          </div>

          {/* Culture & Faith */}
          <div className="animate-fade-up delay-300">
            <Section title="Culture & Faith">
              <div className="flex flex-col gap-4">
                <EditableText label="Faith / religion" value={String(identity.faith ?? "")} onSave={(v) => patch({ faith: v })} />
                <EditableText label="Prayer / schedule Rumi should respect" value={String(identity.salah_awareness ?? "")} onSave={(v) => patch({ salah_awareness: v })} multiline />
                <EditableText label="Language learning / cultural goal" value={String(identity.turkish_goal ?? "")} onSave={(v) => patch({ turkish_goal: v })} multiline />
                <EditableText label="Leisure & hobbies" value={String(identity.leisure ?? "")} onSave={(v) => patch({ leisure: v })} multiline />
              </div>
            </Section>
          </div>

        </div>

        <p className="text-center mt-8 text-xs" style={{ color: "var(--muted)" }}>
          Changes save instantly to Rumi&apos;s memory.
        </p>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </main>
  );
}
