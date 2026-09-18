"""Post-session memory extractor.

Runs after AutoSummarizer. Reads session interactions + current identity,
asks Gemini to identify what new facts were learned, and patches the
identity document in Firestore.

This is what makes Rumi smarter over time — the more sessions,
the more it knows about the user.
"""
import json
import logging
import os
from datetime import datetime, timezone

from google import genai

from src.memory.firestore_client import get_db

logger = logging.getLogger(__name__)

MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

EXTRACT_PROMPT = """\

You are a memory manager for Rumi, a proactive AI companion.

After each session you receive:
1. The user's current identity profile
2. The session's interaction log (what triggers fired, what was said, how the user responded)

Your job: identify any NEW facts worth updating in the identity profile.
Be conservative — only update if the interactions clearly evidence something new.
Do NOT invent facts. Do NOT repeat what's already there.

Return a JSON object with ONLY the fields that should be updated.
If nothing new was learned, return {}.

Updatable fields:
- work_style (string) — new patterns observed
- immediate_goal (string) — if goal seems to have changed
- driving_fear (string) — if frustration patterns reveal deeper fear
- wellness_trigger (string) — if user consistently accepts/dismisses certain suggestions
- projects (array) — update status of existing projects if clearly evidenced
- interests (array) — add new interests if mentioned

Rules:
- If user dismissed ALL interventions → note in work_style that they prefer minimal interruption
- If user accepted all frustration interventions → note they respond well to Rumi/chai suggestions
- If coding_block triggers fired repeatedly on same session → note that project as "blocked"
- Return valid JSON only. No markdown, no explanation.

Current identity:
{identity_json}

Session interactions:
{interactions_json}

Session summary:
{summary}

JSON patch (or {{}} if nothing new):"""


ALLOWED_CANDIDATE_FIELDS = {
    "work_style", "immediate_goal", "long_term_goal", "driving_fear",
    "wellness_trigger", "projects", "interests", "focus_breakers",
    "communication_preference", "companion_language", "companion_tone",
    "student_context", "environment",
}


class MemoryExtractor:
    """Extracts new facts from a session and patches the user's identity."""

    def __init__(self):
        api_key = os.environ["GEMINI_API_KEY"]
        self._client = genai.Client(api_key=api_key)

    async def extract_and_patch(
        self,
        uid: str,
        session_id: str,
        summary: str = "",
    ) -> dict:
        """Run extraction and patch Firestore. Returns the patch dict (empty = nothing learned)."""
        db = get_db()

        # Load current identity
        try:
            identity_doc = db.collection("users").document(uid).get()
            identity = identity_doc.to_dict() or {}
        except Exception as exc:
            logger.warning("MemoryExtractor: failed to load identity: %s", exc)
            return {}

        # Load session interactions
        try:
            interactions_ref = (
                db.collection("users").document(uid)
                .collection("sessions").document(session_id)
                .collection("interactions").order_by("triggered_at")
            )
            interactions = [
                {
                    "trigger_type": d.get("trigger_type"),
                    "intervention_text": d.get("intervention_text", ""),
                    "user_response": d.get("user_response", "no_response"),
                }
                for d in (doc.to_dict() for doc in interactions_ref.stream())
            ]
        except Exception as exc:
            logger.warning("MemoryExtractor: failed to load interactions: %s", exc)
            return {}

        if not interactions:
            logger.info("MemoryExtractor: no interactions — skipping extraction")
            return {}

        # Sanitise identity for Gemini (remove Firestore-internal fields)
        safe_identity = {
            k: v for k, v in identity.items()
            if k not in ("last_updated", "user_id") and not hasattr(v, "seconds")
        }

        prompt = EXTRACT_PROMPT.format(
            identity_json=json.dumps(safe_identity, ensure_ascii=False, indent=2),
            interactions_json=json.dumps(interactions, ensure_ascii=False, indent=2),
            summary=summary or "(no summary available)",
        )

        patch = None
        for model in MODELS:
            try:
                response = await self._client.aio.models.generate_content(
                    model=model, contents=prompt
                )
                raw = (response.text or "").strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                patch = json.loads(raw.strip())
                if patch and isinstance(patch, dict):
                    break
            except Exception as exc:
                logger.warning("MemoryExtractor (%s) failed: %s", model, exc)
                continue

        if not patch or not isinstance(patch, dict):
            logger.info("MemoryExtractor: nothing new learned this session")
            return {}

        # Save inferred memory candidates with provenance without destroying confirmed profile
        try:
            now = datetime.now(timezone.utc)
            candidates_ref = db.collection("users").document(uid).collection("memory_candidates")
            saved_count = 0
            for field_name, value in patch.items():
                if field_name not in ALLOWED_CANDIDATE_FIELDS:
                    logger.debug("MemoryExtractor: skipping unrecognized field '%s'", field_name)
                    continue

                # De-duplication check: avoid duplicate candidate spam
                existing = list(candidates_ref.where("field", "==", field_name).where("status", "==", "inferred").limit(5).stream())
                is_duplicate = False
                for doc in existing:
                    d = doc.to_dict()
                    if d.get("suggested_value") == value:
                        doc.reference.update({"updated_at": now, "confidence": min(1.0, d.get("confidence", 0.75) + 0.05)})
                        is_duplicate = True
                        break

                if not is_duplicate:
                    candidates_ref.add({
                        "field": field_name,
                        "suggested_value": value,
                        "source_session_id": session_id,
                        "confidence": 0.75,
                        "status": "inferred",
                        "created_at": now,
                    })
                    saved_count += 1

            # Touch timestamp on user document only
            db.collection("users").document(uid).update({"last_memory_extraction_at": now})
            logger.info(
                "MemoryExtractor: saved/updated %d inferred memory candidate(s) for session %s",
                saved_count,
                session_id,
            )
        except Exception as exc:
            logger.warning("MemoryExtractor: Firestore candidate storage failed: %s", exc)
            return {}

        return {k: v for k, v in patch.items() if k != "last_updated"}
