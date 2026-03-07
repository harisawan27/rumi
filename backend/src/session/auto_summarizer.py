import logging
import os
from datetime import datetime, timezone

from google import genai

from src.memory.firestore_client import get_db

logger = logging.getLogger(__name__)

AUTO_SUMMARIZER_MODEL = "gemini-2.0-flash"

AUTO_SUMMARIZER_PROMPT_TEMPLATE = """\
You are a concise session summarizer for Rumi. Given the following interaction log
from a session with {name}, write EXACTLY 2 sentences summarizing:
1. The key emotional or cognitive states detected.
2. The most notable intervention offered and the user's response.

Do not include any implementation details, model names, or system information.
Write in third person, past tense. Plain text only — no bullet points, no markdown.

Interaction log:
{interaction_log_json}
"""


class AutoSummarizer:
    """Generates a 2-sentence session summary using Gemini 2.0 Flash (non-streaming)."""

    def __init__(self):
        api_key = os.environ["GEMINI_API_KEY"]
        self._client = genai.Client(api_key=api_key)

    async def summarize(self, uid: str, session_id: str) -> str:
        """Read all Interaction Summaries for the session; call Gemini; return 2-sentence text."""
        import json

        db = get_db()

        # Load user's name for personalised summary
        try:
            user_doc = db.collection("users").document(uid).get()
            name = (user_doc.to_dict() or {}).get("name", "The user")
        except Exception:
            name = "The user"

        interactions_ref = (
            db.collection("users")
            .document(uid)
            .collection("sessions")
            .document(session_id)
            .collection("interactions")
            .order_by("triggered_at")
        )
        interactions = [doc.to_dict() for doc in interactions_ref.stream()]

        if not interactions:
            return (
                f"{name} completed a session without any detected triggers. "
                f"No interventions were offered during this session."
            )

        # Sanitise: remove any non-text fields before sending to Gemini
        safe_interactions = [
            {
                "trigger_type": i.get("trigger_type"),
                "triggered_at": str(i.get("triggered_at", "")),
                "intervention_text": i.get("intervention_text", ""),
                "user_response": i.get("user_response", "no_response"),
            }
            for i in interactions
        ]

        prompt = AUTO_SUMMARIZER_PROMPT_TEMPLATE.format(
            name=name,
            interaction_log_json=json.dumps(safe_interactions, ensure_ascii=False, indent=2)
        )

        response = await self._client.aio.models.generate_content(
            model=AUTO_SUMMARIZER_MODEL, contents=prompt
        )
        text = response.text.strip()

        # Validate: must be exactly 2 sentences
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if len(sentences) < 2:
            logger.warning("AutoSummarizer: response has fewer than 2 sentences — using as-is")
        return text

    async def save_summary(
        self,
        uid: str,
        session_id: str,
        summary_text: str,
        duration_minutes: float,
    ) -> str:
        """Write Session Summary to Firestore; update parent session with summary_id.

        Implements one retry on Firestore write failure before logging error.
        """
        db = get_db()
        from datetime import date as date_type
        today = date_type.today().isoformat()
        doc = {
            "user_id": uid,
            "session_id": session_id,
            "session_date": today,
            "summary_text": summary_text,
            "session_duration_minutes": round(duration_minutes, 1),
            "created_at": datetime.now(timezone.utc),
        }

        summary_id = None
        for attempt in range(2):
            try:
                _, ref = (
                    db.collection("users")
                    .document(uid)
                    .collection("session_summaries")
                    .add(doc)
                )
                summary_id = ref.id
                ref.update({"summary_id": summary_id})
                # Update parent session document
                db.collection("users").document(uid).collection("sessions").document(
                    session_id
                ).update({"session_summary_id": summary_id})
                logger.info("AutoSummarizer: summary saved — %s", summary_id)
                return summary_id
            except Exception as exc:
                if attempt == 0:
                    logger.warning("AutoSummarizer: Firestore write failed, retrying: %s", exc)
                else:
                    logger.error("AutoSummarizer: Firestore write failed after retry: %s", exc)
        return ""

    async def summarize_and_save(
        self,
        uid: str,
        session_id: str,
        ended_at: datetime,
    ) -> tuple[str, str]:
        """Full pipeline: summarize + save. Returns (summary_id, summary_text)."""
        # Retrieve session start time to compute duration
        try:
            db = get_db()
            session_doc = (
                db.collection("users").document(uid).collection("sessions").document(session_id).get()
            )
            session_data = session_doc.to_dict() or {}
            started_at = session_data.get("started_at")
            if started_at and ended_at:
                duration_minutes = (ended_at - started_at).total_seconds() / 60
            else:
                duration_minutes = 0.0
        except Exception:
            duration_minutes = 0.0

        summary_text = await self.summarize(uid, session_id)
        summary_id = await self.save_summary(uid, session_id, summary_text, duration_minutes)
        return summary_id, summary_text
