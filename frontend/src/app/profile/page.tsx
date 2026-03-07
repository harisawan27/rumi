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

// ── Small reusable components ─────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6">
      <h2 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider mb-4">{title}</h2>
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
      <span className="text-xs text-gray-500">{label}</span>
      {editing ? (
        <div className="flex flex-col gap-2">
          {multiline ? (
            <textarea
              rows={3}
              className="bg-gray-800 border border-cyan-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none resize-none"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
          ) : (
            <input
              className="bg-gray-800 border border-cyan-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
          )}
          <div className="flex gap-2">
            <button onClick={save} disabled={saving} className="text-xs px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 rounded-lg disabled:opacity-40">
              {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => { setDraft(value); setEditing(false); }} className="text-xs px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-2 group">
          <p className="text-sm text-white">{value || <span className="text-gray-600 italic">Not set</span>}</p>
          <button
            onClick={() => { setDraft(value); setEditing(true); }}
            className="text-xs text-gray-500 hover:text-cyan-400 sm:opacity-0 sm:group-hover:opacity-100 transition whitespace-nowrap flex-shrink-0"
          >
            Edit
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
      <span className="text-xs text-gray-500">{label}</span>
      <div className="flex gap-2 flex-wrap">
        {(editing ? draft : tags).map((t) => (
          <span key={t} className="flex items-center gap-1 bg-cyan-900/40 text-cyan-300 text-xs px-2 py-1 rounded-full">
            {t}
            {editing && (
              <button onClick={() => setDraft((d) => d.filter((x) => x !== t))} className="hover:text-white">&times;</button>
            )}
          </span>
        ))}
        {!editing && tags.length === 0 && <span className="text-gray-600 italic text-sm">Not set</span>}
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <input
              className="flex-1 bg-gray-800 border border-cyan-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none"
              placeholder="Add tag, press Enter"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
            />
            <button onClick={add} className="px-3 py-2 bg-gray-700 rounded-lg text-sm">Add</button>
          </div>
          <div className="flex gap-2">
            <button onClick={save} disabled={saving} className="text-xs px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 rounded-lg disabled:opacity-40">
              {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => { setDraft(tags); setEditing(false); }} className="text-xs px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => { setDraft(tags); setEditing(true); }} className="text-xs text-cyan-600 hover:text-cyan-400 self-start">
          Edit tags
        </button>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

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
    // Strip Firestore server fields that can't round-trip as JSON
    const { last_updated, user_id, ...payload } = merged as Record<string, unknown>;
    void last_updated; void user_id;
    await saveIdentity(payload);
    setIdentity(merged);
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </main>
    );
  }

  if (!identity) return null;

  const projects = (identity.projects as Project[] | undefined) ?? [];
  const interests = (identity.interests as string[] | undefined) ?? [];
  const roles = (identity.roles as string[] | undefined) ?? [];
  const focusBreakers = (identity.focus_breakers as string[] | undefined) ?? [];

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-2xl mx-auto px-4 py-10">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">Your Memory</h1>
            <p className="text-gray-500 text-sm mt-1">
              Everything Rumi knows about you. Hover any field to edit.
            </p>
          </div>
          <a
            href="/dashboard"
            className="text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg px-4 py-2 hover:bg-gray-800 transition"
          >
            ← Dashboard
          </a>
        </div>

        <div className="flex flex-col gap-4">

          {/* Personal */}
          <Section title="Personal">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <EditableText label="First name" value={String(identity.name ?? "")} onSave={(v) => patch({ name: v })} />
              <EditableText label="Full name" value={String(identity.full_name ?? "")} onSave={(v) => patch({ full_name: v })} />
              <EditableText label="Age" value={String(identity.age ?? "")} onSave={(v) => patch({ age: Number(v) })} />
              <EditableText label="Location" value={String(identity.location ?? "")} onSave={(v) => patch({ location: v })} />
            </div>
            <div className="mt-4">
              <EditableText label="Context / background" value={String(identity.student_context ?? "")} onSave={(v) => patch({ student_context: v })} multiline />
            </div>
            <div className="mt-4">
              <TagsEditor label="Roles" tags={roles} onSave={(v) => patch({ roles: v })} />
            </div>
          </Section>

          {/* Projects */}
          <Section title="Active Projects">
            <div className="flex flex-col gap-4">
              {projects.map((p, i) => (
                <div key={i} className="flex flex-col gap-3 bg-gray-800/40 rounded-xl p-4 border border-gray-700">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-cyan-400 font-medium">Project {i + 1}</span>
                    <button
                      onClick={() => {
                        const updated = projects.filter((_, j) => j !== i);
                        patch({ projects: updated });
                      }}
                      className="text-xs text-gray-600 hover:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                  <EditableText label="Name" value={p.name} onSave={(v) => {
                    const updated = [...projects]; updated[i] = { ...p, name: v };
                    return patch({ projects: updated });
                  }} />
                  <EditableText label="Status" value={p.status} onSave={(v) => {
                    const updated = [...projects]; updated[i] = { ...p, status: v };
                    return patch({ projects: updated });
                  }} />
                  <EditableText label="Pain point / context" value={p.context} onSave={(v) => {
                    const updated = [...projects]; updated[i] = { ...p, context: v };
                    return patch({ projects: updated });
                  }} multiline />
                </div>
              ))}
              {projects.length < 5 && (
                <button
                  onClick={() => patch({ projects: [...projects, { name: "", status: "", context: "" }] })}
                  className="text-sm text-cyan-600 hover:text-cyan-400 border border-dashed border-gray-700 rounded-xl py-3 hover:border-cyan-700 transition"
                >
                  + Add project
                </button>
              )}
            </div>
          </Section>

          {/* Interests & Goals */}
          <Section title="Interests & Goals">
            <div className="flex flex-col gap-4">
              <TagsEditor label="Interests & passions" tags={interests} onSave={(v) => patch({ interests: v })} />
              <EditableText label="Immediate goal" value={String(identity.immediate_goal ?? "")} onSave={(v) => patch({ immediate_goal: v })} multiline />
              <EditableText label="Long-term goal" value={String(identity.long_term_goal ?? "")} onSave={(v) => patch({ long_term_goal: v })} multiline />
              <EditableText label="Driving fear" value={String(identity.driving_fear ?? "")} onSave={(v) => patch({ driving_fear: v })} multiline />
            </div>
          </Section>

          {/* Work style */}
          <Section title="How You Work">
            <div className="flex flex-col gap-4">
              <EditableText label="Work style" value={String(identity.work_style ?? "")} onSave={(v) => patch({ work_style: v })} multiline />
              <TagsEditor label="Focus breakers" tags={focusBreakers} onSave={(v) => patch({ focus_breakers: v })} />
              <EditableText label="How Rumi should talk to you" value={String(identity.communication_preference ?? "")} onSave={(v) => patch({ communication_preference: v })} multiline />
              <EditableText label="Preferred break" value={String(identity.wellness_trigger ?? "")} onSave={(v) => patch({ wellness_trigger: v })} multiline />
            </div>
          </Section>

          {/* Culture & Faith */}
          <Section title="Culture & Faith">
            <div className="flex flex-col gap-4">
              <EditableText label="Faith / religion" value={String(identity.faith ?? "")} onSave={(v) => patch({ faith: v })} />
              <EditableText label="Prayer / schedule Rumi should respect" value={String(identity.salah_awareness ?? "")} onSave={(v) => patch({ salah_awareness: v })} multiline />
              <EditableText label="Language learning / cultural goal" value={String(identity.turkish_goal ?? "")} onSave={(v) => patch({ turkish_goal: v })} multiline />
              <EditableText label="Leisure & hobbies" value={String(identity.leisure ?? "")} onSave={(v) => patch({ leisure: v })} multiline />
            </div>
          </Section>

        </div>

        <p className="text-center text-gray-600 text-xs mt-8">
          Changes save instantly to Rumi&apos;s memory. Active sessions pick them up next restart.
        </p>
      </div>
    </main>
  );
}
