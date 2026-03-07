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
  age: string;
  location: string;
  roles: string[];
  projects: Project[];
  interests: string[];
  immediate_goal: string;
  long_term_goal: string;
  driving_fear: string;
  work_style: string;
  focus_breakers: string[];
  communication_preference: string;
  faith: string;
  salah_awareness: string;
  turkish_goal: string;
  wellness_trigger: string;
}

const EMPTY_PROJECT: Project = { name: "", status: "", context: "" };

const STEP_TITLES = [
  "Who are you?",
  "What are you building?",
  "What drives you?",
  "How do you work?",
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<FormData>({
    name: "",
    full_name: "",
    age: "",
    location: "",
    roles: [],
    projects: [{ ...EMPTY_PROJECT }],
    interests: [],
    immediate_goal: "",
    long_term_goal: "",
    driving_fear: "",
    work_style: "",
    focus_breakers: [],
    communication_preference: "Gentle but firm — inspire through wisdom, not nagging.",
    faith: "",
    salah_awareness: "",
    turkish_goal: "",
    wellness_trigger: "Suggest a chai or doodh patti break.",
  });

  // ── Tag helpers ───────────────────────────────────────────────────────────

  function addTag(field: "roles" | "interests" | "focus_breakers", value: string) {
    const v = value.trim();
    if (!v) return;
    setForm((f) => ({ ...f, [field]: [...new Set([...f[field], v])] }));
  }

  function removeTag(field: "roles" | "interests" | "focus_breakers", value: string) {
    setForm((f) => ({ ...f, [field]: f[field].filter((t) => t !== value) }));
  }

  function TagInput({ field, placeholder }: { field: "roles" | "interests" | "focus_breakers"; placeholder: string }) {
    const [val, setVal] = useState("");
    return (
      <div>
        <div className="flex gap-2 flex-wrap mb-2">
          {form[field].map((t) => (
            <span key={t} className="flex items-center gap-1 bg-cyan-900/40 text-cyan-300 text-xs px-2 py-1 rounded-full">
              {t}
              <button onClick={() => removeTag(field, t)} className="hover:text-white">&times;</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            placeholder={placeholder}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(field, val); setVal(""); } }}
          />
          <button
            type="button"
            onClick={() => { addTag(field, val); setVal(""); }}
            className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg"
          >
            Add
          </button>
        </div>
      </div>
    );
  }

  // ── Project helpers ────────────────────────────────────────────────────────

  function updateProject(i: number, key: keyof Project, value: string) {
    setForm((f) => {
      const projects = [...f.projects];
      projects[i] = { ...projects[i], [key]: value };
      return { ...f, projects };
    });
  }

  // ── Field helper ──────────────────────────────────────────────────────────

  function field(key: keyof FormData) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  function Input({ label, fkey, placeholder, type = "text" }: {
    label: string; fkey: keyof FormData; placeholder?: string; type?: string;
  }) {
    return (
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-400">{label}</span>
        <input
          type={type}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          placeholder={placeholder}
          value={form[fkey] as string}
          onChange={field(fkey)}
        />
      </label>
    );
  }

  function Textarea({ label, fkey, placeholder, rows = 3 }: {
    label: string; fkey: keyof FormData; placeholder?: string; rows?: number;
  }) {
    return (
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-400">{label}</span>
        <textarea
          rows={rows}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 resize-none"
          placeholder={placeholder}
          value={form[fkey] as string}
          onChange={field(fkey)}
        />
      </label>
    );
  }

  // ── Steps ─────────────────────────────────────────────────────────────────

  const steps = [
    // Step 0 — Personal
    <div key="personal" className="flex flex-col gap-4">
      <Input label="First name (what Mirr'at calls you)" fkey="name" placeholder="e.g. Haris" />
      <Input label="Full name" fkey="full_name" placeholder="e.g. Muhammad Haris Awan" />
      <Input label="Age" fkey="age" type="number" placeholder="e.g. 18" />
      <Input label="City / Country" fkey="location" placeholder="e.g. Karachi, Pakistan" />
      <div className="flex flex-col gap-1">
        <span className="text-sm text-gray-400">Your roles (press Enter to add)</span>
        <TagInput field="roles" placeholder="e.g. Full Stack Developer" />
      </div>
    </div>,

    // Step 1 — Projects
    <div key="projects" className="flex flex-col gap-6">
      {form.projects.map((p, i) => (
        <div key={i} className="flex flex-col gap-3 bg-gray-800/50 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-cyan-400">Project {i + 1}</span>
            {form.projects.length > 1 && (
              <button
                onClick={() => setForm((f) => ({ ...f, projects: f.projects.filter((_, j) => j !== i) }))}
                className="text-gray-500 hover:text-red-400 text-xs"
              >
                Remove
              </button>
            )}
          </div>
          <input
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500"
            placeholder="Project name (e.g. DoneKaro)"
            value={p.name}
            onChange={(e) => updateProject(i, "name", e.target.value)}
          />
          <input
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500"
            placeholder="Current status (e.g. MVP complete)"
            value={p.status}
            onChange={(e) => updateProject(i, "status", e.target.value)}
          />
          <input
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 text-sm focus:outline-none focus:border-cyan-500"
            placeholder="What's the pain point right now?"
            value={p.context}
            onChange={(e) => updateProject(i, "context", e.target.value)}
          />
        </div>
      ))}
      {form.projects.length < 5 && (
        <button
          onClick={() => setForm((f) => ({ ...f, projects: [...f.projects, { ...EMPTY_PROJECT }] }))}
          className="text-sm text-cyan-400 hover:text-cyan-300 border border-dashed border-gray-700 rounded-xl py-3 hover:border-cyan-700 transition"
        >
          + Add another project
        </button>
      )}
    </div>,

    // Step 2 — Drive
    <div key="drive" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <span className="text-sm text-gray-400">Interests & passions (press Enter to add)</span>
        <TagInput field="interests" placeholder="e.g. Rumi, Turkish culture, Chess" />
      </div>
      <Textarea label="Immediate goal (this week / month)" fkey="immediate_goal" placeholder="e.g. Win the Google Gemini Challenge" />
      <Textarea label="Long-term goal" fkey="long_term_goal" placeholder="e.g. Build WEBXES into a US/Pakistan LLC" />
      <Textarea label="What's your biggest fear?" fkey="driving_fear" placeholder="e.g. Being generic, fading without global impact" />
    </div>,

    // Step 3 — Work style
    <div key="work" className="flex flex-col gap-4">
      <Textarea label="How do you work best?" fkey="work_style" placeholder="e.g. Late-night deep work sprints, SDD methodology, reflection after sessions" />
      <div className="flex flex-col gap-1">
        <span className="text-sm text-gray-400">What breaks your focus? (press Enter to add)</span>
        <TagInput field="focus_breakers" placeholder="e.g. Doom-scrolling, noise" />
      </div>
      <Textarea label="How should Mirr'at talk to you?" fkey="communication_preference" placeholder="e.g. Gentle but firm — inspire, don't nag" />
      <Input label="Faith / religion (optional)" fkey="faith" placeholder="e.g. Practicing Muslim" />
      <Textarea label="Any prayer / schedule Mirr'at should respect?" fkey="salah_awareness" placeholder="e.g. Asr and Maghrib are low-energy — suggest breaks around them" rows={2} />
      <Textarea label="Language learning or cultural goal?" fkey="turkish_goal" placeholder="e.g. 343-day Duolingo Turkish streak, preparing for Istanbul scholarship" rows={2} />
      <Textarea label="Preferred break (chai / walk / prayer / other)?" fkey="wellness_trigger" placeholder="e.g. Doodh patti and 5 minutes away from screen" rows={2} />
    </div>,
  ];

  async function handleSubmit() {
    setSaving(true);
    setError(null);
    try {
      await verifyAuth();
      const payload = {
        ...form,
        age: form.age ? Number(form.age) : undefined,
        projects: form.projects.filter((p) => p.name.trim()),
      };
      await saveIdentity(payload);
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-start py-12 px-4">
      <div className="w-full max-w-lg">

        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight">Meet Mirr&apos;at</h1>
          <p className="text-gray-400 text-sm mt-2">
            Let&apos;s learn who you are so every interaction feels personal.
          </p>
        </div>

        {/* Progress */}
        <div className="flex gap-2 mb-8">
          {STEP_TITLES.map((title, i) => (
            <div key={i} className="flex-1 flex flex-col gap-1">
              <div className={`h-1 rounded-full transition-all ${i <= step ? "bg-cyan-500" : "bg-gray-700"}`} />
              <span className={`text-xs hidden sm:block ${i === step ? "text-cyan-400" : "text-gray-600"}`}>
                {title}
              </span>
            </div>
          ))}
        </div>

        {/* Step title (mobile) */}
        <h2 className="text-lg font-semibold mb-6 sm:hidden">{STEP_TITLES[step]}</h2>

        {/* Step content */}
        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 mb-6">
          {steps[step]}
        </div>

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {/* Navigation */}
        <div className="flex gap-3">
          {step > 0 && (
            <button
              onClick={() => setStep((s) => s - 1)}
              className="flex-1 py-3 rounded-xl border border-gray-700 text-gray-300 hover:bg-gray-800 transition text-sm"
            >
              Back
            </button>
          )}
          {step < steps.length - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={
                (step === 0 && !form.name.trim()) ||
                (step === 1 && form.projects.every(p => !p.name.trim()))
              }
              className="flex-1 py-3 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white font-medium transition text-sm"
            >
              Continue
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={saving || !form.name.trim()}
              className="flex-1 py-3 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white font-medium transition text-sm"
            >
              {saving ? "Saving…" : "Launch Mirr'at"}
            </button>
          )}
        </div>

        <p className="text-center text-gray-600 text-xs mt-4">
          You can edit all of this later in your profile.
        </p>
      </div>
    </main>
  );
}
