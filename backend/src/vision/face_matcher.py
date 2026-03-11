"""Gemini Vision face comparison — hackathon-grade owner verification.

Production path: replace with MediaPipe Face Recognition (local embeddings,
zero API cost, GDPR-clean). This Gemini approach is sufficient for demo.

Usage:
    result = await compare_faces(owner_photo_url, current_frame_b64)
    if result.is_owner:
        ...
"""
import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class FaceMatchResult:
    is_owner: bool
    confidence: float   # 0.0 – 1.0
    reason: str


_OWNER_THRESHOLD = 0.65   # below this → treat as guest


async def compare_faces(
    owner_photo_url: str,
    current_frame_b64: str,
) -> FaceMatchResult:
    """Compare owner reference photo against a live frame using Gemini Vision.

    Returns FaceMatchResult. On any error → assumes owner (fail-safe, avoids
    false guest triggers from API timeouts or bad frames).
    """
    if not owner_photo_url or not current_frame_b64:
        return FaceMatchResult(is_owner=True, confidence=1.0, reason="no_reference")

    try:
        # Download owner reference photo
        async with httpx.AsyncClient(timeout=8) as client:
            ref_resp = await client.get(owner_photo_url)
            ref_resp.raise_for_status()
            ref_b64 = base64.b64encode(ref_resp.content).decode()

        prompt = (
            "You are a face verification system. "
            "Image 1 is the owner's reference photo. Image 2 is a live camera frame.\n"
            "Task: Determine if the person in Image 2 is the same individual as in Image 1.\n"
            "Consider: lighting differences, angles, and natural variation are acceptable.\n"
            "Reply ONLY with valid JSON, no markdown:\n"
            '{"is_same_person": true_or_false, "confidence": 0.0_to_1.0, "reason": "brief"}'
        )

        from google import genai as _genai
        from google.genai import types as _types

        client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        frame_bytes = base64.b64decode(current_frame_b64)
        ref_bytes   = base64.b64decode(ref_b64)

        contents = [
            _types.Part(inline_data=_types.Blob(data=ref_bytes,   mime_type="image/jpeg")),
            _types.Part(inline_data=_types.Blob(data=frame_bytes, mime_type="image/jpeg")),
            _types.Part(text=prompt),
        ]

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
        )
        raw = (response.text or "").strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        confidence = float(parsed.get("confidence", 0.5))
        is_owner   = parsed.get("is_same_person", True) and confidence >= _OWNER_THRESHOLD

        logger.debug("face_matcher: confidence=%.2f is_owner=%s reason=%s",
                     confidence, is_owner, parsed.get("reason", ""))
        return FaceMatchResult(
            is_owner=is_owner,
            confidence=confidence,
            reason=parsed.get("reason", ""),
        )

    except Exception as exc:
        logger.warning("face_matcher: comparison failed (%s) — assuming owner", exc)
        return FaceMatchResult(is_owner=True, confidence=1.0, reason=f"error:{exc}")
