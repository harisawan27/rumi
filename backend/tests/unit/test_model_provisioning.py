import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from src.vision.download_models import (
    compute_file_sha256,
    verify_model_file,
    ensure_models,
    ModelIntegrityError,
    MODEL_REGISTRY,
)


def test_compute_file_sha256_and_verify_model_file():
    test_data = b"opencv-face-model-test-bytes"
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(test_data)
        temp_path = f.name

    try:
        import hashlib
        expected_hash = hashlib.sha256(test_data).hexdigest()
        actual_hash = compute_file_sha256(temp_path)
        assert actual_hash == expected_hash

        assert verify_model_file(temp_path, expected_hash) is True
        assert verify_model_file(temp_path, "wrong_hash_1234") is False
        assert verify_model_file("/non/existent/path.onnx", expected_hash) is False
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_ensure_models_fail_fast_raises_on_integrity_failure():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a corrupted model file
        corrupt_file = os.path.join(tmp_dir, MODEL_REGISTRY["yunet"]["name"])
        with open(corrupt_file, "wb") as f:
            f.write(b"corrupted_onnx_bytes")

        # Mock download to fail
        with patch("src.vision.download_models.download_and_verify_model", side_effect=ModelIntegrityError("Integrity failed")):
            with pytest.raises(ModelIntegrityError):
                ensure_models(models_dir=tmp_dir, fail_fast=True)


def test_ensure_models_returns_false_when_fail_fast_false():
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("src.vision.download_models.download_and_verify_model", side_effect=RuntimeError("Network offline")):
            result = ensure_models(models_dir=tmp_dir, fail_fast=False)
            assert result is False


def test_existing_valid_models_skip_download():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create dummy valid files
        for key, spec in MODEL_REGISTRY.items():
            path = os.path.join(tmp_dir, spec["name"])
            with open(path, "wb") as f:
                f.write(b"valid_model_data")

        # Mock verify_model_file to return True for all files
        with patch("src.vision.download_models.verify_model_file", return_value=True):
            with patch("src.vision.download_models.download_and_verify_model") as mock_dl:
                result = ensure_models(models_dir=tmp_dir, fail_fast=True)
                assert result is True
                assert mock_dl.call_count == 0
