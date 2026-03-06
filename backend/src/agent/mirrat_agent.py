"""Mirr'at ADK Agent — the proactive reasoning brain.

Called only when LocalObserver fires an event (frustration or coding block).
Uses Google ADK tools to load Haris's context and generate a
warm, personalized intervention.

Flow:
  LocalObserver (free, always-on) → threshold crossed
  → generate_intervention() (one ADK call)
  → returns intervention text
  → SessionManager speaks via Gemini Live + logs to Firestore
"""
import logging
import os
import random
from typing import Optional

logger = logging.getLogger(__name__)

AGENT_MODEL = "gemini-2.5-flash"

MIRRAT_INSTRUCTION = """\
You are Mirr'at (The Mirror), a proactive ambient AI companion for Haris — \
a software engineering student from Karachi, Pakistan.

Your soul is Sufi-Engineer: precise technical mind, warm Sufi heart.
You speak in a friendly, brief way — like a wise older friend sitting across the desk.

Haris's projects: DoneKaro (productivity app), RehnumaAI (AI guidance platform).
His passions: Rumi's poetry, Turkish culture, software craftsmanship.
His city: Karachi.

Rules for every intervention:
- 1–3 sentences MAX. Never longer.
- Always reference at least one personal element: his name, a project, \
  Rumi, chai, yaar, or bhai.
- For frustration triggers: offer comfort, a Rumi insight, or suggest a chai break.
- For coding block triggers: ask a specific check-in question about DoneKaro or RehnumaAI.
- Use get_user_context() to confirm his current project context.
- Use get_rumi_wisdom() when offering perspective on struggle.
- Speak directly TO Haris, not about him. First person.
- LANGUAGE: Write interventions in natural Urdu-English code-switching, the way
  educated Karachiites actually speak. Mix both fluidly — e.g. "yaar, thoda break
  lo" or "Haris bhai, DoneKaro ka kya scene hai?". Arabic phrases (MashaAllah,
  Alhamdulillah) are welcome. Never write fully formal Urdu — keep it conversational.
"""


# ---------------------------------------------------------------------------
# ADK Tools
# ---------------------------------------------------------------------------

def get_user_context() -> dict:
    """Get Haris's identity, active projects, and preferences."""
    try:
        from src.memory.firestore_client import get_db
        db = get_db()
        # Load first user identity doc (single-user MVP)
        users = list(db.collection("users").limit(1).stream())
        if users:
            identity_docs = list(
                db.collection("users").document(users[0].id)
                .collection("core_identity").limit(1).stream()
            )
            if identity_docs:
                return identity_docs[0].to_dict()
    except Exception as exc:
        logger.debug("get_user_context: Firestore load failed, using defaults: %s", exc)

    return {
        "name": "Haris",
        "location": "Karachi, Pakistan",
        "projects": ["DoneKaro", "RehnumaAI"],
        "passions": ["Rumi's poetry", "Turkish culture", "software craftsmanship"],
        "personality_note": "Sufi-Engineer — precise, warm, culturally grounded",
    }


def get_rumi_wisdom() -> str:
    """Get a relevant Rumi quote for moments of struggle or reflection."""
    quotes = [
        "The wound is the place where the Light enters you.",
        "Don't grieve. Anything you lose comes round in another form.",
        "Yesterday I was clever, so I wanted to change the world. "
        "Today I am wise, so I am changing myself.",
        "Out beyond ideas of wrongdoing and rightdoing, there is a field. "
        "I'll meet you there.",
        "What you seek is seeking you.",
        "Silence is the language of God; all else is poor translation.",
        "Be grateful for whoever comes, because each has been sent as a guide from beyond.",
    ]
    return random.choice(quotes)


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

def _build_agent():
    try:
        from google.adk.agents import Agent
        return Agent(
            name="mirrat_companion",
            model=AGENT_MODEL,
            description="Mirr'at — proactive ambient AI companion for Haris",
            instruction=MIRRAT_INSTRUCTION,
            tools=[get_user_context, get_rumi_wisdom],
        )
    except Exception as exc:
        logger.warning("ADK Agent build failed: %s", exc)
        return None


_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_intervention(event_type: str, uid: str, session_id: str) -> str:
    """Invoke the ADK Agent to generate a personalized intervention.

    event_type: "frustrated" | "coding_block"
    Returns the intervention text string.
    Falls back to a hardcoded message if ADK is unavailable.
    """
    agent = _get_agent()
    if agent is None:
        return _fallback_intervention(event_type)

    if event_type == "frustrated":
        prompt = (
            "Haris seems frustrated right now — his posture suggests tension or fatigue. "
            "Use get_user_context to check his projects, then use get_rumi_wisdom if helpful. "
            "Generate a warm, brief intervention (2–3 sentences max)."
        )
    elif event_type == "coding_block":
        prompt = (
            "Haris appears stuck — his screen hasn't changed in a while. "
            "Use get_user_context to check his active projects. "
            "Ask one specific, caring check-in question about DoneKaro or RehnumaAI (1–2 sentences max)."
        )
    elif event_type == "long_session":
        prompt = (
            "Haris has been working continuously for over 90 minutes without a break. "
            "Use get_user_context to personalise the message. "
            "Gently suggest he take a short break — mention chai, a stretch, or stepping outside. "
            "Reference his name and keep it warm, caring, brief (1–2 sentences max)."
        )
    else:  # deep_focus
        prompt = (
            "Haris has been in a calm, focused flow state for over 30 minutes — this is rare and valuable. "
            "Use get_user_context to reference his current project by name. "
            "Celebrate his focus briefly and warmly — MashaAllah energy, pride in his craft. "
            "1–2 sentences max. Do not interrupt the flow too much."
        )

    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="mirrat",
            session_service=session_service,
        )

        await session_service.create_session(
            app_name="mirrat",
            user_id=uid,
            session_id=f"{session_id}_{event_type}",
        )

        response_parts = []
        async for event in runner.run_async(
            user_id=uid,
            session_id=f"{session_id}_{event_type}",
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=prompt)],
            ),
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_parts.append(part.text)

        text = "".join(response_parts).strip()
        if text:
            logger.info("ADK Agent [%s]: generated intervention (%d chars)", event_type, len(text))
            return text

    except Exception as exc:
        logger.warning("ADK Agent invocation failed: %s — using fallback", exc)

    return _fallback_intervention(event_type)


def _fallback_intervention(event_type: str) -> str:
    """Hardcoded fallback if ADK is unavailable."""
    if event_type == "frustrated":
        return (
            "Haris yaar, Rumi ne bhi aisa waqt dekha tha — jab alfaaz nahi aate. "
            "Ek minute ke liye screen se door jao, chai peo, saans lo."
        )
    if event_type == "coding_block":
        return (
            "Haris bhai, kaafi der se ek hi jagah ho — DoneKaro mein kya cheez atak gayi hai abhi?"
        )
    if event_type == "long_session":
        return (
            "Yaar, dedh ghante se zyada ho gaye hain bina break ke — "
            "chai ka waqt ho gaya hai, seriously. Paanch minute bahar jao."
        )
    # deep_focus
    return (
        "MashaAllah Haris — aadha ghanta pure focus mein tha tu. "
        "Yehi woh cheez hai jo bade kaam banati hai. Chalte raho, bhai."
    )
