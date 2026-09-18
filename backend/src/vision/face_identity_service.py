import hashlib
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import cv2
import httpx
import numpy as np

from src.vision.face_matcher import FaceVerificationStatus, fetch_reference_photo_b64

logger = logging.getLogger(__name__)

# Model metadata
MODEL_VERSION = "opencv-sface-2021dec-v1"
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
SFACE_SHA256 = "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

# Configurable conservative matching thresholds (calibrated starting points)
DEFAULT_OWNER_MATCH_THRESHOLD = float(os.getenv("RUMI_OWNER_MATCH_THRESHOLD", "0.45"))
DEFAULT_KNOWN_PERSON_MATCH_THRESHOLD = float(os.getenv("RUMI_KNOWN_PERSON_MATCH_THRESHOLD", "0.40"))


@dataclass
class FaceIdentityResult:
    status: FaceVerificationStatus
    person_id: Optional[str] = None
    name: Optional[str] = None
    relationship: Optional[str] = None
    similarity: Optional[float] = None
    confidence: Optional[float] = None
    faces_detected: int = 0


class BaseFaceEmbedder(ABC):
    """Abstract face detection and 128-d embedding interface."""

    @abstractmethod
    def detect_and_embed(self, frame_bytes: bytes) -> tuple[int, Optional[np.ndarray]]:
        """Return (num_faces, embedding_vector).

        If num_faces == 1, embedding_vector is a 128-d L2-normalized float32 numpy array.
        Otherwise, embedding_vector is None.
        """
        pass

    @abstractmethod
    def compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two 128-d vectors."""
        pass


class OpenCVFaceEmbedder(BaseFaceEmbedder):
    """Local face detection & embedding using OpenCV YuNet + SFace."""

    def __init__(self, models_dir: Optional[str] = None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
        self.models_dir = os.path.abspath(models_dir)
        os.makedirs(self.models_dir, exist_ok=True)

        self.yunet_path = os.path.join(self.models_dir, "face_detection_yunet_2023mar.onnx")
        self.sface_path = os.path.join(self.models_dir, "face_recognition_sface_2021dec.onnx")

        self._detector = None
        self._recognizer = None
        self.init_error: Optional[str] = None

        self._ensure_and_load_models()

    def is_available(self) -> bool:
        """Return True if both detector and recognizer are loaded and ready."""
        return bool(self._detector is not None and self._recognizer is not None)

    def _ensure_and_load_models(self) -> None:
        """Verify models on disk, provisioning them via download_models if needed."""
        try:
            from src.vision.download_models import ensure_models
            ensure_models(models_dir=self.models_dir, fail_fast=False)
        except Exception as exc:
            self.init_error = f"Model provisioning error: {exc}"
            logger.warning("OpenCVFaceEmbedder: %s", self.init_error)

        try:
            if os.path.isfile(self.yunet_path):
                self._detector = cv2.FaceDetectorYN.create(
                    self.yunet_path, "", (320, 320), score_threshold=0.6, nms_threshold=0.3
                )
            else:
                self.init_error = f"Missing YuNet model: {self.yunet_path}"

            if os.path.isfile(self.sface_path):
                self._recognizer = cv2.FaceRecognizerSF.create(self.sface_path, "")
            else:
                self.init_error = f"Missing SFace model: {self.sface_path}"

            if self.is_available():
                logger.info("OpenCVFaceEmbedder: initialized YuNet detector and SFace recognizer")
            else:
                logger.warning("OpenCVFaceEmbedder: model initialization failed (%s)", self.init_error)
        except Exception as exc:
            self.init_error = f"OpenCV model initialization error: {exc}"
            self._detector = None
            self._recognizer = None
            logger.warning("OpenCVFaceEmbedder: %s", self.init_error)

    def detect_and_embed(self, frame_bytes: bytes) -> tuple[int, Optional[np.ndarray]]:
        if not self.is_available():
            raise RuntimeError(f"OpenCVFaceEmbedder unavailable: {self.init_error or 'models not loaded'}")

        nparr = np.frombuffer(frame_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return 0, None

        h, w, _ = img.shape
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(img)

        if faces is None or len(faces) == 0:
            return 0, None

        num_faces = len(faces)
        if num_faces > 1:
            return num_faces, None

        face = faces[0]
        aligned_face = self._recognizer.alignCrop(img, face)
        feature = self._recognizer.feature(aligned_face)
        feature = feature.flatten()
        norm = np.linalg.norm(feature)
        if norm > 1e-6:
            feature = feature / norm
        return 1, feature.astype(np.float32)

    def compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        v1 = vec1.flatten()
        v2 = vec2.flatten()
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))


class FaceIdentityService:
    """Dedicated face identity and verification service.

    Architecture & Complexity:
    - Face detection: 1 local model inference (YuNet)
    - Face embedding: 1 local model inference (SFace)
    - Identity matching: O(N) cosine comparisons over N enrolled embeddings in memory
    Replaces O(N) remote multimodal Gemini Vision calls with 1 local embedding inference
    plus O(N) in-memory vector comparisons.

    Policy:
    - 0 faces: NO_FACE
    - 1 face: Identify against owner and enrolled known people
    - 2+ faces: MULTIPLE_FACES — Multiple simultaneous faces conservatively remove
      owner-private authorization / enter protected guest state. Note: Rumi does not
      identify individual faces in multi-face scenes; it conservatively locks private access
      to protect owner privacy.
    - Model failure / exception: Fail closed (VERIFICATION_UNAVAILABLE). Never treat failure as OWNER.
    - Persists reference embeddings in users/{uid}/face_embeddings/{person_id}.
    - Lazy migration for existing photos without stored embeddings.
    """

    def __init__(
        self,
        embedder: Optional[BaseFaceEmbedder] = None,
        owner_threshold: float = DEFAULT_OWNER_MATCH_THRESHOLD,
        known_threshold: float = DEFAULT_KNOWN_PERSON_MATCH_THRESHOLD,
    ):
        self.embedder = embedder or OpenCVFaceEmbedder()
        self.owner_threshold = owner_threshold
        self.known_threshold = known_threshold
        self._cache: dict[str, dict] = {}  # uid -> {person_id: {"name": ..., "embedding": ..., "rel": ...}}

    def _get_embeddings_collection(self, uid: str):
        from src.memory.firestore_client import get_db
        db = get_db()
        return db.collection("users").document(uid).collection("face_embeddings")

    def _load_cached_or_stored_embeddings(self, uid: str) -> dict[str, dict]:
        if uid in self._cache:
            return self._cache[uid]

        loaded = {}
        try:
            docs = self._get_embeddings_collection(uid).stream()
            for doc in docs:
                data = doc.to_dict() or {}
                raw_emb = data.get("embedding")
                if raw_emb and isinstance(raw_emb, list):
                    loaded[doc.id] = {
                        "name": data.get("name", ""),
                        "relationship": data.get("relationship", ""),
                        "embedding": np.array(raw_emb, dtype=np.float32),
                        "model": data.get("model", MODEL_VERSION),
                    }
            self._cache[uid] = loaded
        except Exception as exc:
            logger.warning("FaceIdentityService: failed to load embeddings for %s: %s", uid, exc)

        return loaded

    async def _compute_and_store_embedding(
        self,
        uid: str,
        person_id: str,
        name: str,
        photo_url: str,
        relationship: str = "",
    ) -> Optional[np.ndarray]:
        """Lazy migration helper: fetch photo, extract embedding, store in Firestore."""
        if not photo_url:
            return None

        try:
            b64_str = await fetch_reference_photo_b64(photo_url)
            if not b64_str:
                return None

            import base64
            frame_bytes = base64.b64decode(b64_str)
            num_faces, emb = self.embedder.detect_and_embed(frame_bytes)
            if num_faces == 1 and emb is not None:
                doc_payload = {
                    "person_id": person_id,
                    "name": name,
                    "relationship": relationship,
                    "embedding": [float(x) for x in emb.tolist()],
                    "model": MODEL_VERSION,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "source_photo_path": photo_url[:200],
                }
                try:
                    self._get_embeddings_collection(uid).document(person_id).set(doc_payload)
                    if uid not in self._cache:
                        self._cache[uid] = {}
                    self._cache[uid][person_id] = {
                        "name": name,
                        "relationship": relationship,
                        "embedding": emb,
                        "model": MODEL_VERSION,
                    }
                    logger.info("FaceIdentityService: lazy migrated embedding for %s (%s)", person_id, name)
                except Exception as save_err:
                    logger.warning("FaceIdentityService: could not persist embedding for %s: %s", person_id, save_err)
                return emb
        except Exception as exc:
            logger.warning("FaceIdentityService: lazy migration error for %s: %s", person_id, exc)

        return None

    async def identify(
        self,
        frame_bytes: bytes,
        uid: str,
        owner_photo_url: Optional[str] = None,
        owner_name: str = "Owner",
    ) -> FaceIdentityResult:
        """Identify face in frame against owner and known people."""
        if hasattr(self.embedder, "is_available") and not self.embedder.is_available():
            init_err = getattr(self.embedder, "init_error", "models not loaded")
            try:
                from src.utils.observability import log_structured_event
                log_structured_event("FACE_IDENTIFICATION_ERROR", {
                    "error": "MODEL_UNAVAILABLE",
                    "details": str(init_err)[:100],
                })
            except Exception:
                pass
            return FaceIdentityResult(
                status=FaceVerificationStatus.VERIFICATION_UNAVAILABLE,
                confidence=0.0,
                faces_detected=0,
            )

        try:
            num_faces, emb = self.embedder.detect_and_embed(frame_bytes)
        except Exception as exc:
            try:
                from src.utils.observability import log_structured_event
                log_structured_event("FACE_IDENTIFICATION_ERROR", {
                    "error": "INFERENCE_FAILED",
                    "details": str(exc)[:100],
                })
            except Exception:
                pass
            logger.error("FaceIdentityService: inference failed: %s", exc)
            return FaceIdentityResult(
                status=FaceVerificationStatus.VERIFICATION_UNAVAILABLE,
                confidence=0.0,
                faces_detected=0,
            )

        if num_faces == 0:
            return FaceIdentityResult(
                status=FaceVerificationStatus.NO_FACE,
                faces_detected=0,
            )

        if num_faces > 1:
            return FaceIdentityResult(
                status=FaceVerificationStatus.MULTIPLE_FACES,
                faces_detected=num_faces,
            )

        if emb is None:
            return FaceIdentityResult(
                status=FaceVerificationStatus.NO_FACE,
                faces_detected=0,
            )

        # Single face detected — compare with embeddings
        embeddings = self._load_cached_or_stored_embeddings(uid)

        # ── 1. Check Owner ───────────────────────────────────────────────────
        owner_emb = None
        if "owner" in embeddings:
            owner_emb = embeddings["owner"]["embedding"]
        elif owner_photo_url:
            owner_emb = await self._compute_and_store_embedding(
                uid=uid, person_id="owner", name=owner_name, photo_url=owner_photo_url
            )

        if owner_emb is not None:
            sim = self.embedder.compute_similarity(emb, owner_emb)
            if sim >= self.owner_threshold:
                return FaceIdentityResult(
                    status=FaceVerificationStatus.OWNER,
                    person_id="owner",
                    name=owner_name,
                    similarity=round(sim, 3),
                    confidence=round(sim, 3),
                    faces_detected=1,
                )

        # ── 2. Check Known People ────────────────────────────────────────────
        best_match: Optional[dict] = None
        best_sim: float = -1.0

        # Also lazily check any known people in Firestore that don't have embeddings yet
        from src.memory.known_people import get_known_people
        try:
            known_people_list = get_known_people(uid)
        except Exception:
            known_people_list = []

        for person in known_people_list:
            pid = person.get("id")
            if not pid:
                continue
            p_emb = None
            if pid in embeddings:
                p_emb = embeddings[pid]["embedding"]
            elif person.get("photo_url"):
                p_emb = await self._compute_and_store_embedding(
                    uid=uid,
                    person_id=pid,
                    name=person.get("name", ""),
                    photo_url=person["photo_url"],
                    relationship=person.get("relationship", ""),
                )

            if p_emb is not None:
                sim = self.embedder.compute_similarity(emb, p_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_match = {
                        "id": pid,
                        "name": person.get("name", ""),
                        "relationship": person.get("relationship", ""),
                        "sim": sim,
                    }

        if best_match and best_sim >= self.known_threshold:
            return FaceIdentityResult(
                status=FaceVerificationStatus.KNOWN_PERSON,
                person_id=best_match["id"],
                name=best_match["name"],
                relationship=best_match["relationship"],
                similarity=round(best_sim, 3),
                confidence=round(best_sim, 3),
                faces_detected=1,
            )

        # Neither owner nor known person matched -> Unknown Person
        return FaceIdentityResult(
            status=FaceVerificationStatus.UNKNOWN_PERSON,
            similarity=round(best_sim, 3) if best_sim >= 0 else None,
            confidence=0.0,
            faces_detected=1,
        )

    def delete_person_embedding(self, uid: str, person_id: str) -> None:
        """Delete stored embedding and evict from cache."""
        try:
            self._get_embeddings_collection(uid).document(person_id).delete()
        except Exception as exc:
            logger.warning("FaceIdentityService: delete_person_embedding failed for %s/%s: %s", uid, person_id, exc)

        if uid in self._cache:
            self._cache[uid].pop(person_id, None)

    def clear_cache(self, uid: Optional[str] = None) -> None:
        if uid:
            self._cache.pop(uid, None)
        else:
            self._cache.clear()


# Global singleton instance
face_identity_service = FaceIdentityService()
