"""Visual presence verification layer.

NOTE: This is a probabilistic visual presence confirmation layer for ambient assistance,
NOT a cryptographic or biometric-grade authentication system.

Usage:
    result = await compare_faces(owner_photo_url, current_frame_b64)
    if result.status == FaceVerificationStatus.OWNER:
        ...
"""
import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class FaceVerificationStatus(str, Enum):
    OWNER = "OWNER"
    KNOWN_PERSON = "KNOWN_PERSON"
    UNKNOWN_PERSON = "UNKNOWN_PERSON"
    NO_FACE = "NO_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    NO_REFERENCE = "NO_REFERENCE"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


@dataclass
class FaceMatchResult:
    is_owner: bool
    confidence: float   # 0.0 – 1.0
    reason: str
    face_detected: bool = True
    status: FaceVerificationStatus = FaceVerificationStatus.UNKNOWN_PERSON


_OWNER_THRESHOLD = 0.65   # below this → treat as unknown/guest


async def fetch_reference_photo_b64(photo_url: str) -> Optional[str]:
    """Securely load reference portrait bytes.

    Supports:
    - Base64 data URIs ("data:image/jpeg;base64,...")
    - Private Cloud Storage URIs ("gs://bucket/path") via server-side admin credentials
    - Firebase Storage URLs ("https://firebasestorage.googleapis.com/...") via admin credentials
    - Standard HTTPS URLs with fallback to authenticated download
    """
    if not photo_url:
        return None

    if photo_url.startswith("data:"):
        parts = photo_url.split(",", 1)
        return parts[1] if len(parts) > 1 else None

    # Server-side Firebase Admin Storage access for private blobs
    is_storage_target = (
        photo_url.startswith("gs://")
        or "firebasestorage.googleapis.com" in photo_url
        or "storage.googleapis.com" in photo_url
    )

    if is_storage_target:
        try:
            from firebase_admin import storage as _fb_storage
            import urllib.parse
            bucket = _fb_storage.bucket()

            blob_path = None
            if photo_url.startswith("gs://"):
                parts = photo_url[5:].split("/", 1)
                if len(parts) == 2:
                    blob_path = parts[1]
            elif "firebasestorage.googleapis.com" in photo_url:
                if "/o/" in photo_url:
                    raw_path = photo_url.split("/o/")[1].split("?")[0]
                    blob_path = urllib.parse.unquote(raw_path)
            elif "storage.googleapis.com" in photo_url and "Signature=" not in photo_url:
                parts = photo_url.split("storage.googleapis.com/")[1].split("/", 1)
                if len(parts) == 2:
                    blob_path = parts[1].split("?")[0]

            if blob_path:
                blob = bucket.blob(blob_path)
                data = await asyncio.get_event_loop().run_in_executor(None, blob.download_as_bytes)
                if data:
                    return base64.b64encode(data).decode()
        except Exception as exc:
            logger.debug("fetch_reference_photo_b64: admin storage fetch failed (%s) — falling back to HTTP", exc)

    # Remote HTTP URL (including signed URLs or third-party avatars)
    if photo_url.startswith("http://") or photo_url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                ref_resp = await client.get(photo_url)
                ref_resp.raise_for_status()
                return base64.b64encode(ref_resp.content).decode()
        except Exception as exc:
            logger.warning("fetch_reference_photo_b64: HTTP fetch failed: %s", exc)

    return None


async def compare_faces(
    owner_photo_url: str,
    current_frame_b64: str,
) -> FaceMatchResult:
    """Compare reference photo against a live frame using Gemini Vision.

    Fail-safe design: on any error, timeout, or missing data, returns
    VERIFICATION_UNAVAILABLE or appropriate non-owner status. Never falsely authenticates.
    """
    if not owner_photo_url:
        return FaceMatchResult(
            is_owner=False,
            confidence=0.0,
            reason="no_reference",
            face_detected=False,
            status=FaceVerificationStatus.NO_REFERENCE,
        )

    if not current_frame_b64:
        return FaceMatchResult(
            is_owner=False,
            confidence=0.0,
            reason="no_frame",
            face_detected=False,
            status=FaceVerificationStatus.NO_FACE,
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("face_matcher: GEMINI_API_KEY not configured")
        return FaceMatchResult(
            is_owner=False,
            confidence=0.0,
            reason="api_key_missing",
            face_detected=False,
            status=FaceVerificationStatus.VERIFICATION_UNAVAILABLE,
        )

    try:
        ref_b64 = await fetch_reference_photo_b64(owner_photo_url)
        if not ref_b64:
            logger.warning("compare_faces: could not retrieve reference photo for %s", owner_photo_url[:60])
            return FaceMatchResult(
                is_owner=False,
                confidence=0.0,
                reason="could_not_fetch_reference",
                face_detected=False,
                status=FaceVerificationStatus.VERIFICATION_UNAVAILABLE,
            )

        prompt = (
            "You are a visual presence verification helper. "
            "Image 1 is the owner's reference photo. Image 2 is a live camera frame.\n"
            "Task: First check if any human face is clearly visible in Image 2. "
            "If no face is visible, set face_detected to false and is_same_person to false.\n"
            "If a face is visible, determine if it appears to be the same individual as in Image 1.\n"
            "Consider: natural lighting differences and angles are expected.\n"
            "Reply ONLY with valid JSON, no markdown:\n"
            '{"face_detected": true_or_false, "is_same_person": true_or_false, "confidence": 0.0_to_1.0, "reason": "brief"}'
        )

        from google import genai as _genai
        from google.genai import types as _types

        client = _genai.Client(api_key=api_key)
        frame_bytes = base64.b64decode(current_frame_b64)
        ref_bytes   = base64.b64decode(ref_b64)

        contents = [
            _types.Part(inline_data=_types.Blob(data=ref_bytes,   mime_type="image/jpeg")),
            _types.Part(inline_data=_types.Blob(data=frame_bytes, mime_type="image/jpeg")),
            _types.Part(text=prompt),
        ]

        raw = ""
        for model in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash"):
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                )
                raw = (response.text or "").strip()
                if raw:
                    break
            except Exception as exc:
                logger.warning("face_matcher (%s) failed: %s", model, exc)
                continue

        if not raw:
            return FaceMatchResult(
                is_owner=False,
                confidence=0.0,
                reason="empty_api_response",
                face_detected=False,
                status=FaceVerificationStatus.VERIFICATION_UNAVAILABLE,
            )

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        face_detected = bool(parsed.get("face_detected", True))
        confidence    = float(parsed.get("confidence", 0.0))
        is_same       = bool(parsed.get("is_same_person", False))
        is_owner      = face_detected and is_same and confidence >= _OWNER_THRESHOLD

        if not face_detected:
            status = FaceVerificationStatus.NO_FACE
        elif is_owner:
            status = FaceVerificationStatus.OWNER
        else:
            status = FaceVerificationStatus.UNKNOWN_PERSON

        logger.debug("face_matcher: face_detected=%s confidence=%.2f status=%s reason=%s",
                     face_detected, confidence, status, parsed.get("reason", ""))
        return FaceMatchResult(
            is_owner=is_owner,
            confidence=confidence,
            reason=parsed.get("reason", ""),
            face_detected=face_detected,
            status=status,
        )

    except Exception as exc:
        logger.warning("face_matcher: verification error (%s) — failing safe", exc)
        return FaceMatchResult(
            is_owner=False,
            confidence=0.0,
            reason=f"error:{exc}",
            face_detected=False,
            status=FaceVerificationStatus.VERIFICATION_UNAVAILABLE,
        )
