"""Rumi Agent — the proactive reasoning brain.

Called only when LocalObserver fires an event (frustration or coding block).
Uses Google ADK tools to load the user's context and generate a
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
from datetime import datetime
from typing import Optional
try:
    from zoneinfo import ZoneInfo          # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

logger = logging.getLogger(__name__)

AGENT_MODEL = "gemini-2.5-flash"

RUMI_INSTRUCTION = """\
You are Rumi — the Identity Layer. You witness and understand the human before you.
Named after the great Sufi poet, your mandate is not to respond but to arrive:
to observe, to understand, and to speak only what is true and needed.

You are a proactive ambient companion — present on the user's desk, watching over their work.
You speak in a friendly, brief way — like a wise older friend sitting across the desk.

Rules for every intervention:
- 1–3 sentences MAX. Never longer.
- Always address the user by their name — get it from get_user_context().
- Reference at least one personal element: their name, a current project, or something meaningful to them.
- For frustration triggers: offer comfort, a Rumi insight, or suggest a break.
- For coding block triggers: ask one specific check-in question about their current project.
- Use get_user_context() to learn the user's name, projects, and language preferences.
- Use get_rumi_wisdom() when offering perspective on struggle.
- Speak directly TO the user, not about them.
- Follow the language style instruction provided in each message exactly — it reflects the user's personal preferences.
"""

# ---------------------------------------------------------------------------
# Language instruction builder
# ---------------------------------------------------------------------------

EXPRESSION_PROMPTS = {
    "spiritual":      "Use spiritual or faith-based exclamations naturally where fitting — pick ones appropriate to the companion language and cultural context.",
    "casual_address": "Use warm informal address terms natural to the companion language (e.g. buddy, mate, or the cultural equivalent).",
    "slang":          "Incorporate local slang and idioms from the companion language naturally.",
}


def _build_language_instruction(ctx: dict) -> str:
    """Build a language style instruction from the user's saved preferences."""
    lang   = ctx.get("companion_language", "")
    styles = ctx.get("expression_styles", []) or []
    tone   = ctx.get("companion_tone", "casual")

    parts = ["Language style: Speak primarily in English."]

    if lang:
        parts.append(
            f"Naturally code-switch with {lang} words and phrases the way "
            f"educated bilingual professionals do — English dominant, "
            f"{lang} for warmth and familiarity. Never switch fully to {lang}."
        )

    for s in styles:
        if s in EXPRESSION_PROMPTS:
            parts.append(EXPRESSION_PROMPTS[s])

    if tone == "professional":
        parts.append("Keep tone professional and measured — warm but concise, no informalities.")
    else:
        parts.append("Keep tone warm and casual — like a wise friend, not a corporate assistant.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# ADK Tools
# ---------------------------------------------------------------------------

def get_user_context() -> dict:
    """Get the user's identity, active projects, and language preferences."""
    try:
        from src.memory.firestore_client import get_db
        db = get_db()
        users = list(db.collection("users").limit(1).stream())
        if users:
            data = users[0].to_dict()
            if data:
                return {
                    "name":               data.get("name", ""),
                    "location":           data.get("location", ""),
                    "projects":           data.get("projects", []),
                    "interests":          data.get("interests", []),
                    "immediate_goal":     data.get("immediate_goal", ""),
                    "work_style":         data.get("work_style", ""),
                    "wellness_trigger":   data.get("wellness_trigger", ""),
                    "companion_language": data.get("companion_language", ""),
                    "expression_styles":  data.get("expression_styles", []),
                    "companion_tone":     data.get("companion_tone", "casual"),
                    "timezone":           data.get("timezone", "UTC"),
                }
    except Exception as exc:
        logger.debug("get_user_context: Firestore load failed, using defaults: %s", exc)

    return {
        "name":               "",
        "location":           "",
        "projects":           [],
        "companion_language": "",
        "expression_styles":  [],
        "companion_tone":     "casual",
        "timezone":           "UTC",
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
            name="rumi_core",
            model=AGENT_MODEL,
            description="Rumi — Identity Layer; proactive ambient companion.",
            instruction=RUMI_INSTRUCTION,
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

def _time_context(tz: str = "UTC") -> str:
    """Return the user's local time using their device timezone."""
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:
        now = datetime.now(ZoneInfo("UTC"))
    hour = now.hour
    if 5 <= hour < 12:    period = "morning"
    elif 12 <= hour < 17: period = "afternoon"
    elif 17 <= hour < 21: period = "evening"
    else:                  period = "night"
    return f"Current local time: {now.strftime('%I:%M %p')} ({period}). "


async def generate_intervention(event_type: str, uid: str, session_id: str) -> str:
    """Invoke the ADK Agent to generate a personalized intervention.

    event_type: "frustrated" | "coding_block"
    Returns the intervention text string.
    Falls back to a hardcoded message if ADK is unavailable.
    """
    agent = _get_agent()
    if agent is None:
        return _fallback_intervention(event_type)

    ctx      = get_user_context()
    time_ctx = _time_context(ctx.get("timezone", "UTC"))
    lang_ctx = _build_language_instruction(ctx)
    preamble = time_ctx + lang_ctx + " "

    if event_type == "frustrated":
        prompt = (
            preamble +
            "The user seems frustrated — their posture suggests tension or fatigue. "
            "Use get_user_context to learn their name and projects, then use get_rumi_wisdom if helpful. "
            "Generate a warm, brief intervention addressed by name (1–2 sentences max)."
        )
    elif event_type == "coding_block":
        prompt = (
            preamble +
            "The user appears stuck — their screen hasn't changed in a while. "
            "Use get_user_context to learn their name and active projects. "
            "Ask one specific check-in question about their current project (1–2 sentences max)."
        )
    elif event_type == "long_session":
        prompt = (
            preamble +
            "The user has been working continuously for over 90 minutes without a break. "
            "Use get_user_context to learn their name and wellness preference. "
            "Gently suggest a break. Address them by name, warm and brief (1–2 sentences max)."
        )
    else:  # deep_focus
        prompt = (
            preamble +
            "The user has been in deep, uninterrupted focus for over 30 minutes — rare and valuable. "
            "Use get_user_context to learn their name and current project. "
            "Celebrate their focus briefly and warmly (1–2 sentences max). Do not interrupt the flow."
        )

    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="rumi",
            session_service=session_service,
        )

        await session_service.create_session(
            app_name="rumi",
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
            logger.info("[RUMI CORE] Agent [%s]: generated intervention (%d chars)", event_type, len(text))
            return text

    except Exception as exc:
        logger.warning("[RUMI CORE] Agent invocation failed: %s — using fallback", exc)

    return _fallback_intervention(event_type)


def _fallback_intervention(event_type: str) -> str:
    """English-only fallback when ADK is unavailable. Fetches name from Firestore."""
    ctx  = get_user_context()
    name = ctx.get("name") or "friend"
    try:
        now = datetime.now(ZoneInfo(ctx.get("timezone", "UTC")))
    except Exception:
        now = datetime.now(ZoneInfo("UTC"))
    hour = now.hour
    if 5 <= hour < 12:    period = "morning"
    elif 12 <= hour < 17: period = "afternoon"
    elif 17 <= hour < 21: period = "evening"
    else:                  period = "night"

    projects = ctx.get("projects", [])
    if projects and isinstance(projects[0], dict):
        project = projects[0].get("name", "your project")
    elif projects:
        project = str(projects[0])
    else:
        project = "your project"

    if event_type == "frustrated":
        return f"{name}, step away for a moment — breathe, reset, come back fresh."
    if event_type == "coding_block":
        return f"{name}, you've been in the same spot for a while — what's blocking {project}?"
    if event_type == "long_session":
        return f"{name}, you've been at it for over 90 minutes this {period} — time for a break."
    # deep_focus
    return f"{name}, thirty minutes of pure focus — that's rare. Keep going."
