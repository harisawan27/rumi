"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { saveIdentity, verifyAuth } from "@/services/session";

interface Project {
  name: string;
  status: string;
  context: string;
}

interface FormData {
  name: string;
  full_name: string;
  location: string;
  roles: string[];
  projects: Project[];
  immediate_goal: string;
  long_term_goal: string;
  work_style: string;
  communication_preference: string;
  wellness_trigger: string;
  // Optional expandable fields
  interests: string[];
  focus_breakers: string[];
  faith: string;
  salah_awareness: string;
  turkish_goal: string;
}

const TONE_PRESETS = [
  {
    id: "gentle",
    label: "Gentle & Inspiring",
    desc: "Gentle but firm — inspire through wisdom, not nagging.",
  },
  {
    id: "direct",
    label: "Direct & Concise",
    desc: "Direct, focused on execution, minimal pleasantries.",
  },
  {
    id: "reflective",
    label: "Thoughtful & Ambient",
    desc: "Warm, reflective companion that observes and prompts when appropriate.",
  },
];

const ROLE_SUGGESTIONS = [
  "Engineer",
  "Designer",
  "Founder",
  "Researcher",
  "Writer",
  "Student",
];

const STEP_TITLES = [
  "Identity",
  "Focus",
  "Companion Style",
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [form, setForm] = useState<FormData>({
    name: "",
    full_name: "",
    location: "",
    roles: [],
    projects: [{ name: "", status: "", context: "" }],
    immediate_goal: "",
    long_term_goal: "",
    work_style: "",
    communication_preference: TONE_PRESETS[0].desc,
    wellness_trigger: "Suggest a chai or hydration break after long focus sprints.",
    interests: [],
    focus_breakers: [],
    faith: "",
    salah_awareness: "",
    turkish_goal: "",
  });

  function setField(key: keyof FormData) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  function toggleRole(role: string) {
    setForm((f) => {
      const exists = f.roles.includes(role);
      const roles = exists ? f.roles.filter((r) => r !== role) : [...f.roles, role];
      return { ...f, roles };
    });
  }

  async function handleSubmit() {
    if (!form.name.trim()) {
      setError("Please provide a name so Rumi knows what to call you.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await verifyAuth();
      const payload = {
        ...form,
        projects: form.projects.filter((p) => p.name.trim()),
      };
      await saveIdentity(payload);
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save profile");
      setSaving(false);
    }
  }

  const isLastStep = step === STEP_TITLES.length - 1;

  return (
    <main
      className="dot-grid noise-overlay min-h-screen flex flex-col items-center justify-start py-10 px-4"
      style={{ background: "var(--bg)" }}
    >
      <div className="w-full max-w-lg animate-fade-up">
        {/* Brand Header */}
        <div className="mb-6 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono uppercase tracking-wider mb-3"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--gold)" }}>
            ✦ Meet Your Ambient Companion
          </div>
          <h1
            className="font-display text-gold"
            style={{ fontSize: "2.25rem", fontWeight: 300, letterSpacing: "0.04em" }}
          >
            Welcome to Rumi
          </h1>
          <p className="mt-1.5 text-sm" style={{ color: "var(--text-2)" }}>
            A quick setup so every moment feels attuned to who you are. (Takes under 60s)
          </p>
        </div>

        {/* Step Progress */}
        <div className="flex gap-2 mb-6">
          {STEP_TITLES.map((title, i) => (
            <div key={title} className="flex-1 flex flex-col gap-1.5">
              <div
                className="h-1 rounded-full transition-all duration-300"
                style={{
                  background:
                    i <= step
                      ? "linear-gradient(90deg, var(--gold), var(--teal))"
                      : "var(--border)",
                }}
              />
              <span
                className="text-xs transition-colors duration-200"
                style={{
                  color: i === step ? "var(--gold)" : "var(--muted)",
                  fontSize: "0.7rem",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                {i + 1}. {title}
              </span>
            </div>
          ))}
        </div>

        {/* Form Card */}
        <div className="rumi-card mb-5 p-6 rounded-2xl" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
          {/* STEP 0: IDENTITY */}
          {step === 0 && (
            <div className="flex flex-col gap-4">
              <div>
                <label className="flex flex-col gap-1.5">
                  <span className="uppercase-label font-mono text-xs text-gold">What should Rumi call you? *</span>
                  <input
                    type="text"
                    className="rumi-input text-base"
                    placeholder="e.g. Haris"
                    value={form.name}
                    onChange={setField("name")}
                    autoFocus
                  />
                </label>
              </div>

              <div>
                <label className="flex flex-col gap-1.5">
                  <span className="uppercase-label font-mono text-xs text-muted">City / Location</span>
                  <input
                    type="text"
                    className="rumi-input"
                    placeholder="e.g. Karachi, Pakistan"
                    value={form.location}
                    onChange={setField("location")}
                  />
                </label>
              </div>

              <div>
                <span className="uppercase-label font-mono text-xs text-muted block mb-2">What best describes your roles?</span>
                <div className="flex flex-wrap gap-1.5">
                  {ROLE_SUGGESTIONS.map((role) => {
                    const active = form.roles.includes(role);
                    return (
                      <button
                        key={role}
                        type="button"
                        onClick={() => toggleRole(role)}
                        className="px-3 py-1.5 rounded-lg text-xs font-mono transition-all duration-150"
                        style={{
                          background: active ? "var(--gold)" : "var(--surface-2)",
                          color: active ? "#000" : "var(--text-2)",
                          border: active ? "1px solid var(--gold)" : "1px solid var(--border)",
                        }}
                      >
                        {role} {active ? "✓" : "+"}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* STEP 1: FOCUS */}
          {step === 1 && (
            <div className="flex flex-col gap-4">
              <div>
                <label className="flex flex-col gap-1.5">
                  <span className="uppercase-label font-mono text-xs text-gold">Primary focus / project right now</span>
                  <input
                    type="text"
                    className="rumi-input text-base"
                    placeholder="e.g. Shipping Project Rumi, building DoneKaro"
                    value={form.projects[0]?.name || ""}
                    onChange={(e) => {
                      const val = e.target.value;
                      setForm((f) => ({
                        ...f,
                        projects: [{ ...f.projects[0], name: val }],
                      }));
                    }}
                    autoFocus
                  />
                </label>
              </div>

              <div>
                <label className="flex flex-col gap-1.5">
                  <span className="uppercase-label font-mono text-xs text-muted">What is your immediate goal?</span>
                  <textarea
                    rows={2}
                    className="rumi-input text-sm"
                    placeholder="e.g. Finish the Google Gemini challenge with zero regressions"
                    value={form.immediate_goal}
                    onChange={setField("immediate_goal")}
                  />
                </label>
              </div>

              <div>
                <label className="flex flex-col gap-1.5">
                  <span className="uppercase-label font-mono text-xs text-muted">How do you like to work?</span>
                  <input
                    type="text"
                    className="rumi-input text-sm"
                    placeholder="e.g. Late-night deep work sprints, minimal interruptions"
                    value={form.work_style}
                    onChange={setField("work_style")}
                  />
                </label>
              </div>
            </div>
          )}

          {/* STEP 2: COMPANION STYLE */}
          {step === 2 && (
            <div className="flex flex-col gap-5">
              <div>
                <span className="uppercase-label font-mono text-xs text-gold block mb-2">How should Rumi speak to you?</span>
                <div className="flex flex-col gap-2">
                  {TONE_PRESETS.map((preset) => {
                    const active = form.communication_preference === preset.desc;
                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, communication_preference: preset.desc }))}
                        className="text-left p-3 rounded-xl transition-all duration-150 flex flex-col gap-1"
                        style={{
                          background: active ? "rgba(201, 168, 76, 0.08)" : "var(--surface-2)",
                          border: active ? "1px solid var(--gold)" : "1px solid var(--border)",
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium" style={{ color: active ? "var(--gold)" : "var(--text)" }}>
                            {preset.label}
                          </span>
                          {active && <span className="text-xs text-gold font-mono">Selected</span>}
                        </div>
                        <span className="text-xs text-muted">{preset.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="flex flex-col gap-1.5">
                  <span className="uppercase-label font-mono text-xs text-muted">Wellness break reminder cue</span>
                  <input
                    type="text"
                    className="rumi-input text-sm"
                    placeholder="e.g. Suggest a doodh patti break and stretch"
                    value={form.wellness_trigger}
                    onChange={setField("wellness_trigger")}
                  />
                </label>
              </div>

              {/* Advanced optional section toggle */}
              <div className="pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-xs font-mono text-muted hover:text-gold transition-colors flex items-center gap-1.5"
                >
                  <span>{showAdvanced ? "▾ Hide additional personal context" : "▸ Add optional personal context (faith, language, goals)"}</span>
                </button>

                {showAdvanced && (
                  <div className="mt-4 flex flex-col gap-3.5 animate-fade-up">
                    <label className="flex flex-col gap-1">
                      <span className="uppercase-label font-mono text-xs text-muted">Faith / Prayer Awareness</span>
                      <input
                        type="text"
                        className="rumi-input text-xs"
                        placeholder="e.g. Practicing Muslim — aware of Asr and Maghrib prayer times"
                        value={form.salah_awareness}
                        onChange={setField("salah_awareness")}
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="uppercase-label font-mono text-xs text-muted">Language or Cultural Focus</span>
                      <input
                        type="text"
                        className="rumi-input text-xs"
                        placeholder="e.g. Daily Turkish practice"
                        value={form.turkish_goal}
                        onChange={setField("turkish_goal")}
                      />
                    </label>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {error && (
          <div
            className="mb-4 p-3 rounded-xl text-xs font-mono"
            style={{ background: "rgba(224, 82, 82, 0.1)", border: "1px solid var(--error)", color: "var(--error)" }}
          >
            {error}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3">
          {step > 0 && (
            <button
              type="button"
              onClick={() => setStep((s) => s - 1)}
              className="btn-ghost flex-1 py-3 text-sm font-mono"
            >
              Back
            </button>
          )}

          {isLastStep ? (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={saving || !form.name.trim()}
              className="btn-primary flex-1 py-3 text-sm font-medium flex items-center justify-center gap-2"
            >
              {saving ? (
                <>
                  <span
                    style={{
                      display: "inline-block",
                      width: 14,
                      height: 14,
                      borderRadius: "50%",
                      border: "2px solid currentColor",
                      borderTopColor: "transparent",
                      animation: "spin 0.7s linear infinite",
                    }}
                  />
                  <span>Launching…</span>
                </>
              ) : (
                <span>Launch Rumi</span>
              )}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setStep((s) => s + 1)}
              disabled={step === 0 && !form.name.trim()}
              className="btn-primary flex-1 py-3 text-sm font-medium"
            >
              Continue
            </button>
          )}
        </div>

        {/* Fast launch shortcut if name is entered */}
        {form.name.trim().length > 0 && !isLastStep && (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving}
            className="w-full mt-3 text-xs font-mono transition-colors text-center py-2"
            style={{ color: "var(--muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--gold)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted)")}
          >
            Skip rest & meet Rumi now →
          </button>
        )}

        <p className="text-center mt-4 text-xs font-mono" style={{ color: "var(--muted)" }}>
          You can refine your memories and privacy settings at any time in the Memory Center.
        </p>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </main>
  );
}
