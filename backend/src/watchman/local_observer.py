import logging
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


class LocalObserver:
    """On-device MediaPipe observer. Zero API cost. Runs on every frame.

    Layer 1 of the robot-style perception stack:
    - MediaPipe Pose  → detects frustration signals (head drop, shoulder hunch, hand-to-face)
    - MediaPipe Face  → detects squinting / tired eyes
    - Frame diff      → detects idle / static screen

    Only fires ADK Agent when scores cross threshold — no continuous LLM calls.
    """

    # MediaPipe pose landmark indices
    _NOSE = 0
    _LEFT_EAR = 7
    _RIGHT_EAR = 8
    _LEFT_SHOULDER = 11
    _RIGHT_SHOULDER = 12
    _LEFT_WRIST = 15
    _RIGHT_WRIST = 16

    # Face mesh eyelid landmarks (left eye)
    _EYE_UPPER = 159
    _EYE_LOWER = 145

    def __init__(self):
        self._pose = None
        self._face_mesh = None
        self._prev_gray: Optional[np.ndarray] = None
        self._mp_loaded = False
        self._load_mediapipe()

    def _load_mediapipe(self) -> None:
        try:
            import mediapipe as mp
            self._mp_pose = mp.solutions.pose
            self._mp_face = mp.solutions.face_mesh
            self._pose = self._mp_pose.Pose(
                static_image_mode=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._face_mesh = self._mp_face.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                min_detection_confidence=0.5,
            )
            self._mp_loaded = True
            logger.info("LocalObserver: MediaPipe loaded")
        except ImportError:
            logger.warning("LocalObserver: mediapipe not installed — using frame diff only")

    def observe(self, frame_bytes: bytes) -> LocalObservation:
        """Analyse a JPEG frame locally. No API call ever."""
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return LocalObservation(event="neutral", frustration_score=0.0, idle_score=0.0)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frustration_score, cues = self._score_frustration(rgb) if self._mp_loaded else (0.0, [])
        idle_score = self._score_idle(frame)

        if frustration_score >= 0.55:
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
        )

    def _score_frustration(self, rgb: np.ndarray) -> tuple:
        score = 0.0
        cues = []
        try:
            pose_result = self._pose.process(rgb)
            face_result = self._face_mesh.process(rgb)

            if pose_result.pose_landmarks:
                lm = pose_result.pose_landmarks.landmark
                nose = lm[self._NOSE]
                left_shoulder = lm[self._LEFT_SHOULDER]
                right_shoulder = lm[self._RIGHT_SHOULDER]
                left_ear = lm[self._LEFT_EAR]
                left_wrist = lm[self._LEFT_WRIST]
                right_wrist = lm[self._RIGHT_WRIST]

                shoulder_y = (left_shoulder.y + right_shoulder.y) / 2

                # Head drooping down
                if nose.y > shoulder_y + 0.12:
                    score += 0.3
                    cues.append("head_down")

                # Shoulders hunched up toward ears
                if abs(left_shoulder.y - left_ear.y) < 0.08:
                    score += 0.2
                    cues.append("shoulders_hunched")

                # Hand near face (head-in-hands / rubbing face)
                for wrist in (left_wrist, right_wrist):
                    dist = ((wrist.x - nose.x) ** 2 + (wrist.y - nose.y) ** 2) ** 0.5
                    if dist < 0.15:
                        score += 0.25
                        cues.append("hand_near_face")
                        break

            if face_result.multi_face_landmarks:
                face_lm = face_result.multi_face_landmarks[0].landmark
                eye_open = abs(face_lm[self._EYE_UPPER].y - face_lm[self._EYE_LOWER].y)
                if eye_open < 0.012:
                    score += 0.2
                    cues.append("squinting")

        except Exception as exc:
            logger.debug("LocalObserver: pose scoring error: %s", exc)

        return min(score, 1.0), cues

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
