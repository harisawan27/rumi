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

MODEL = "gemini-2.0-flash"

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

        try:
            response = await self._client.aio.models.generate_content(
                model=MODEL, contents=prompt
            )
            raw = response.text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            patch = json.loads(raw.strip())
        except Exception as exc:
            logger.warning("MemoryExtractor: Gemini call failed: %s", exc)
            return {}

        if not patch or not isinstance(patch, dict):
            logger.info("MemoryExtractor: nothing new learned this session")
            return {}

        # Apply patch to Firestore
        try:
            patch["last_updated"] = datetime.now(timezone.utc)
            db.collection("users").document(uid).update(patch)
            logger.info(
                "MemoryExtractor: identity patched — %d field(s) updated: %s",
                len(patch) - 1,
                list(patch.keys()),
            )
        except Exception as exc:
            logger.warning("MemoryExtractor: Firestore patch failed: %s", exc)
            return {}

        return {k: v for k, v in patch.items() if k != "last_updated"}
