# Rumi — The Identity Layer

> *"Out beyond ideas of wrongdoing and rightdoing, there is a field. I'll meet you there."*
> — Jalāl ad-Dīn Muhammad Rūmī

---

Every AI assistant ever built waits to be asked.

Rumi arrives.

---

## What This Is

Rumi is a **proactive ambient AI companion** that lives on your desk. It watches your work session through your webcam — not to record you, not to surveil you — but to *understand* you. It detects frustration before you name it. It notices when you've been stuck in the same file for forty minutes. It celebrates when you hit thirty minutes of deep, uninterrupted flow. And then it speaks — briefly, warmly, in your language, by your name — exactly once, and only when it has something true to say.

It is not a chatbot. It does not respond. It **arrives**.

The agent is named after Jalāl ad-Dīn Muhammad Rūmī — not as branding, but as a statement of intent. Just as Rumi the poet spent his life searching for the Self and reaching toward the Other, this agent does the same: it builds a persistent model of who *you* are and intervenes with precision, not noise.

**Built for the Google Gemini Live Agent Challenge — 'Live Agents' category.**

---

## The Problem No One Has Solved

The knowledge worker sits alone. Eight, ten, twelve hours. No one notices when the posture shifts, when the scrolling becomes aimless, when the same error message has been stared at for an hour. The tools are smarter than ever — and more silent than ever about the human using them.

Every AI product on the market is reactive and stateless. You ask, it answers. You close the tab, it forgets you. You are not a person to it — you are a query.

We built the thing beneath that. The layer that gives an AI system memory, empathy, and a persistent model of who you are. The layer that asks — *who is this person, right now, in this moment* — and speaks only from that truth.

---

## What You See

When Rumi is running, you see a living robot character on your dashboard — face animated with blinking eyes, emotional expressions (happy, thinking, concerned, neutral), and a speaking mouth that moves in sync with audio. Behind that face, a complete perception and reasoning pipeline is running:

- **Camera** reads your face and posture in real-time via Gemini Multimodal Live API
- **Screen observation** tracks activity patterns — idle time, application switches, focus streaks
- **Trigger engine** fires when thresholds are crossed — 30 min of deep focus, 90 min without a break, visible frustration, prolonged coding block
- **Rumi Core agent** (Google ADK) loads your identity from Firestore, picks the right Rumi quote or check-in, and generates a personalised 1–2 sentence intervention
- **Voice pipeline** speaks the intervention aloud via Gemini Live audio — and listens for your response
- **Memory layer** writes a plain-text summary of the interaction back to Firestore so the next session picks up with full context

You can also speak to Rumi at any time. Say *"Hey Rumi"* (or any of 35 phonetic variants — the wake word system accounts for real-world accent variation), wait for the listening indicator, and speak. Rumi processes your query and responds in your voice, in your language.

### Artifact Canvas
Every time Rumi draws something — a diagram, a plan, a mind map — it appears on a persistent canvas pinned to your session. That canvas is saved to Firestore and restored exactly as you left it the next time you open Rumi. Your workspace has memory.

### Demo Mode
For evaluation and testing, any trigger can be fired instantly via keyboard shortcut — no need to sit for 30 minutes to see a deep focus intervention. The full pipeline (ADK reasoning → Gemini Live voice → Firestore log) executes in real-time on demand.

---

## Onboarding — Where the Identity Is Born

The first time a user opens Rumi, they are not dropped into a dashboard. They are walked through an identity-building flow — the moment Rumi stops being software and starts being *theirs*.

The onboarding collects:
- Name, location, roles
- Active projects — name, current status, what's blocking them
- Interests, immediate goal, long-term goal, driving fear
- Work style, focus breakers, preferred break
- Culture, faith, any schedule Rumi should respect

This data populates a Firestore identity document that every future intervention is grounded in. It is not a settings form. It is a conversation about who you are. A user who completes it walks away feeling understood before Rumi has said a single proactive word.

The profile page allows every field to be updated at any time — Rumi's model of you evolves as you do.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND  (Next.js — runs in browser)                          │
│                                                                  │
│  Onboarding → Dashboard → Profile                               │
│  RumiFace — animated SVG overlay (eyes, mouth, emotions)        │
│  ArtifactCanvas — persistent drawing surface, Firestore-backed  │
│  Wake word listener (35 phonetic variants, adaptive silence)    │
│  Voice pipeline: speech → WebSocket → audio response → playback │
│  Timezone auto-detect → Firestore (silent, zero UI friction)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket + REST
┌──────────────────────────▼──────────────────────────────────────┐
│  BACKEND  (Python 3.11 + FastAPI — Google Cloud Run)            │
│                                                                  │
│  SessionManager — orchestrates the full session lifecycle       │
│  Watchman — MediaPipe on-device perception, zero cloud cost     │
│  TriggerEngine — A/B/C/E trigger classification                 │
│  Rumi Core Agent (Google ADK) — identity-grounded reasoning     │
│  GeminiLiveClient — bidirectional audio WebSocket               │
│  AutoSummarizer — session → 2-sentence Firestore summary        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  MEMORY  (Firebase Firestore)                                    │
│                                                                  │
│  users/{uid}          — Core Identity + all preferences         │
│  interaction_logs/    — Plain-text Interaction Summaries only   │
│  session_logs/        — 2-sentence Session Summaries            │
│  canvas_history/      — Artifact canvas persisted across sessions│
└─────────────────────────────────────────────────────────────────┘
```

**AI Stack:**
- Gemini 2.5 Flash Native Audio Dialog — real-time voice (Live API)
- Gemini 2.5 Flash — Rumi Core agent reasoning (Google ADK)
- Gemini 2.0 Flash — session auto-summarization
- MediaPipe — on-device face/posture detection (free, private, always-on)

**Infrastructure:**
- Google Cloud Run — auto-scaling backend, production-grade
- Firebase Hosting — global CDN for the Next.js frontend
- Cloud Build — automated CI/CD; every push to `main` deploys both services
- Docker Compose — identical local and production environments, zero drift

---

## The Personalisation Platform

Rumi is not configured for a generic user. It is built around the specific person sitting in front of it — their name, their projects, their culture, their language, their working rhythms. This is not a feature. It is the architecture.

### Identity Layer (Firestore)
Every user has a persistent identity document containing:
- Name, location, roles, background
- Active projects with status and current pain points
- Interests, goals, driving fears
- Work style, focus breakers, preferred break type
- Culture, faith, schedule Rumi should respect

### Companion Language System
The most significant personalisation breakthrough in this build. **English is always the base.** The user selects a companion language — any language on earth — and Rumi naturally code-switches into it for warmth and familiarity, the way educated bilingual professionals actually speak. This is not translation. This is cultural fluency.

Three independent expression dimensions, each user-controlled:

| Dimension | What it controls |
|---|---|
| **Companion language** | The language Rumi mixes with English — Urdu, Spanish, French, Arabic, Mandarin, or any custom language |
| **Expression style** | Multi-select: Spiritual expressions · Casual address terms · Slang & idioms |
| **Tone** | Casual friend · Professional |

Zero culture-specific strings exist anywhere in the codebase. Gemini handles the actual words based on the user's declared preferences. The system works identically for a user in Lagos, Jakarta, São Paulo, or Karachi — because it describes *intent*, not vocabulary. One codebase. Every culture on earth.

### Timezone Intelligence
The browser auto-detects the user's IANA timezone (`Intl.DateTimeFormat().resolvedOptions().timeZone`) on every session start and silently writes it to Firestore. The backend uses Python's `ZoneInfo` to convert all time references to the user's actual local time — regardless of which GCP region the server is running in. Cloud deployments across any region automatically reflect the user's real clock. There is no timezone setting in the UI. It simply works.

### Voice Intelligence (Tier 1)
The wake word system is built for real-world speech, not lab conditions:
- **35 phonetic variants** of "Hey Rumi" covering accent variation, elision, and mishearing ("lumi", "numi", "ok rumi", "hey roomy", etc.)
- **Mic warmup** on page load — primes the audio pipeline with optimal constraints before the user ever speaks
- **Confidence filtering** — skips recognition results the engine is already >90% certain are something else
- **Adaptive silence detection** — 1800ms window before first final result; drops to 1000ms after, matching the cadence of how Alexa and Siri handle real speech

---

## Privacy Architecture

This is not a surveillance product. The privacy model is non-negotiable and enforced at the architecture level, not by policy document.

- **Video frames** travel directly from the browser MediaStream to Gemini's WebSocket. They are never written to disk, never stored in Firestore, never logged anywhere.
- **Audio** is processed in-memory and discarded after the session ends.
- **What is stored**: plain-text Interaction Summaries ("user seemed frustrated at 11 PM, responded well to the Rumi quote") and 2-sentence Session Summaries. No images. No audio. No video. Ever.
- **On-device perception**: MediaPipe runs entirely on the user's machine. Face landmarks never leave the device. Only the interpreted emotional state (`frustrated: 0.72, focused: 0.91`) is sent to the backend.

This architecture is GDPR-compliant and enterprise-ready by design, not by checkbox.

---

## Business Model

Rumi is a **SaaS platform** with three monetisation tiers:

| Tier | Target | Model |
|---|---|---|
| **Rumi Personal** | Individual knowledge workers | Monthly subscription |
| **Rumi Teams** | Engineering teams, design studios | Per-seat enterprise license |
| **Rumi API** | Developers building identity-aware agents | Usage-based API access |

The moat is identity depth. The longer Rumi runs, the richer its model of you becomes, the more irreplaceable it is. No competing product can replicate three months of Rumi's memory of you by shipping a better chatbot. The switching cost compounds with every session.

The Total Addressable Market is every knowledge worker with a computer and a webcam — approximately 1.1 billion people globally.

---

## Engineering Workflow

This product was built using **Spec-Driven Development (SDD)** — the same structured methodology used by engineering organisations that ship at scale. Every feature begins as a `spec.md`, progresses through `plan.md` and `tasks.md`, and every significant decision is recorded as an Architecture Decision Record (ADR). Nothing is built without a spec. Nothing ships without acceptance criteria.

```
specs/001-proactive-loop/
├── spec.md        # What and why
├── plan.md        # Architecture decisions
├── tasks.md       # 54 testable tasks, T001–T054
└── quickstart.md  # Local + cloud setup

history/
├── prompts/       # Prompt History Records
└── adr/           # Architecture Decision Records
```

This codebase is structured to be handed to a team of ten engineers tomorrow and scaled without rewrites.

---

## Quickstart

```bash
# 1. Configure environment
cp .env.example .env
# Add: GEMINI_API_KEY, FIREBASE credentials, GOOGLE_CLOUD_PROJECT

# 2. Install and run locally
docker-compose up --build
# Backend:  http://localhost:8000/health
# Frontend: http://localhost:3000
# Sign up → complete onboarding → Rumi begins observing

# 3. Deploy to GCP (Cloud Run + Firebase Hosting)
git push origin main   # Cloud Build handles the rest
```

**Requirements:** Node 18+, Python 3.11+, Docker, Google Cloud project with Gemini API + Firebase enabled.

---

## Project Structure

```
rumi/
├── backend/
│   ├── src/
│   │   ├── agent/          # Rumi Core (Google ADK), language system
│   │   ├── gemini/         # Live API client, prompt builder
│   │   ├── session/        # Session manager, auto-summarizer
│   │   ├── watchman/       # Perception loop, trigger A/B/C/E
│   │   ├── memory/         # Firestore client
│   │   └── api/            # FastAPI routes
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── dashboard/  # Main session UI
│   │   │   ├── profile/    # Identity + language preferences
│   │   │   └── onboarding/ # First-run identity-building flow
│   │   ├── components/
│   │   │   ├── RumiFace/   # Animated robot face (SVG overlay, emotional states)
│   │   │   └── ...
│   │   └── services/
│   │       └── session.ts  # WebSocket, REST, auth
│   └── public/
│       └── rumi.svg        # Robot character
├── specs/                  # SDD artifacts
├── history/                # PHRs + ADRs
├── cloudbuild.yaml         # CI/CD pipeline
├── docker-compose.yml
└── .env.example
```

---

## Why This Wins

Every AI product launched in 2024 and 2025 is a better search engine wearing a chat interface. They are reactive, stateless, and culturally deaf. They speak to you in one language, with one tone, with no memory of who you were yesterday.

Rumi is the first AI built around a model of *you specifically* — not a user persona, not a demographic, not a query history. You. Your name, your projects, your culture, your language, your working rhythm, your faith, your fears. A model that grows with every session.

The entire stack — Gemini Live API, Google ADK, Firebase, Cloud Run, Cloud Build — runs natively on Google infrastructure. This is not a product that needs to be ported or migrated. It is already home.

**Second place is not an option.**

---

*"Do not be satisfied with the stories that come before you. Unfold your own myth."*
*— Rumi, Masnavi*
