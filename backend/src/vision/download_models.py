"""Model provisioning and integrity verification for Project Rumi.

Downloads official OpenCV Zoo ONNX models (YuNet and SFace) from pinned URLs,
verifies exact SHA256 checksums, and performs atomic writes to prevent partial
or corrupted model files from entering production.
"""

import argparse
import hashlib
import logging
import os
import shutil
import sys
import tempfile
from typing import Optional

import httpx

logger = logging.getLogger("rumi.model_provisioning")

# Pinned official OpenCV Zoo model weights (Apache 2.0)
MODEL_REGISTRY = {
    "yunet": {
        "name": "face_detection_yunet_2023mar.onnx",
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        "size_bytes": 232589,
        "description": "YuNet Face Detector (March 2023)",
    },
    "sface": {
        "name": "face_recognition_sface_2021dec.onnx",
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        "size_bytes": 38696353,
        "description": "SFace Face Recognizer (Dec 2021)",
    },
}


class ModelIntegrityError(RuntimeError):
    """Raised when an ONNX model fails SHA256 verification or cannot be provisioned."""
    pass


def compute_file_sha256(filepath: str, chunk_size: int = 65536) -> str:
    """Stream file bytes and compute SHA256 hash without loading entire file to memory."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def verify_model_file(filepath: str, expected_sha256: str) -> bool:
    """Check if model exists on disk and has matching SHA256."""
    if not os.path.isfile(filepath):
        return False
    actual_hash = compute_file_sha256(filepath)
    return actual_hash.lower() == expected_sha256.lower()


def download_and_verify_model(
    dest_path: str,
    url: str,
    expected_sha256: str,
    name: str,
    timeout_sec: float = 180.0,
) -> None:
    """Download model with streaming chunks, verify SHA256, and atomically write."""
    dest_dir = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(dest_dir, exist_ok=True)

    # Use a named temporary file in the same directory for atomic rename
    fd, temp_path = tempfile.mkstemp(prefix=f"{name}_dl_", suffix=".tmp", dir=dest_dir)
    os.close(fd)

    logger.info("Downloading %s from %s...", name, url)
    h = hashlib.sha256()

    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        h.update(chunk)

        actual_sha256 = h.hexdigest().lower()
        if actual_sha256 != expected_sha256.lower():
            raise ModelIntegrityError(
                f"Model integrity check failed for {name}! "
                f"Expected SHA256: {expected_sha256}, got: {actual_sha256}"
            )

        # Atomic replacement
        shutil.move(temp_path, dest_path)
        logger.info("Successfully provisioned and verified %s (SHA256: %s)", name, actual_sha256)

    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


def ensure_models(models_dir: Optional[str] = None, fail_fast: bool = True) -> bool:
    """Ensure all required ONNX models exist and pass checksum verification.

    Args:
        models_dir: Directory where models are stored. Defaults to backend/models.
        fail_fast: If True, raises ModelIntegrityError on failure. If False, logs and returns False.

    Returns:
        True if all models are present and verified; False otherwise.
    """
    if models_dir is None:
        models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
    models_dir = os.path.abspath(models_dir)
    os.makedirs(models_dir, exist_ok=True)

    for key, spec in MODEL_REGISTRY.items():
        dest_path = os.path.join(models_dir, spec["name"])
        expected_sha256 = spec["sha256"]

        if verify_model_file(dest_path, expected_sha256):
            logger.info("Verified existing %s at %s", spec["name"], dest_path)
            continue

        try:
            download_and_verify_model(
                dest_path=dest_path,
                url=spec["url"],
                expected_sha256=expected_sha256,
                name=spec["name"],
            )
        except Exception as exc:
            error_msg = f"Failed to provision {spec['name']}: {exc}"
            logger.critical(error_msg)
            if fail_fast:
                raise ModelIntegrityError(error_msg) from exc
            return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Download and verify OpenCV Zoo models for Project Rumi.")
    parser.add_argument("--models-dir", type=str, default=None, help="Target directory for model files")
    args = parser.parse_args()

    try:
        ensure_models(models_dir=args.models_dir, fail_fast=True)
        print("All face recognition models successfully verified.")
        sys.exit(0)
    except Exception as err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
