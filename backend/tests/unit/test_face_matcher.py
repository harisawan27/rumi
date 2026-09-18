import pytest
from unittest.mock import patch, AsyncMock
from src.vision.face_matcher import compare_faces, FaceMatchResult


@pytest.mark.asyncio
async def test_face_matcher_fails_safe_on_api_error():
    """An API error/timeout must NEVER evaluate to is_owner=True."""
    with patch("httpx.AsyncClient.get", side_effect=Exception("Network timeout")):
        result = await compare_faces("http://example.com/photo.jpg", "invalid_base64")
        assert not result.is_owner, "API failure must NOT confirm owner identity!"
        # Should return an explicit safe verification status or fail-closed
        if hasattr(result, "status"):
            assert result.status == "VERIFICATION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_face_matcher_no_reference_photo_fails_safe():
    """Missing reference photo cannot confirm owner."""
    result = await compare_faces("", "some_base64")
    assert not result.is_owner, "Missing reference photo must not authenticate owner"


@pytest.mark.asyncio
async def test_face_matcher_no_face_detected():
    """When no face is in frame, is_owner must be False."""
    mock_response = AsyncMock()
    mock_response.text = '{"face_detected": false, "is_same_person": false, "confidence": 0.0, "reason": "no face"}'
    
    with patch("google.genai.Client") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.aio.models.generate_content.return_value = mock_response
        result = await compare_faces("data:image/jpeg;base64,123", "data:image/jpeg;base64,456")
        assert not result.is_owner
        assert not result.face_detected


@pytest.mark.asyncio
async def test_fetch_reference_photo_b64_data_uri():
    from src.vision.face_matcher import fetch_reference_photo_b64
    b64 = await fetch_reference_photo_b64("data:image/jpeg;base64,QUJDREVGRw==")
    assert b64 == "QUJDREVGRw=="


@pytest.mark.asyncio
async def test_fetch_reference_photo_b64_private_gs_path():
    from src.vision.face_matcher import fetch_reference_photo_b64
    from unittest.mock import MagicMock

    mock_blob = MagicMock()
    mock_blob.download_as_bytes.return_value = b"test_jpeg_bytes"

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    with patch("firebase_admin.storage.bucket", return_value=mock_bucket):
        b64 = await fetch_reference_photo_b64("gs://my-private-bucket/known-people/user1/test.jpg")
        mock_bucket.blob.assert_called_with("known-people/user1/test.jpg")
        import base64
        assert b64 == base64.b64encode(b"test_jpeg_bytes").decode()
