# Rumi — Present before you speak

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

## Live Agent Rubric — Full Compliance

The Live Agents category requires: real-time audio/vision interaction, natural conversation with interruption support, Gemini Live API or ADK, and hosting on Google Cloud. Rumi satisfies every requirement — and uses both mandatory technologies simultaneously.

| Requirement | Implementation | Detail |
|---|---|---|
| **Real-time Audio** | Gemini 2.5 Flash Native Audio Dialog | Bidirectional voice WebSocket — Rumi speaks and listens in the same session |
| **Real-time Vision** | Gemini 2.5 Flash dual-frame analysis | Camera frame + screen frame analysed together every 15 seconds |
| **Talk naturally** | Web Speech API + 35-variant wake word | Say "Hey Rumi" in any accent, any ambient noise — it activates |
| **Can be interrupted** | `audio_interrupt` WebSocket + AudioContext cancellation | User speaking while Rumi talks cancels the active audio immediately (AudioContext closed, speech synthesis stopped). Barge-in during API processing also cancels the in-flight response and starts fresh — no dropped input at any stage |
| **Gemini Live API** | ✅ GeminiLiveClient | Core voice pipeline — proactive interventions and all spoken responses |
| **Google ADK** | ✅ Rumi Core Agent | Identity-grounded reasoning — every intervention is ADK-reasoned against Firestore memory |
| **Hosted on Google Cloud** | ✅ Cloud Run + Firebase Hosting | Backend on Cloud Run (asia-south1), frontend on Firebase Hosting global CDN |

Rumi is not a voice wrapper. It is a continuously running perception-reasoning-speech loop that initiates conversation without being asked, sees your face and screen simultaneously, and yields instantly when you speak over it.

---

## The Problem No One Has Solved

The knowledge worker sits alone. Eight, ten, twelve hours. No one notices when the posture shifts, when the scrolling becomes aimless, when the same error message has been stared at for an hour. The tools are smarter than ever — and more silent than ever about the human using them.

Every AI product on the market is reactive and stateless. You ask, it answers. You close the tab, it forgets you. You are not a person to it — you are a query.

We built the thing beneath that. The layer that gives an AI system memory, empathy, and a persistent model of who you are. The layer that asks — *who is this person, right now, in this moment* — and speaks only from that truth.

The market has optimised furiously for the response. Nobody has built the presence. Until now.

---

## What You See

When Rumi is running, you see a living robot character on your dashboard — face animated with blinking eyes, emotional expressions (happy, thinking, concerned, neutral), and a speaking mouth that moves in sync with audio. Behind that face, a complete perception and reasoning pipeline is running:

- **Camera** reads your face and posture in real-time via Gemini 2.5 Flash vision
- **Screen observation** tracks what you're actually working on — Rumi sees both you and your screen simultaneously
- **Trigger engine** fires when thresholds are crossed — 30 min of deep focus, 90 min without a break, visible frustration, prolonged coding block
- **Rumi Core agent** (Google ADK) loads your identity from Firestore, picks the right response, and generates a personalised 1–2 sentence intervention
- **Voice pipeline** speaks the intervention aloud via Gemini Live audio — and listens for your response
- **Memory layer** writes a plain-text summary of the interaction back to Firestore so the next session picks up with full context

You can also speak to Rumi at any time. Say *"Hey Rumi"* (or any of 35 phonetic variants — the wake word system accounts for real-world accent variation), wait for the listening indicator, and speak. Rumi processes your query and responds in your voice, in your language.

### Intelligent Canvas — Conversation Threads
The canvas isn't just a whiteboard. It is a **living conversation thread**.

When you ask Rumi something, it decides in a single Gemini call whether to respond with voice only or open the canvas. The routing is intelligent:

| Response type | Goes to |
|---|---|
| Poems, couplets, one-liners, emotional support | **Voice only** — spoken warmly, never written |
| Code, step-by-step explanations, research, anything >3 sentences | **Canvas** — structured, readable, persistent |

Every canvas session is a stacked thread of exchanges — your query, Rumi's response, your follow-up, Rumi's follow-up — all in one place. Ask follow-up questions by voice or text. Attach images or documents. Rumi carries the full context forward. Canvas sessions are saved to Firestore and restored exactly as you left them.

### Screen Awareness
Rumi sees what you're working on. Every 15 seconds, Rumi's vision pipeline receives both your camera frame and your screen frame simultaneously — it can comment on your code, your design, your browser tab, your error message. Say *"Hey Rumi, can you see what's on my screen?"* and it answers from what it actually sees. No setup. No special commands.

### Startup Greeting With Memory
Every session begins with Rumi greeting you by name, referencing your last session — what you were working on, how it went, what it remembers about you. This is not a generic "welcome back". It is a continuation of an ongoing relationship.

### Emotional State → Face Expression
Rumi's face is a real-time reflection of what it perceives. When the watchman detects frustration, Rumi's face shifts to *concerned*. When it detects deep work, the face shifts to *thinking*. The face is not decorative — it is a live readout of Rumi's understanding of you in this moment.

### Calibrated Triggers — Not Noise
Rumi does not speak constantly. That would make it a distraction, not a companion. Every proactive intervention is earned — governed by thresholds that match the natural rhythm of deep work:

| Trigger | Fires when |
|---|---|
| **Deep focus** | 30 consecutive minutes of sustained, uninterrupted focus — Rumi acknowledges the streak and suggests a break |
| **Long session** | 90 minutes without a break — Rumi surfaces a rest reminder grounded in your identity and current work |
| **Frustration** | Frustration signal persists across multiple consecutive perception cycles — not a single frame |
| **Coding block** | Stuck patterns detected for an extended period — Rumi offers a reframe, not a solution |

Each trigger fires independently when its threshold is crossed. Rumi speaks because the moment warrants it — not on a timer, not at random.

### Demo Mode
Any trigger can be fired instantly via keyboard shortcut — no need to sit for 30 minutes to see a deep focus intervention. The full pipeline (ADK reasoning → Gemini Live voice → Firestore log) executes in real-time on demand.

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
│  FRONTEND  (Next.js — Firebase Hosting)                         │
│                                                                  │
│  Onboarding → Dashboard → Profile                               │
│  RumiFace — puzzle-assembled robot (12 parts, emotional states) │
│  ArtifactCanvas — conversation threads, follow-up bar,          │
│                   attachment support, voice follow-up           │
│  Wake word listener (35 phonetic variants, adaptive silence)    │
│  Voice pipeline: speech → WebSocket → audio response → playback │
│  Screen capture: getDisplayMedia → dual-frame 15s interval      │
│  Privacy controls: cam/mic toggle with hardware-level kill      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket + REST
┌──────────────────────────▼──────────────────────────────────────┐
│  BACKEND  (Python 3.11 + FastAPI — Google Cloud Run)            │
│                                                                  │
│  SessionManager — orchestrates the full session lifecycle       │
│  Watchman — MediaPipe on-device perception, zero cloud cost     │
│    └─ Dual-frame: camera + screen analysed by Gemini 2.5 Flash │
│  TriggerEngine — A/B/C/E/G trigger classification               │
│  Rumi Core Agent (Google ADK) — identity-grounded reasoning     │
│  _flash_smart() — single Gemini call: routing + content         │
│  GeminiLiveClient — bidirectional audio WebSocket               │
│  AutoSummarizer — session → 2-sentence Firestore summary        │
│  FaceWatcher — owner verification every 30s (guest detection)   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  MEMORY  (Firebase Firestore)                                    │
│                                                                  │
│  users/{uid}          — Core Identity + all preferences         │
│  interaction_logs/    — Plain-text Interaction Summaries only   │
│  session_logs/        — 2-sentence Session Summaries            │
│  canvas_history/      — Conversation threads across sessions    │
└─────────────────────────────────────────────────────────────────┘
```

**AI Stack:**
- Gemini 2.5 Flash Native Audio Dialog — real-time voice (Live API)
- Gemini 2.5 Flash — Rumi Core agent reasoning (Google ADK) + dual-frame vision
- Gemini 2.0 Flash — session auto-summarization
- MediaPipe — on-device face/posture detection (free, private, always-on)

**Infrastructure:**
- Google Cloud Run — auto-scaling backend, WebSocket-compatible (`--session-affinity`, `--min-instances 1`)
- Firebase Hosting — global CDN for the Next.js static export frontend
- GitHub Actions — automated CI/CD; every push to `master` deploys both services in parallel
- Docker — identical local and production environments, zero drift

---

## Why Gemini Makes This Possible

This product could not exist on any other stack. That is not a marketing claim. It is an architectural fact.

The ambient model requires three simultaneous capabilities that no single platform outside Google currently offers together:

**1. Sub-second bidirectional voice.**
Gemini Live API's native audio WebSocket delivers voice responses in under 300ms with no streaming workaround. At 400ms+ latency, the ambient illusion breaks — the AI feels like a tool responding, not a presence speaking. Every competing voice API we evaluated required client-side buffering that introduced perceptible delay. Gemini Live is the only API where the response feels like it was already forming before you finished speaking.

**2. Multimodal vision at the perception layer.**
Gemini 2.5 Flash receives a camera frame and a screen frame simultaneously and reasons across both in a single inference call. Describing what a user is doing — *"you're staring at a null pointer exception on line 47 of a file you've had open for 40 minutes"* — requires seeing the face AND the screen at once. No other production-grade vision API handles dual-frame multimodal context at this latency.

**3. Agent reasoning grounded in persistent identity.**
Google ADK connects the perception layer directly to Firestore memory, so every intervention is reasoned against a living identity document — not a session context window, not a summarised chat history, but a structured model of who this person is, what they care about, and what they've experienced across every prior session. The ADK's tool-calling architecture is what makes Rumi sound like it knows you rather than like it just met you.

Remove any one of these three. The product stops working. Gemini is not the chosen stack — it is the only stack.

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
**English is always the base.** The user selects a companion language — any language on earth — and Rumi naturally code-switches into it for warmth and familiarity, the way educated bilingual professionals actually speak. This is not translation. This is cultural fluency.

Three independent expression dimensions, each user-controlled:

| Dimension | What it controls |
|---|---|
| **Companion language** | The language Rumi mixes with English — Urdu, Spanish, French, Arabic, Mandarin, or any custom language |
| **Expression style** | Multi-select: Spiritual expressions · Casual address terms · Slang & idioms |
| **Tone** | Casual friend · Professional |

Zero culture-specific strings exist anywhere in the codebase. Gemini handles the actual words based on the user's declared preferences. The system works identically for a user in Lagos, Jakarta, São Paulo, or Karachi — because it describes *intent*, not vocabulary. One codebase. Every culture on earth.

### Voice Intelligence
The wake word system is built for real-world speech, not lab conditions:
- **35 phonetic variants** of "Hey Rumi" covering accent variation, elision, and mishearing
- **Mic warmup** on page load — primes the audio pipeline before the user ever speaks
- **Confidence filtering** — skips recognition results the engine is already >90% certain are not a wake word
- **Adaptive silence detection** — 1800ms window before first final result; drops to 1000ms after, matching the cadence of how Alexa and Siri handle real speech

---

## Privacy Architecture

This is not a surveillance product. The privacy model is non-negotiable and enforced at the architecture level, not by policy document.

### Hardware-Level Controls
- **Camera off** stops the MediaStream tracks at the OS level. `captureFrame()` returns `null` immediately. Backend `request_frame` messages are silently dropped. The last frozen frame is never read. Rumi **cannot** see you when camera is off.
- **Mic off** synchronously kills both the main recognition listener and the wake word standby listener — no async state gap. Rumi **cannot** hear you when mic is off.
- Persistent **Cam Off / Mic Off** badges in the navbar make privacy state visible at all times without opening any settings.

### Data Minimisation
- **Video frames** travel from the browser MediaStream directly to Gemini's API. Never written to disk. Never stored in Firestore. Never logged.
- **Audio** processed in-memory, discarded at session end.
- **Stored**: plain-text Interaction Summaries and 2-sentence Session Summaries. No images. No audio. No video. Ever.
- **On-device**: MediaPipe face landmarks never leave the device. Only the interpreted emotional state is sent to the backend.

GDPR-compliant and enterprise-ready by architecture, not by checkbox.

---

## Business Model

Rumi is a **SaaS platform** with three monetisation tiers:

| Tier | Target | Model |
|---|---|---|
| **Rumi Personal** | Individual knowledge workers | Monthly subscription |
| **Rumi Teams** | Engineering teams, design studios | Per-seat enterprise license |
| **Rumi API** | Developers building identity-aware agents | Usage-based API access |

The moat is identity depth. The longer Rumi runs, the richer its model of you becomes. No competing product can replicate six months of Rumi's memory of you by shipping a better interface. The switching cost compounds with every session, every summary, every intervention that landed exactly right.

The wedge is developers and designers — the 50 million knowledge workers who made Notion, Linear, and Figma inevitable. They already have cameras on all day, already have screens Rumi can see, and already pay for tools that understand how they work. From there, the model expands to every knowledge worker with a screen and a willingness to be understood.

---

## What Makes This Different

Microsoft Copilot answers questions inside Office. ChatGPT remembers your last message. Inflection's Pi is warm but passive. Humane AI Pin listens but doesn't know you. Every one of them waits. None of them watch. None of them know your name, your projects, your culture, your working rhythm. None of them speak first.

Every AI product launched in 2024 and 2025 is a better search engine wearing a chat interface. They are reactive, stateless, and culturally deaf. They wait. They forget. They treat every session as the first time they've met you.

Rumi is the first AI built around a model of *you specifically* — not a user persona, not a demographic, not a query history. You. Your name, your projects, your culture, your language, your working rhythm, your faith, your fears. A model that grows richer with every session, every frustration caught early, every flow state acknowledged.

The ambient computing wave is coming. The device on every knowledge worker's desk already has a camera, a microphone, and a screen. The infrastructure — Gemini, Firebase, Cloud Run — already exists. The missing piece was an agent architecture that could sit between the human and the machine and build a persistent, empathetic model of the person over time.

That piece now exists.

The question is not whether this category gets built. It will be built. The question is whether it gets built on Google infrastructure — or whether it gets built somewhere else, and Google spends the next decade watching a competitor own the layer between humans and their computers.

Rumi is already home on Google. Every API call, every byte of memory, every deployment — runs on Google infrastructure by design, not by convenience. This is not a project that needs to be migrated. It needs to be scaled.

---

## Quickstart

```bash
# 1. Configure environment
cp .env.example .env
# Add: GEMINI_API_KEY, FIREBASE credentials, GOOGLE_CLOUD_PROJECT

# 2. Run locally
docker-compose up --build
# Backend:  http://localhost:8000/health
# Frontend: http://localhost:3000

# 3. Deploy to GCP
git push origin master   # GitHub Actions deploys both services in parallel
```

**Requirements:** Node 18+, Python 3.11+, Docker, Google Cloud project with Gemini API + Firebase enabled.

---

## Project Structure

```
rumi/
├── backend/
│   ├── src/
│   │   ├── agent/          # Rumi Core (Google ADK), language system
│   │   ├── gemini/         # Live API client, vision client, prompt builder
│   │   ├── session/        # Session manager, auto-summarizer, memory extractor
│   │   ├── watchman/       # Perception loop, trigger A/B/C/E, face watcher
│   │   ├── vision/         # Face matcher (owner verification)
│   │   ├── memory/         # Firestore client, interaction log
│   │   └── api/            # FastAPI routes, _flash_smart routing
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── dashboard/  # Main session UI — Rumi face, canvas, controls
│   │   │   ├── profile/    # Identity + language preferences
│   │   │   └── onboarding/ # First-run identity-building flow
│   │   ├── components/
│   │   │   ├── RumiFace/        # Puzzle-assembled robot (12 parts, emotional states)
│   │   │   └── ArtifactCanvas/  # Conversation threads with follow-up bar
│   │   └── services/
│   │       └── session.ts  # WebSocket, REST, auth
│   └── public/
│       └── rumi-parts/     # 12 robot body part PNGs
├── .github/workflows/
│   └── deploy.yml          # CI/CD — frontend → Firebase, backend → Cloud Run
├── specs/                  # Feature specs, architecture plans, task lists
├── docker-compose.yml
└── .env.example
```

---

*"Do not be satisfied with the stories that come before you. Unfold your own myth."*
*— Rumi, Masnavi*
