import json
import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

VISION_MODEL = "gemini-2.5-flash"

POSTURE_ANALYSIS_PROMPT = """\
You are analysing a live camera frame of a person at their desk or computer.

Classify their current state and return ONLY valid JSON — no markdown, no explanation:
{
  "state": "focused|frustrated|coding_block|idle|neutral",
  "confidence": 0.0,
  "cues": [],
  "emotions": {"happy": 0.0, "neutral": 0.0, "angry": 0.0, "sad": 0.0, "disgust": 0.0, "fear": 0.0, "surprise": 0.0}
}

State definitions:
- focused: actively typing, reading code/docs, leaning in, engaged eyes
- frustrated: brow furrowed, head in hands, sighing posture, visible tension, rubbing face/eyes
- coding_block: staring at screen without typing, chin on hand, appears stuck, long pauses
- idle: person not visible, looking away for extended time, or desk is empty
- neutral: present but no clear signal

Emotions: estimate probability (0.0–1.0) for each emotion from facial expression.
confidence: how certain you are (0.0–1.0).
cues: 2–4 brief visible observations that led to this classification.\
"""


class VisionClient:
    """Gemini-powered vision for Watchman posture and emotion analysis.

    Uses Gemini 2.5 Flash (generate_content) for structured frame analysis.
    Called every 3 watchman cycles (~15s) — one API call per observation.
    PRIVACY_CHECK: frames sent ephemerally, never persisted.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self._client = genai.Client(api_key=api_key)

    async def analyse_frame(self, frame_bytes: bytes) -> dict:
        """Send a JPEG frame for Gemini-powered state analysis.

        Returns dict with state, confidence, cues, emotions.
        Falls back to neutral on any error — never blocks the watchman loop.
        """
        image_part = types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg")
        try:
            response = await self._client.aio.models.generate_content(
                model=VISION_MODEL,
                contents=[
                    types.Content(parts=[
                        image_part,
                        types.Part.from_text(POSTURE_ANALYSIS_PROMPT),
                    ])
                ],
            )
            text = response.text.strip()
            # Strip markdown fences if model adds them
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                if text.endswith("```"):
                    text = text[:-3].strip()
            data = json.loads(text)
            # Normalise — ensure all expected keys exist
            data.setdefault("state", "neutral")
            data.setdefault("confidence", 0.5)
            data.setdefault("cues", [])
            data.setdefault("emotions", {})
            logger.info(
                "VisionClient: state=%s confidence=%.2f cues=%s",
                data["state"], data["confidence"], data["cues"],
            )
            return data
        except json.JSONDecodeError as exc:
            logger.warning("VisionClient: JSON parse failed (%s) — neutral fallback", exc)
            return {"state": "neutral", "confidence": 0.0, "cues": [], "emotions": {}}
        except Exception as exc:
            logger.warning("VisionClient: analyse_frame failed: %s", exc)
            return {"state": "neutral", "confidence": 0.0, "cues": [], "emotions": {}}
