import asyncio
import base64
import os
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - optional in cloud/server deployments
    cv2 = None

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except Exception:  # pragma: no cover - optional in cloud/server deployments
    mp = None
    python = None
    vision = None


class FaceAuthenticator:
    MODEL_PATH = str(Path(__file__).with_name("face_landmarker.task"))
    MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"

    def __init__(self, reference_image_path: Optional[str] = None, on_status_change=None, on_frame=None):
        self.reference_image_path = reference_image_path or str(Path(__file__).with_name("reference.jpg"))
        self.on_status_change = on_status_change
        self.on_frame = on_frame
        self._landmarker = None
        self._reference_landmarks = None
        self._running = False

        if self.is_available():
            self._ensure_model()
        if self.is_available() and os.path.exists(self.reference_image_path):
            try:
                self._load_reference()
            except Exception:
                self._reference_landmarks = None

    def is_available(self):
        return cv2 is not None and mp is not None and python is not None and vision is not None

    def _ensure_model(self):
        if not self.is_available():
            raise RuntimeError("Face authentication dependencies are not installed.")
        if not os.path.exists(self.MODEL_PATH):
            raise FileNotFoundError(f"Face Landmarker model not found at {self.MODEL_PATH}")

    def _init_landmarker(self):
        if not self.is_available():
            raise RuntimeError("Face authentication dependencies are not installed.")
        if self._landmarker is not None:
            return

        base_options = python.BaseOptions(model_asset_path=self.MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            num_faces=1,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def _extract_landmarks(self, image_bgr):
        if not self.is_available():
            return None
        if image_bgr is None or image_bgr.size == 0:
            return None

        self._init_landmarker()
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(image_rgb))
        result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None

        face = result.face_landmarks[0]
        coords = np.array([[lm.x, lm.y, lm.z] for lm in face], dtype=np.float32).flatten()
        return coords

    def _compare_landmarks(self, landmarks1, landmarks2, threshold=0.035):
        if landmarks1 is None or landmarks2 is None:
            return False

        a = np.asarray(landmarks1, dtype=np.float32)
        b = np.asarray(landmarks2, dtype=np.float32)
        if a.shape != b.shape:
            return False

        distance = float(np.mean(np.abs(a - b)))
        return distance <= threshold

    def _load_reference(self):
        if not self.is_available():
            raise RuntimeError("Face authentication dependencies are not installed.")
        image = cv2.imread(self.reference_image_path)
        if image is None:
            raise FileNotFoundError(f"Reference image not found at {self.reference_image_path}")

        landmarks = self._extract_landmarks(image)
        if landmarks is None:
            raise ValueError("No face detected in reference image")

        self._reference_landmarks = landmarks
        return landmarks

    def has_reference(self):
        if not self.is_available():
            return False
        return self._reference_landmarks is not None or os.path.exists(self.reference_image_path)

    def save_reference_frame(self, frame_bgr):
        if not self.is_available():
            raise RuntimeError("Face authentication dependencies are not installed.")
        os.makedirs(os.path.dirname(self.reference_image_path), exist_ok=True)
        cv2.imwrite(self.reference_image_path, frame_bgr)
        self._reference_landmarks = None
        self._load_reference()
        return True

    def authenticate_frame(self, frame_bgr, threshold=0.035):
        if not self.is_available():
            return False, "Face authentication is unavailable on this deployment."
        if self._reference_landmarks is None:
            if not os.path.exists(self.reference_image_path):
                return False, "Face ID is not enrolled yet."
            self._load_reference()

        candidate = self._extract_landmarks(frame_bgr)
        if candidate is None:
            return False, "No face detected in the current frame."

        matched = self._compare_landmarks(self._reference_landmarks, candidate, threshold=threshold)
        if matched:
            return True, "Face verified."
        return False, "Face does not match the enrolled reference."

    async def _run_cv_loop(self):
        if not self.is_available():
            if self.on_status_change:
                await self.on_status_change(False)
            return
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            if self.on_status_change:
                await self.on_status_change(False)
            return

        self._running = True
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.1)
                    continue

                if self.on_frame:
                    ok, encoded = cv2.imencode(".jpg", frame)
                    if ok:
                        await self.on_frame(base64.b64encode(encoded.tobytes()).decode("utf-8"))

                if self._reference_landmarks is not None:
                    matched, _ = self.authenticate_frame(frame)
                    if self.on_status_change:
                        await self.on_status_change(matched)

                await asyncio.sleep(0.1)
        finally:
            cap.release()

    def start_authentication_loop(self):
        return asyncio.create_task(self._run_cv_loop())

    def stop(self):
        self._running = False
