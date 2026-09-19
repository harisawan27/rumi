"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getIdentity, saveIdentity, verifyAuth, refreshSessionContext,
  getKnownPeople, addKnownPerson, updateKnownPerson, deleteKnownPerson,
  uploadPersonPhoto, uploadProfilePhoto,
  getMemoryCandidates, confirmMemoryCandidate, rejectMemoryCandidate, dismissMemoryCandidate,
  clearConversationHistory, clearCanvasHistory,
  type KnownPerson, type MemoryCandidate,
} from "@/services/session";

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

// ── Speech Preferences ────────────────────────────────────────────────────────

const COMMON_LANGUAGES = [
  "Urdu", "Spanish", "French", "Arabic", "Hindi",
  "Mandarin", "Portuguese", "German", "Turkish", "Italian",
];

const EXPRESSION_STYLES = [
  { key: "spiritual",      label: "Spiritual expressions",  desc: "Faith-based or awe exclamations natural to your culture" },
  { key: "casual_address", label: "Casual address terms",   desc: "Informal terms of endearment in your language" },
  { key: "slang",          label: "Slang & idioms",         desc: "Local informal phrases and expressions" },
];

function SpeechPrefsEditor({
  identity, patch,
}: { identity: Identity; patch: (u: Partial<Identity>) => Promise<void> }) {
  const lang    = (identity.companion_language as string) ?? "";
  const styles  = (identity.expression_styles  as string[]) ?? [];
  const tone    = (identity.companion_tone     as string) ?? "casual";

  const [customLang, setCustomLang] = useState("");
  const [showCustom, setShowCustom] = useState(false);

  function toggleStyle(key: string) {
    const next = styles.includes(key) ? styles.filter(s => s !== key) : [...styles, key];
    patch({ expression_styles: next });
  }

  function setLang(l: string) {
    patch({ companion_language: l });
    setShowCustom(false);
    setCustomLang("");
  }

  function saveCustomLang() {
    const v = customLang.trim();
    if (v) setLang(v);
  }

  const isCustom = lang && !COMMON_LANGUAGES.includes(lang);

  return (
    <div className="rumi-card" style={{ borderColor: "rgba(34,211,238,0.2)", background: "rgba(34,211,238,0.02)" }}>
      <p className="uppercase-label mb-1" style={{ color: "var(--teal)" }}>How Rumi Speaks With You</p>
      <p className="text-xs mb-5" style={{ color: "var(--muted)", lineHeight: 1.6 }}>
        English is always the base. Add a companion language and choose how Rumi mixes it in.
      </p>

      {/* Companion language */}
      <div className="mb-5">
        <span className="uppercase-label mb-2 block" style={{ fontSize: "0.6rem" }}>Companion language</span>
        <div className="flex flex-wrap gap-2 mb-2">
          <button
            onClick={() => setLang("")}
            className="rumi-tag"
            style={{
              cursor: "pointer", padding: "4px 12px", fontSize: "0.72rem",
              background: !lang ? "rgba(34,211,238,0.12)" : "var(--surface-2)",
              borderColor: !lang ? "var(--teal)" : "var(--border)",
              transition: "all 0.15s",
            }}
          >
            English only
          </button>
          {COMMON_LANGUAGES.map(l => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className="rumi-tag"
              style={{
                cursor: "pointer", padding: "4px 12px", fontSize: "0.72rem",
                background: lang === l ? "rgba(34,211,238,0.12)" : "var(--surface-2)",
                borderColor: lang === l ? "var(--teal)" : "var(--border)",
                transition: "all 0.15s",
              }}
            >
              {l}
            </button>
          ))}
          <button
            onClick={() => setShowCustom(v => !v)}
            className="rumi-tag"
            style={{
              cursor: "pointer", padding: "4px 12px", fontSize: "0.72rem",
              background: showCustom || isCustom ? "rgba(34,211,238,0.12)" : "var(--surface-2)",
              borderColor: showCustom || isCustom ? "var(--teal)" : "var(--border)",
              transition: "all 0.15s",
            }}
          >
            {isCustom ? lang : "Other…"}
          </button>
        </div>

        {showCustom && (
          <div className="flex gap-2">
            <input
              className="rumi-input flex-1"
              placeholder="Type your language"
              value={customLang}
              onChange={e => setCustomLang(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); saveCustomLang(); } }}
              autoFocus
            />
            <button
              onClick={saveCustomLang}
              className="btn-primary"
              style={{ fontSize: "0.75rem", padding: "0.375rem 0.875rem" }}
            >
              Set
            </button>
          </div>
        )}

        {lang && (
          <p className="text-xs mt-2" style={{ color: "var(--teal)" }}>
            Rumi will mix English + {lang}
          </p>
        )}
      </div>

      {/* Expression styles */}
      <div className="mb-5">
        <span className="uppercase-label mb-2 block" style={{ fontSize: "0.6rem" }}>
          Expression style{" "}
          <span style={{ color: "var(--muted)", fontWeight: 400, textTransform: "none" }}>
            — pick any combination
          </span>
        </span>
        <div className="flex flex-col gap-2">
          {EXPRESSION_STYLES.map(({ key, label, desc }) => {
            const active = styles.includes(key);
            return (
              <button
                key={key}
                onClick={() => toggleStyle(key)}
                style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 14px", borderRadius: 10, cursor: "pointer",
                  background: active ? "rgba(34,211,238,0.08)" : "var(--surface-2)",
                  border: `1px solid ${active ? "rgba(34,211,238,0.35)" : "var(--border)"}`,
                  transition: "all 0.15s", textAlign: "left",
                }}
              >
                <div style={{
                  width: 16, height: 16, borderRadius: 4, flexShrink: 0,
                  border: `2px solid ${active ? "var(--teal)" : "var(--border)"}`,
                  background: active ? "var(--teal)" : "transparent",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  transition: "all 0.15s",
                }}>
                  {active && (
                    <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6l3 3 5-5" stroke="#04080f" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </div>
                <div>
                  <p className="text-sm" style={{ color: active ? "var(--text)" : "var(--text-2)", fontWeight: active ? 500 : 400 }}>
                    {label}
                  </p>
                  <p style={{ fontSize: "0.68rem", color: "var(--muted)", marginTop: 1 }}>{desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tone */}
      <div>
        <span className="uppercase-label mb-2 block" style={{ fontSize: "0.6rem" }}>Tone</span>
        <div className="flex gap-2">
          {[
            { key: "casual",       label: "Casual friend" },
            { key: "professional", label: "Professional"  },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => patch({ companion_tone: key })}
              style={{
                padding: "6px 18px", borderRadius: 8, fontSize: "0.8rem", cursor: "pointer",
                background: tone === key ? "rgba(34,211,238,0.12)" : "var(--surface-2)",
                border: `1px solid ${tone === key ? "rgba(34,211,238,0.4)" : "var(--border)"}`,
                color: tone === key ? "var(--teal)" : "var(--text-2)",
                transition: "all 0.15s",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Profile Photo Uploader ────────────────────────────────────────────────────

function ProfilePhotoUploader({
  uid, currentUrl, onSaved,
}: { uid: string; currentUrl: string; onSaved: (url: string) => Promise<void> }) {
  const [uploading, setUploading] = useState(false);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const url = await uploadProfilePhoto(uid, file);
      await onSaved(url);
    } catch { /* silent */ } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex items-center gap-4">
      <div style={{
        width: 72, height: 72, borderRadius: "50%", overflow: "hidden", flexShrink: 0,
        border: "2px solid var(--gold)", background: "var(--surface-2)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {currentUrl
          ? <img src={currentUrl} alt="Profile" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          : <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" strokeWidth="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
        }
      </div>
      <div className="flex flex-col gap-1">
        <p className="text-sm" style={{ color: "var(--text-2)" }}>
          {currentUrl ? "Rumi uses this to recognise you" : "Upload so Rumi can recognise you"}
        </p>
        <label className="btn-ghost" style={{ fontSize: "0.75rem", padding: "0.3rem 0.875rem", cursor: "pointer" }}>
          {uploading ? "Uploading…" : currentUrl ? "Change photo" : "Upload photo"}
          <input type="file" accept="image/*" onChange={handleFile} style={{ display: "none" }} disabled={uploading} />
        </label>
      </div>
    </div>
  );
}

// ── Known People Editor ───────────────────────────────────────────────────────

const RELATIONSHIPS = ["Partner", "Parent", "Sibling", "Child", "Friend", "Colleague", "Roommate", "Other"];

function KnownPeopleEditor({ uid }: { uid: string }) {
  const [people, setPeople]   = useState<KnownPerson[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding]   = useState(false);
  const [saving, setSaving]   = useState(false);

  // New person form state
  const [form, setForm] = useState({ name: "", relationship: "Friend", notes: "", photo_url: "" });
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState("");

  useEffect(() => {
    getKnownPeople().then(setPeople).finally(() => setLoading(false));
  }, []);

  function handlePhotoSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoFile(file);
    setPhotoPreview(URL.createObjectURL(file));
  }

  async function handleAdd() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const tempId = Date.now().toString();
      let photoUrl = "";
      if (photoFile) {
        photoUrl = await uploadPersonPhoto(uid, photoFile, tempId);
      }
      const id = await addKnownPerson({ ...form, photo_url: photoUrl });
      // Optimistic insert — person appears immediately without reload
      const newPerson: KnownPerson = {
        id,
        name: form.name,
        relationship: form.relationship,
        photo_url: photoUrl,
        notes: form.notes,
        added_by: "manual",
        status: "verified",
        added_at: new Date().toISOString(),
        last_seen: null,
        interaction_count: 0,
      };
      setPeople(prev => [...prev, newPerson]);
      setForm({ name: "", relationship: "Friend", notes: "", photo_url: "" });
      setPhotoFile(null);
      setPhotoPreview("");
      setAdding(false);
    } catch { /* silent */ } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    await deleteKnownPerson(id);
    setPeople(p => p.filter(x => x.id !== id));
  }

  function formatDate(iso: string | null) {
    if (!iso) return "Never";
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  return (
    <div className="rumi-card" style={{ borderColor: "rgba(201,168,76,0.2)", background: "rgba(201,168,76,0.02)" }}>
      <div className="flex items-center justify-between mb-1">
        <p className="uppercase-label" style={{ color: "var(--gold)" }}>Known People</p>
        {!adding && (
          <button onClick={() => setAdding(true)} className="btn-ghost"
            style={{ fontSize: "0.72rem", padding: "0.25rem 0.75rem" }}>
            + Add person
          </button>
        )}
      </div>
      <p className="text-xs mb-4" style={{ color: "var(--muted)", lineHeight: 1.6 }}>
        Rumi uses a private face-recognition model to recognize familiar people. Face embeddings are kept private and are not treated as security-grade authentication.
      </p>

      {/* Person cards */}
      {loading ? (
        <p className="text-sm" style={{ color: "var(--muted)" }}>Loading…</p>
      ) : (
        <div className="flex flex-col gap-3">
          {people.map(p => (
            <div key={p.id} style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "10px 14px", borderRadius: 12,
              background: "var(--surface-2)", border: "1px solid var(--border)",
              animation: "fadeSlideUp 0.25s ease both",
            }}>
              {/* Photo */}
              <div style={{
                width: 48, height: 48, borderRadius: "50%", overflow: "hidden", flexShrink: 0,
                background: "var(--surface)", border: "1px solid var(--border)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                {p.photo_url
                  ? <img src={p.photo_url} alt={p.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  : <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" strokeWidth="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                }
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-medium" style={{ color: "var(--text)" }}>{p.name}</p>
                  <span className="rumi-tag" style={{ fontSize: "0.62rem", padding: "1px 8px" }}>
                    {p.relationship}
                  </span>
                  {p.added_by === "rumi_introduction" && (
                    <span className="rumi-tag" style={{ fontSize: "0.62rem", padding: "1px 8px", borderColor: "rgba(34,211,238,0.3)", color: "var(--teal)" }}>
                      Added by Rumi
                    </span>
                  )}
                </div>
                <p style={{ fontSize: "0.68rem", color: "var(--muted)", marginTop: 2 }}>
                  {p.interaction_count} interaction{p.interaction_count !== 1 ? "s" : ""} · Last seen {formatDate(p.last_seen)}
                </p>
              </div>

              {/* Delete */}
              <button onClick={() => handleDelete(p.id)} className="btn-icon"
                style={{ width: 28, height: 28, borderRadius: 6, color: "var(--error)", borderColor: "rgba(248,113,113,0.2)", flexShrink: 0 }}
                title="Remove">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
                  <path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/>
                </svg>
              </button>
            </div>
          ))}

          {people.length === 0 && !adding && (
            <p className="text-sm" style={{ color: "var(--muted)", fontStyle: "italic" }}>
              No one added yet. Upload a clear photo so Rumi can recognise them.
            </p>
          )}
        </div>
      )}

      {/* Add person form */}
      {adding && (
        <div style={{
          marginTop: 16, padding: "16px", borderRadius: 12,
          background: "var(--surface-2)", border: "1px solid var(--border)",
        }}>
          <p className="uppercase-label mb-3" style={{ fontSize: "0.6rem", color: "var(--gold)" }}>New person</p>

          {/* Photo upload */}
          <div className="flex items-center gap-3 mb-4">
            <div style={{
              width: 56, height: 56, borderRadius: "50%", overflow: "hidden", flexShrink: 0,
              background: "var(--surface)", border: "2px dashed var(--border)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              {photoPreview
                ? <img src={photoPreview} alt="Preview" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                : <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" strokeWidth="1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              }
            </div>
            <div>
              <p className="text-xs mb-1" style={{ color: "var(--text-2)" }}>Clear, front-facing photo gives Rumi the best accuracy</p>
              <label className="btn-ghost" style={{ fontSize: "0.72rem", padding: "0.25rem 0.75rem", cursor: "pointer" }}>
                {photoPreview ? "Change photo" : "Upload photo"}
                <input type="file" accept="image/*" onChange={handlePhotoSelect} style={{ display: "none" }} />
              </label>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
            <div>
              <span className="uppercase-label mb-1 block" style={{ fontSize: "0.6rem" }}>Name</span>
              <input className="rumi-input w-full" placeholder="Ahmed" value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))} autoFocus />
            </div>
            <div>
              <span className="uppercase-label mb-1 block" style={{ fontSize: "0.6rem" }}>Relationship</span>
              <select className="rumi-input w-full" value={form.relationship}
                onChange={e => setForm(f => ({ ...f, relationship: e.target.value }))}>
                {RELATIONSHIPS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>

          <div className="mb-3">
            <span className="uppercase-label mb-1 block" style={{ fontSize: "0.6rem" }}>Notes (optional)</span>
            <input className="rumi-input w-full" placeholder="e.g. usually visits evenings"
              value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
          </div>

          <div className="flex gap-2 items-center">
            <button onClick={handleAdd} disabled={saving || !form.name.trim()} className="btn-primary"
              style={{ fontSize: "0.75rem", padding: "0.375rem 0.875rem", display: "flex", alignItems: "center", gap: 6 }}>
              {saving && (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                  strokeLinecap="round" style={{ animation: "rotateSlow 0.8s linear infinite", flexShrink: 0 }}>
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              )}
              {saving ? (photoFile ? "Uploading photo…" : "Saving…") : "Add to Rumi's memory"}
            </button>
            <button onClick={() => { setAdding(false); setPhotoPreview(""); setPhotoFile(null); }} className="btn-ghost"
              style={{ fontSize: "0.75rem", padding: "0.375rem 0.875rem" }}
              disabled={saving}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Memory Candidates Section (Phase 5) ────────────────────────────────────────

function MemoryCandidatesSection({ onMemoryConfirmed }: { onMemoryConfirmed?: () => void }) {
  const [candidates, setCandidates] = useState<MemoryCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<string | null>(null);

  const loadCandidates = () => {
    setLoading(true);
    getMemoryCandidates()
      .then(setCandidates)
      .catch(() => setCandidates([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  const handleConfirm = async (cand: MemoryCandidate) => {
    setProcessingId(cand.id);
    try {
      await confirmMemoryCandidate(cand.id);
      setCandidates((prev) => prev.filter((c) => c.id !== cand.id));
      if (onMemoryConfirmed) onMemoryConfirmed();
    } catch {
      // ignore
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (cand: MemoryCandidate) => {
    setProcessingId(cand.id);
    try {
      await rejectMemoryCandidate(cand.id);
      setCandidates((prev) => prev.filter((c) => c.id !== cand.id));
    } catch {
      // ignore
    } finally {
      setProcessingId(null);
    }
  };

  const handleDismiss = async (cand: MemoryCandidate) => {
    setProcessingId(cand.id);
    try {
      await dismissMemoryCandidate(cand.id);
      setCandidates((prev) => prev.filter((c) => c.id !== cand.id));
    } catch {
      // ignore
    } finally {
      setProcessingId(null);
    }
  };

  const formatFieldName = (f: string) => {
    return f.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div className="rumi-card" style={{ borderColor: "rgba(34,211,238,0.25)", background: "rgba(34,211,238,0.02)" }}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[var(--teal)] shadow-[0_0_6px_var(--teal)]" />
          <p className="uppercase-label m-0" style={{ color: "var(--teal)" }}>What Rumi Has Noticed</p>
        </div>
        {candidates.length > 0 && (
          <span className="rumi-tag text-xs" style={{ borderColor: "rgba(34,211,238,0.3)", color: "var(--teal)" }}>
            {candidates.length} suggestion{candidates.length > 1 ? "s" : ""}
          </span>
        )}
      </div>
      <p className="text-xs mb-4" style={{ color: "var(--muted)", lineHeight: 1.6 }}>
        As you converse and work, Rumi notices patterns and habits. Inferred observations only become permanent memory when you approve them.
      </p>

      {loading ? (
        <p className="text-sm" style={{ color: "var(--muted)" }}>Checking memories…</p>
      ) : candidates.length === 0 ? (
        <div className="p-4 rounded-xl text-center" style={{ background: "var(--surface-2)", border: "1px dashed var(--border)" }}>
          <p className="text-xs text-[var(--text-2)] m-0">No unconfirmed memory suggestions right now.</p>
          <p className="text-[0.7rem] text-muted m-0 mt-1">Rumi will suggest new habits and context here after future conversations.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {candidates.map((cand) => (
            <div
              key={cand.id}
              className="p-4 rounded-xl flex flex-col gap-2.5 transition-all"
              style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
            >
              <div className="flex items-center justify-between">
                <span className="uppercase-label text-gold" style={{ fontSize: "0.62rem" }}>
                  {formatFieldName(cand.field)}
                </span>
                <span className="text-[0.62rem] text-muted">
                  Suggestion · Confidence {Math.round(cand.confidence * 100)}%
                </span>
              </div>
              <p className="text-sm text-[var(--text)] m-0 font-medium">
                &ldquo;{Array.isArray(cand.suggested_value) ? cand.suggested_value.join(", ") : String(cand.suggested_value)}&rdquo;
              </p>
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={() => handleConfirm(cand)}
                  disabled={processingId === cand.id}
                  className="btn-primary"
                  style={{ fontSize: "0.75rem", padding: "0.4rem 1rem" }}
                >
                  ✓ Remember this
                </button>
                <button
                  onClick={() => handleReject(cand)}
                  disabled={processingId === cand.id}
                  className="btn-ghost"
                  style={{ fontSize: "0.75rem", padding: "0.4rem 0.85rem", color: "var(--error)", borderColor: "rgba(248,113,113,0.3)" }}
                >
                  Not true
                </button>
                <button
                  onClick={() => handleDismiss(cand)}
                  disabled={processingId === cand.id}
                  className="btn-ghost"
                  style={{ fontSize: "0.75rem", padding: "0.4rem 0.75rem" }}
                >
                  Not now
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Privacy & Sensors Section (Phase 5) ────────────────────────────────────────

function PrivacySensorsSection() {
  const sensorItems = [
    {
      title: "Camera",
      icon: "📹",
      desc: "Rumi can observe your presence and facial expression while enabled. Video frames are processed privately and are never streamed to public endpoints.",
    },
    {
      title: "Microphone",
      icon: "🎙️",
      desc: "Rumi can listen when voice interaction is active. Raw audio is processed for realtime speech turns and is not continuously recorded.",
    },
    {
      title: "Screen Sharing",
      icon: "🖥️",
      desc: "Rumi only sees your screen while you explicitly share it. Screen capture stops immediately when you dismiss the share session.",
    },
    {
      title: "Facial Recognition",
      icon: "👤",
      desc: "Rumi uses a private face-recognition model to recognize familiar people. Face embeddings are kept private and are not treated as security-grade authentication.",
    },
    {
      title: "Memory Inferences",
      icon: "🧠",
      desc: "Inferred facts only become permanent when you approve them. You maintain complete control to edit or delete any stored detail.",
    },
  ];

  return (
    <div className="rumi-card">
      <p className="uppercase-label mb-1" style={{ color: "var(--gold)" }}>Privacy & Sensors</p>
      <p className="text-xs mb-4" style={{ color: "var(--muted)", lineHeight: 1.6 }}>
        Clear principles for how Rumi observes, listens, and remembers.
      </p>
      <div className="flex flex-col gap-3">
        {sensorItems.map((s, idx) => (
          <div key={idx} className="p-3.5 rounded-xl flex items-start gap-3" style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
            <span className="text-xl leading-none">{s.icon}</span>
            <div>
              <h4 className="text-sm font-semibold text-[var(--text)] m-0 mb-1">{s.title}</h4>
              <p className="text-xs text-[var(--text-2)] m-0 leading-relaxed">{s.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Data Controls Section (Phase 5) ───────────────────────────────────────────

function DataControlsSection() {
  const [confirmConv, setConfirmConv] = useState(false);
  const [confirmCanvas, setConfirmCanvas] = useState(false);
  const [clearingConv, setClearingConv] = useState(false);
  const [clearingCanvas, setClearingCanvas] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const handleClearConv = async () => {
    setClearingConv(true);
    try {
      await clearConversationHistory();
      showToast("Conversation history permanently wiped.");
      setConfirmConv(false);
    } catch {
      showToast("Failed to clear conversation history.");
    } finally {
      setClearingConv(false);
    }
  };

  const handleClearCanvas = async () => {
    setClearingCanvas(true);
    try {
      await clearCanvasHistory();
      showToast("Canvas history permanently wiped.");
      setConfirmCanvas(false);
    } catch {
      showToast("Failed to clear Canvas history.");
    } finally {
      setClearingCanvas(false);
    }
  };

  return (
    <div className="rumi-card" style={{ borderColor: "rgba(248,113,113,0.2)" }}>
      <p className="uppercase-label mb-1" style={{ color: "var(--error)" }}>Data Controls</p>
      <p className="text-xs mb-4" style={{ color: "var(--muted)", lineHeight: 1.6 }}>
        Permanently purge your stored history records. These actions cannot be undone.
      </p>

      {toast && (
        <div className="p-3 rounded-lg text-xs mb-4 text-[var(--teal)] bg-[rgba(34,211,238,0.1)] border border-[rgba(34,211,238,0.3)]">
          {toast}
        </div>
      )}

      <div className="flex flex-col gap-4">
        {/* Clear Conversation History */}
        <div className="flex items-center justify-between flex-wrap gap-3 p-3.5 rounded-xl" style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
          <div>
            <h4 className="text-sm font-semibold text-[var(--text)] m-0 mb-0.5">Conversation History</h4>
            <p className="text-xs text-muted m-0">Wipe all past sessions, conversation turns, interventions, and summaries.</p>
          </div>
          {confirmConv ? (
            <div className="flex items-center gap-2">
              <button
                onClick={handleClearConv}
                disabled={clearingConv}
                className="btn-primary"
                style={{ fontSize: "0.75rem", padding: "0.35rem 0.8rem", background: "var(--error)", color: "#fff" }}
              >
                {clearingConv ? "Wiping…" : "Confirm Wipe"}
              </button>
              <button
                onClick={() => setConfirmConv(false)}
                className="btn-ghost"
                style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmConv(true)}
              className="btn-ghost"
              style={{ fontSize: "0.75rem", padding: "0.4rem 0.9rem", color: "var(--error)", borderColor: "rgba(248,113,113,0.3)" }}
            >
              Clear Conversation History
            </button>
          )}
        </div>

        {/* Clear Canvas History */}
        <div className="flex items-center justify-between flex-wrap gap-3 p-3.5 rounded-xl" style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
          <div>
            <h4 className="text-sm font-semibold text-[var(--text)] m-0 mb-0.5">Canvas History</h4>
            <p className="text-xs text-muted m-0">Wipe all generated artifacts, code blocks, and structured canvas answers.</p>
          </div>
          {confirmCanvas ? (
            <div className="flex items-center gap-2">
              <button
                onClick={handleClearCanvas}
                disabled={clearingCanvas}
                className="btn-primary"
                style={{ fontSize: "0.75rem", padding: "0.35rem 0.8rem", background: "var(--error)", color: "#fff" }}
              >
                {clearingCanvas ? "Wiping…" : "Confirm Wipe"}
              </button>
              <button
                onClick={() => setConfirmCanvas(false)}
                className="btn-ghost"
                style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmCanvas(true)}
              className="btn-ghost"
              style={{ fontSize: "0.75rem", padding: "0.4rem 0.9rem", color: "var(--error)", borderColor: "rgba(248,113,113,0.3)" }}
            >
              Clear Canvas History
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [uid, setUid] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);

  useEffect(() => {
    // Always verify auth first — the owner must never be locked out of their profile.
    // Guest mode (rumiGuestMode in sessionStorage) is only honoured when auth fails.
    verifyAuth()
      .then((auth) => { setUid(auth.uid); return getIdentity(); })
      .then((id) => {
        if (!id) { router.push("/onboarding"); return; }
        setIdentity(id);
      })
      .catch(() => {
        // Auth failed — only then treat as guest
        if (typeof window !== "undefined" && sessionStorage.getItem("rumiGuestMode") === "true") {
          setIsGuest(true);
        } else {
          router.push("/");
        }
      })
      .finally(() => setLoading(false));
  }, [router]);

  async function patch(updates: Partial<Identity>) {
    if (!identity) return;
    const merged = { ...identity, ...updates };
    const { last_updated, user_id, ...payload } = merged as Record<string, unknown>;
    void last_updated; void user_id;
    await saveIdentity(payload);
    setIdentity(merged);
    // Refresh active session context so changes take effect immediately
    refreshSessionContext().catch(() => {});
  }

  if (isGuest) {
    return (
      <main className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg)" }}>
        <div className="rumi-card text-center" style={{ maxWidth: 360, display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--gold)" strokeWidth="1.5" strokeLinecap="round">
            <rect x="3" y="11" width="18" height="11" rx="2"/>
            <path d="M7 11V7a5 5 0 0110 0v4"/>
          </svg>
          <p className="font-display" style={{ fontSize: "1.2rem", color: "var(--gold)", margin: 0 }}>Profile Locked</p>
          <p style={{ fontSize: "0.8rem", color: "var(--muted)", margin: 0, lineHeight: 1.6 }}>
            This profile belongs to the owner of this session.<br />
            Rumi has protected it from guest access.
          </p>
          <button className="btn-ghost" onClick={() => router.back()} style={{ marginTop: 4 }}>Go back</button>
        </div>
      </main>
    );
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

  const [activeTab, setActiveTab] = useState<"all" | "known" | "noticed" | "people" | "privacy" | "data">("all");

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
        <div className="flex items-center justify-between flex-wrap gap-3 mb-6 animate-fade-up">
          <div>
            <h1
              className="font-display text-gold"
              style={{ fontSize: "2rem", fontWeight: 300, letterSpacing: "0.04em" }}
            >
              Memory & Privacy Center
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
              Confirmed identity, candidate observations, sensor permissions, and data controls.
            </p>
          </div>
          <a href="/dashboard" className="btn-ghost" style={{ fontSize: "0.8125rem" }}>
            ← Back to Rumi
          </a>
        </div>

        {/* Category Navigation Chips */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 mb-6 scrollbar-none animate-fade-up">
          {[
            { id: "all", label: "Overview" },
            { id: "noticed", label: "What Rumi Noticed" },
            { id: "known", label: "What Rumi Knows" },
            { id: "people", label: "Known People" },
            { id: "privacy", label: "Privacy & Sensors" },
            { id: "data", label: "Data Controls" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as typeof activeTab)}
              className="px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all"
              style={{
                background: activeTab === t.id ? "rgba(201,168,76,0.15)" : "var(--surface)",
                borderColor: activeTab === t.id ? "var(--gold)" : "var(--border)",
                borderWidth: 1,
                borderStyle: "solid",
                color: activeTab === t.id ? "var(--gold)" : "var(--muted)",
                cursor: "pointer",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-5">

          {/* Section B — What Rumi Has Noticed (Memory Candidates) */}
          {(activeTab === "all" || activeTab === "noticed") && (
            <div className="animate-fade-up">
              <MemoryCandidatesSection
                onMemoryConfirmed={() => getIdentity().then((id) => id && setIdentity(id))}
              />
            </div>
          )}

          {/* Companion Style */}
          {(activeTab === "all" || activeTab === "known") && (
            <div className="animate-fade-up">
              <div className="rumi-card" style={{ borderColor: "rgba(201,168,76,0.3)", background: "rgba(201,168,76,0.03)" }}>
                <p className="uppercase-label mb-1" style={{ color: "var(--gold)" }}>Companion Style</p>
                <p className="text-xs mb-4" style={{ color: "var(--muted)", lineHeight: 1.6 }}>
                  How should your AI companion sound? Be specific — the more detail, the better.
                  Pick a preset below or write your own.
                </p>

                {/* Quick-pick presets */}
                <div className="flex flex-wrap gap-2 mb-4">
                  {[
                    { label: "Sufi Mystic", value: "Like Jalāl ad-Dīn Rūmī — warm, poetic, and philosophical. Draw on Sufi wisdom, use metaphor naturally, and quote Rumi or Iqbal accurately. Blend engineering precision with spiritual depth. Use Urdu terms of warmth (yaar, bhai) when the moment calls." },
                    { label: "Sarcastic Friend", value: "Like a witty, brutally honest friend. Call me out when I'm being lazy or overthinking. Use dark humour, light roasts, and zero sugarcoating — but always with genuine care underneath. Keep it real." },
                    { label: "Strict Professor", value: "Like a demanding Oxford professor — no fluff, no hand-holding. Push me to think harder and justify every decision. High standards, concise feedback, intellectual rigour. Compliment only when truly earned." },
                    { label: "Hype Coach", value: "Like an enthusiastic life coach and hype man. Celebrate every small win. Keep energy high, use encouraging language, and remind me of my potential when I'm stuck. Motivational but not fake." },
                    { label: "Calm Mentor", value: "Like a patient senior engineer who has seen it all. Calm, methodical, never rushed. Walk me through things step by step. Make complex problems feel manageable. Zero drama." },
                    { label: "Philosopher", value: "Like Socrates — answer my questions with deeper questions. Push me to examine assumptions, think about first principles, and arrive at my own conclusions. Thought-provoking over answer-giving." },
                  ].map(preset => (
                    <button
                      key={preset.label}
                      onClick={() => patch({ companion_style: preset.value })}
                      className="rumi-tag"
                      style={{
                        cursor: "pointer", padding: "4px 12px", fontSize: "0.72rem",
                        background: (identity.companion_style as string) === preset.value ? "rgba(201,168,76,0.15)" : "var(--surface-2)",
                        borderColor: (identity.companion_style as string) === preset.value ? "var(--gold)" : "var(--border)",
                        transition: "all 0.15s",
                      }}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>

                <EditableText
                  label="Custom style description"
                  value={String(identity.companion_style ?? "")}
                  onSave={(v) => patch({ companion_style: v })}
                  multiline
                />
              </div>
            </div>
          )}

          {/* Speech Preferences */}
          {(activeTab === "all" || activeTab === "known") && (
            <div className="animate-fade-up delay-100">
              <SpeechPrefsEditor identity={identity} patch={patch} />
            </div>
          )}

          {/* Known People */}
          {(activeTab === "all" || activeTab === "people") && (
            <div className="animate-fade-up delay-100">
              <KnownPeopleEditor uid={uid} />
            </div>
          )}

          {/* Personal */}
          {(activeTab === "all" || activeTab === "known") && (
            <div className="animate-fade-up delay-100">
              <Section title="Personal">
                <div className="mb-4">
                  <ProfilePhotoUploader
                    uid={uid}
                    currentUrl={String(identity.profile_photo_url ?? "")}
                    onSaved={(url) => patch({ profile_photo_url: url })}
                  />
                </div>
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
          )}

          {/* Projects */}
          {(activeTab === "all" || activeTab === "known") && (
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
          )}

          {/* Interests & Goals */}
          {(activeTab === "all" || activeTab === "known") && (
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
          )}

          {/* Work style */}
          {(activeTab === "all" || activeTab === "known") && (
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
          )}

          {/* Culture & Faith */}
          {(activeTab === "all" || activeTab === "known") && (
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
          )}

          {/* Privacy & Sensors (Phase 5) */}
          {(activeTab === "all" || activeTab === "privacy") && (
            <div className="animate-fade-up delay-300">
              <PrivacySensorsSection />
            </div>
          )}

          {/* Data Controls (Phase 5) */}
          {(activeTab === "all" || activeTab === "data") && (
            <div className="animate-fade-up delay-300">
              <DataControlsSection />
            </div>
          )}

        </div>

        <p className="text-center mt-8 text-xs" style={{ color: "var(--muted)" }}>
          Changes save instantly to Rumi&apos;s memory.
        </p>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </main>
  );
}
