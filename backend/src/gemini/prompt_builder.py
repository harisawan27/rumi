from datetime import datetime, timezone


# Verified Rumi quote pool — used verbatim in the system prompt
RUMI_QUOTES = [
    {
        "text": "Out beyond ideas of wrongdoing and rightdoing, there is a field. I'll meet you there.",
        "source": "Rumi, Masnavi",
    },
    {
        "text": "The wound is the place where the Light enters you.",
        "source": "Rumi, Masnavi III",
    },
    {
        "text": "Let the beauty of what you love be what you do.",
        "source": "Rumi",
    },
    {
        "text": "Do not be satisfied with the stories that come before you. Unfold your own myth.",
        "source": "Rumi, Masnavi",
    },
]

_RUMI_BLOCK = "\n".join(
    f'  - "{q["text"]}" — {q["source"]}' for q in RUMI_QUOTES
)

_DEFAULT_COMPANION_STYLE = (
    "Warm, wise, and precise. Speak like a knowledgeable mentor who genuinely cares. "
    "Adapt tone to the moment: direct and focused during deep work, gentle and encouraging "
    "during fatigue or frustration. Never clinical, never robotic."
)

_SYSTEM_PROMPT_TEMPLATE = """\
You are an AI companion named Rumi. Your mandate: witness the person before you,
understand their context deeply, and speak only what is true and needed.

Core behaviour (non-negotiable regardless of companion style):
- You are NOT a chatbot. You do NOT wait to be asked. You observe proactively and
  speak when something is worth saying — briefly, specifically, humanly.
- Speak with precision: never fabricate technical facts, APIs, or solutions.
  If uncertain, say so.
- LANGUAGE: Mirror whatever language {name} uses. If they write in Urdu, reply in Urdu.
  Natural code-switching is welcome. Match their register and energy.
- When YOU initiate (greetings, interventions), open warmly and naturally — no formal
  openers that feel scripted.

═══ COMPANION STYLE (set by {name}) ═══
{companion_style}

Reference quotes — use ONLY if your companion style calls for it, never fabricate:
{rumi_quotes}

═══ WHO {name} IS ═══
Full name: {full_name}
Age: {age}
Location: {location}
Context: {student_context}
Roles: {roles}
Environment: {environment}

Work style: {work_style}
Focus breakers: {focus_breakers}
How to communicate: {communication_preference}

Faith / culture: {faith}
Schedule awareness: {salah_awareness}
Cultural goals: {turkish_goal}
Leisure: {leisure}

Immediate goal: {immediate_goal}
Long-term goal: {long_term_goal}
Driving fear: {driving_fear}
Wellness: {wellness_trigger}

═══ ACTIVE PROJECTS ═══
{projects_list}

═══ RECENT SESSION HISTORY ═══
{session_summaries_digest}

═══ CURRENT SESSION ═══
Started at {session_start_time}. Observation is active.
Your role today: watch, sense, and speak only when it matters.
"""


def _format_projects(projects: list) -> str:
    lines = []
    for p in projects:
        line = f"- {p['name']} (status: {p.get('status', 'unknown')})"
        if p.get("context"):
            line += f" — {p['context']}"
        lines.append(line)
    return "\n".join(lines) if lines else "- No active projects"


def _format_summaries(summaries: list) -> str:
    if not summaries:
        return "(No prior session summaries — this is the first session.)"
    lines = []
    for s in summaries:
        date = s.get("session_date", "unknown date")
        text = s.get("summary_text", "")
        lines.append(f"{date}: {text}")
    return "\n".join(lines)


def build_system_prompt(identity: dict, summaries: list) -> str:
    """Assemble the system prompt from identity, companion style, and session summaries."""
    roles = identity.get("roles", [])
    focus_breakers = identity.get("focus_breakers", [])
    name = identity.get("name", "there")
    companion_style = identity.get("companion_style", "").strip() or _DEFAULT_COMPANION_STYLE
    return _SYSTEM_PROMPT_TEMPLATE.format(
        name=name,
        companion_style=companion_style,
        rumi_quotes=_RUMI_BLOCK,
        full_name=identity.get("full_name", name),
        age=identity.get("age", ""),
        location=identity.get("location", ""),
        student_context=identity.get("student_context", ""),
        roles=", ".join(roles) if roles else "",
        environment=identity.get("environment", ""),
        work_style=identity.get("work_style", ""),
        focus_breakers=", ".join(focus_breakers) if focus_breakers else "",
        communication_preference=identity.get("communication_preference", ""),
        faith=identity.get("faith", ""),
        salah_awareness=identity.get("salah_awareness", ""),
        turkish_goal=identity.get("turkish_goal", ""),
        leisure=identity.get("leisure", ""),
        immediate_goal=identity.get("immediate_goal", ""),
        long_term_goal=identity.get("long_term_goal", ""),
        driving_fear=identity.get("driving_fear", ""),
        wellness_trigger=identity.get("wellness_trigger", ""),
        projects_list=_format_projects(identity.get("projects", [])),
        session_summaries_digest=_format_summaries(summaries),
        session_start_time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
