import logging
import sys
import types
from dataclasses import dataclass, field
from typing import Optional

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


class LocalObserver:
    """On-device emotion observer. Zero API cost. Runs on every frame.

    Layer 1 of the robot-style perception stack:
    - FER (CNN trained on AffectNet) → classifies emotions from face
    - Frame diff                      → detects idle / static screen

    Frustration score = weighted sum of angry + sad + disgust probabilities.
    Only fires ADK Agent when score is sustained above threshold for 30s.
    """

    _FRUSTRATION_THRESHOLD = 0.45

    def __init__(self):
        self._fer = None
        self._fer_loaded = False
        self._prev_gray: Optional[np.ndarray] = None
        import threading
        threading.Thread(target=self._load_fer, daemon=True).start()

    def _load_fer(self) -> None:
        try:
            # pkg_resources was removed from setuptools 82+ as a top-level import.
            # FER uses it for version lookup AND resource_filename (model path).
            # Inject a minimal stub that satisfies both without requiring setuptools shim.
            if "pkg_resources" not in sys.modules:
                import importlib.util, os

                def _resource_filename(pkg_name, resource_path):
                    spec = importlib.util.find_spec(pkg_name)
                    if spec and spec.origin:
                        return os.path.join(os.path.dirname(spec.origin), resource_path)
                    return resource_path

                stub = types.ModuleType("pkg_resources")
                stub.get_distribution = lambda n: type("D", (), {"version": "0.0"})()
                stub.DistributionNotFound = Exception
                stub.resource_filename = _resource_filename
                sys.modules["pkg_resources"] = stub

            from fer.fer import FER
            self._fer = FER(mtcnn=False)
            self._fer_loaded = True
            logger.info("LocalObserver: FER emotion detector loaded")
        except Exception as exc:
            logger.warning(
                "LocalObserver: fer unavailable (%s) — emotion detection disabled", exc
            )

    def observe(self, frame_bytes: bytes) -> LocalObservation:
        """Analyse a JPEG frame locally. No API call ever."""
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return LocalObservation(event="neutral", frustration_score=0.0, idle_score=0.0)

        frustration_score, cues, emotions = self._score_frustration(frame) if self._fer_loaded else (0.0, [], {})
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
        )

    def _score_frustration(self, frame: np.ndarray) -> tuple:
        """Score frustration using FER's CNN emotion classifier."""
        try:
            results = self._fer.detect_emotions(frame)
            if not results:
                return 0.0, [], {}

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
            return min(score, 1.0), cues, {e: round(v, 2) for e, v in emotions.items()}

        except Exception as exc:
            logger.debug("LocalObserver: FER scoring error: %s", exc)
            return 0.0, [], {}

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
