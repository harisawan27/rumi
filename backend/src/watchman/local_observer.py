import logging
import sys
import types
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class LocalObservation:
    event: str             # "neutral" | "frustrated" | "idle"
    frustration_score: float
    idle_score: float
    cues: list = field(default_factory=list)
    landmarks: dict = field(default_factory=dict)
    face_detected: bool = False
    detector_status: str = "loading"  # "ready" | "loading" | "unavailable"


class LocalObserver:
    """On-device emotion observer. Zero API cost. Runs on every frame.

    Layer 1 of the robot-style perception stack:
    - FER (CNN trained on AffectNet) → classifies emotions from face
    - YuNet fallback                 → robust face bounding-box locator if Haar misses
    - Frame diff                     → detects idle / static screen

    Frustration score = weighted sum of angry + sad + disgust probabilities.
    Only fires ADK Agent when score is sustained above threshold for 30s.
    """

    _FRUSTRATION_THRESHOLD = 0.45

    def __init__(self):
        self._fer = None
        self._fer_loaded = False
        self._detector_status = "loading"
        self._detector_error: Optional[str] = None
        self._prev_gray: Optional[np.ndarray] = None
        import threading
        threading.Thread(target=self._load_fer, daemon=True).start()

    def _load_fer(self) -> None:
        try:
            # Check pkg_resources natively (e.g. setuptools<82)
            try:
                import pkg_resources
            except ImportError:
                # Python standard library compatibility shim for setuptools>=82
                import importlib.metadata
                import importlib.util
                import os

                class _Distribution:
                    def __init__(self, name: str):
                        try:
                            self.version = importlib.metadata.version(name)
                        except Exception:
                            self.version = "22.5.1"

                def _resource_filename(pkg_name: str, resource_path: str) -> str:
                    spec = importlib.util.find_spec(pkg_name)
                    if spec and spec.origin:
                        return os.path.join(os.path.dirname(spec.origin), resource_path)
                    return resource_path

                stub = types.ModuleType("pkg_resources")
                stub.get_distribution = lambda n: _Distribution(n)
                stub.DistributionNotFound = Exception
                stub.resource_filename = _resource_filename
                sys.modules["pkg_resources"] = stub

            from fer.fer import FER
            self._fer = FER(mtcnn=False)
            self._fer_loaded = True
            self._detector_status = "ready"
            logger.info("LocalObserver: FER emotion detector loaded")
        except Exception as exc:
            self._detector_status = "unavailable"
            self._detector_error = str(exc)
            logger.warning(
                "LocalObserver: fer unavailable (%s) — emotion detection disabled", exc
            )

    def _find_face_rectangles(self, frame: np.ndarray) -> list:
        """Find face bounding boxes using YuNet fallback if available."""
        try:
            from src.vision.face_identity_service import face_identity_service
            embedder = getattr(face_identity_service, "embedder", None)
            if embedder and embedder.is_available() and embedder._detector is not None:
                h, w, _ = frame.shape
                embedder._detector.setInputSize((w, h))
                _, faces = embedder._detector.detect(frame)
                if faces is not None and len(faces) > 0:
                    rects = []
                    for f in faces:
                        # [x, y, w, h]
                        rects.append((int(f[0]), int(f[1]), int(f[2]), int(f[3])))
                    return rects
        except Exception as exc:
            logger.debug("LocalObserver: YuNet face detection check failed: %s", exc)
        return []

    def has_face(self, frame_bytes: bytes) -> bool:
        """Return True if at least one face is detected in the frame.

        Used as a free, local pre-check before calling the Gemini face-matcher
        API. If FER is not yet loaded, checks YuNet or returns True (fail-safe).
        """
        try:
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                return False

            if self._fer_loaded and self._fer is not None:
                results = self._fer.detect_emotions(frame)
                if len(results) > 0:
                    return True

            # Check YuNet
            if len(self._find_face_rectangles(frame)) > 0:
                return True

            return False if self._fer_loaded else True
        except Exception:
            return True  # fail-safe on error

    def observe(self, frame_bytes: bytes) -> LocalObservation:
        """Analyse a JPEG frame locally. Zero API cost."""
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return LocalObservation(
                event="neutral",
                frustration_score=0.0,
                idle_score=0.0,
                face_detected=False,
                detector_status=self._detector_status,
            )

        if self._fer_loaded:
            frustration_score, cues, emotions, face_detected = self._score_frustration(frame)
        else:
            frustration_score, cues, emotions, face_detected = 0.0, [], {}, False

        idle_score = self._score_idle(frame)

        if frustration_score >= self._FRUSTRATION_THRESHOLD:
            event = "frustrated"
        elif idle_score >= 0.85:
            event = "idle"
        else:
            event = "neutral"

        return LocalObservation(
            event=event,
            frustration_score=round(frustration_score, 2),
            idle_score=round(idle_score, 2),
            cues=cues,
            landmarks=emotions,
            face_detected=face_detected,
            detector_status=self._detector_status,
        )

    def _score_frustration(self, frame: np.ndarray) -> Tuple[float, list, dict, bool]:
        """Score frustration using FER's CNN emotion classifier.

        Returns:
            (frustration_score, cues, emotions_dict, face_detected)
        """
        try:
            # 1. Try FER's default detection (Haar cascade)
            results = self._fer.detect_emotions(frame)

            # 2. If Haar cascade misses a face, fallback to YuNet bounding box
            if not results:
                yunet_rects = self._find_face_rectangles(frame)
                if yunet_rects:
                    results = self._fer.detect_emotions(frame, face_rectangles=yunet_rects)

            if not results:
                return 0.0, [], {}, False

            face = max(results, key=lambda r: r["box"][2] * r["box"][3])
            emotions = face["emotions"]

            score = (
                emotions.get("angry", 0.0) * 0.70
                + emotions.get("sad", 0.0) * 0.20
                + emotions.get("disgust", 0.0) * 0.10
            )

            cues = [e for e, v in emotions.items() if v > 0.15]

            logger.debug(
                "LocalObserver: angry=%.2f sad=%.2f happy=%.2f neutral=%.2f → score=%.2f",
                emotions.get("angry", 0), emotions.get("sad", 0),
                emotions.get("happy", 0), emotions.get("neutral", 0), score,
            )
            return min(score, 1.0), cues, {e: round(v, 2) for e, v in emotions.items()}, True

        except Exception as exc:
            logger.debug("LocalObserver: FER scoring error: %s", exc)
            return 0.0, [], {}, False

    def _score_idle(self, frame: np.ndarray) -> float:
        """Frame diff: 0.0 = active movement, 1.0 = completely static."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (64, 48))

        if self._prev_gray is None:
            self._prev_gray = gray
            return 0.0

        diff = np.mean(np.abs(gray.astype(float) - self._prev_gray.astype(float)))
        self._prev_gray = gray
        # diff > 10 = clear movement; diff < 1 = nearly static
        return max(0.0, 1.0 - (diff / 10.0))
