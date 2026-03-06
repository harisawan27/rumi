import json
import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

VISION_MODEL = "gemini-2.5-flash"

POSTURE_ANALYSIS_PROMPT = (
    "Analyse the person's posture and desk state in this frame. "
    "Respond with JSON only — no markdown, no explanation: "
    '{"state": "focused|frustrated|idle|neutral", '
    '"confidence": 0.0, '
    '"cues": []}'
)


class VisionClient:
    """Single-call vision client for Watchman posture analysis.

    Uses Gemini 2.5 Flash (free tier) for posture and desk state analysis.
    PRIVACY_CHECK: frames are sent ephemerally — never persisted.
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self._client = genai.Client(api_key=api_key)

    async def analyse_frame(self, frame_bytes: bytes) -> dict:
        """Send a single JPEG frame for posture analysis.

        Returns a dict with state, confidence, cues.
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
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            logger.info(
                "VisionClient: state=%s confidence=%.2f",
                data.get("state"), data.get("confidence"),
            )
            return data
        except json.JSONDecodeError:
            logger.warning("VisionClient: JSON parse failed, returning neutral")
            return {"state": "neutral", "confidence": 0.0, "cues": []}
        except Exception as exc:
            logger.warning("VisionClient: analyse_frame failed: %s", exc)
            return {"state": "neutral", "confidence": 0.0, "cues": []}
