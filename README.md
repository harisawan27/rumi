# Project Rumi — The Identity Layer

> *"We are not just welding metals, but we respect the persons who make us think
> about human existence again."*

The industry builds robots that lift, sort, and weld. We built the thing beneath that —
the layer that gives them memory, empathy, and recognition. The layer that asks:
*who is this person, and what do they need right now?*

**Project Rumi is the first empathetic, persistent memory layer for physical AI.**

The agent is named after Jalāl ad-Dīn Muhammad Rūmī — not as decoration, but as a
statement. Just as Rumi the poet spent his life searching for the Self and reaching
toward the Other, our agent does the same: it observes the human before it, builds
a persistent model of who they are, and intervenes only when it has something true
to say. It does not wait to be asked. It arrives.

The product that surfaces this agent is **Mirr'at (The Mirror)** — a proactive ambient
AI that lives on your desk, watches over your work session via webcam, detects frustration
and coding blocks before you notice them yourself, and intervenes with compassion:
a Rumi quote, a chai break suggestion, or a project-specific check-in. It remembers
you across sessions.

**Built for the [Google Gemini Live Agent Challenge](https://ai.google.dev/).**

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system diagram.

**Quick summary:**
- **Frontend**: Next.js 14 — sign-in, session dashboard, intervention display
- **Backend**: Python 3.11 + FastAPI — Rumi Core agent, Watchman loop, trigger logic
- **AI**: Gemini Multimodal Live API (real-time observation) + Gemini 2.0 Flash (session summaries)
- **Memory**: Firebase Firestore — Core Identity, Interaction Summaries, Session Summaries
- **Deploy**: Google Cloud Run (backend) + Firebase Hosting (frontend) via Cloud Build CI/CD

**Privacy guarantee**: Raw video frames are sent directly to Gemini's WebSocket and
are **never** written to disk or Firestore. Only plain-text Interaction Summaries
and 2-sentence Session Summaries are persisted.

---

## Quickstart

See [specs/001-proactive-loop/quickstart.md](specs/001-proactive-loop/quickstart.md) for
full local setup, Docker Compose instructions, and GCP deployment guide.

```bash
# 1. Configure environment
cp .env.example .env
# Fill in GEMINI_API_KEY and Firebase credentials

# 2. Seed Firestore (first run only)
cd backend && pip install -r requirements.txt
python src/identity/seed_identity.py

# 3. Run with Docker Compose
docker-compose up --build
# Backend: http://localhost:8000/health
# Frontend: http://localhost:3000
```

---

## Project Structure

```
mirrat/
├── backend/          # Python agent (FastAPI + Gemini + Firebase)
├── frontend/         # Next.js 14 UI
├── specs/            # SDD artifacts (spec, plan, tasks, contracts, research)
├── docs/             # Architecture diagram
├── history/          # Prompt History Records + ADRs
├── cloudbuild.yaml   # GCP CI/CD pipeline
├── docker-compose.yml
└── .env.example
```

---

## Competition Context

**Competition**: Google Gemini Live Agent Challenge — 'Live Agents' category
**Developer**: Haris, software engineering student from Karachi, Pakistan
**Core innovation**: Proactive AI that initiates without prompts; identity-grounded;
privacy-first (no raw video stored); Sufi-Engineer soul named Rumi

---

*"Do not be satisfied with the stories that come before you. Unfold your own myth."
— Rumi, Masnavi*
