import pytest
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock

from src.vision.face_identity_service import (
    FaceIdentityService,
    BaseFaceEmbedder,
    FaceIdentityResult,
    FaceVerificationStatus,
    MODEL_VERSION,
)


class MockEmbedder(BaseFaceEmbedder):
    """Deterministic mock embedder for tests."""

    def __init__(self, num_faces: int = 1, vector: np.ndarray = None):
        self.num_faces = num_faces
        if vector is None:
            self.vector = np.zeros(128, dtype=np.float32)
            self.vector[0] = 1.0  # unit vector along axis 0
        else:
            self.vector = vector

    def detect_and_embed(self, frame_bytes: bytes) -> tuple[int, np.ndarray]:
        if self.num_faces == 0:
            return 0, None
        if self.num_faces > 1:
            return self.num_faces, None
        return 1, self.vector

    def compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        v1 = vec1.flatten()
        v2 = vec2.flatten()
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))


@pytest.fixture
def mock_db():
    mock_client = MagicMock()
    mock_coll = MagicMock()
    mock_client.collection.return_value.document.return_value.collection.return_value = mock_coll
    with patch("src.memory.firestore_client.get_db", return_value=mock_client):
        yield mock_client, mock_coll


@pytest.mark.asyncio
async def test_face_identity_no_face_detected():
    embedder = MockEmbedder(num_faces=0)
    service = FaceIdentityService(embedder=embedder)

    result = await service.identify(b"dummy_frame", uid="user_123")
    assert result.status == FaceVerificationStatus.NO_FACE
    assert result.faces_detected == 0


@pytest.mark.asyncio
async def test_face_identity_multiple_faces_detected():
    embedder = MockEmbedder(num_faces=2)
    service = FaceIdentityService(embedder=embedder)

    result = await service.identify(b"dummy_frame", uid="user_123")
    assert result.status == FaceVerificationStatus.MULTIPLE_FACES
    assert result.faces_detected == 2


@pytest.mark.asyncio
async def test_face_identity_owner_match():
    # Unit vector along axis 0
    owner_vec = np.zeros(128, dtype=np.float32)
    owner_vec[0] = 1.0

    embedder = MockEmbedder(num_faces=1, vector=owner_vec)
    service = FaceIdentityService(embedder=embedder)

    # Pre-populate owner embedding in service cache
    service._cache["user_123"] = {
        "owner": {
            "name": "Alice Owner",
            "relationship": "",
            "embedding": owner_vec,
            "model": MODEL_VERSION,
        }
    }

    result = await service.identify(b"dummy_frame", uid="user_123", owner_name="Alice Owner")
    assert result.status == FaceVerificationStatus.OWNER
    assert result.similarity >= 0.99
    assert result.name == "Alice Owner"


@pytest.mark.asyncio
async def test_face_identity_known_person_match():
    # Current face vector along axis 1
    person_vec = np.zeros(128, dtype=np.float32)
    person_vec[1] = 1.0

    owner_vec = np.zeros(128, dtype=np.float32)
    owner_vec[0] = 1.0  # orthogonal to person_vec

    embedder = MockEmbedder(num_faces=1, vector=person_vec)
    service = FaceIdentityService(embedder=embedder)

    service._cache["user_123"] = {
        "owner": {"name": "Alice", "embedding": owner_vec, "relationship": ""},
        "person_bob": {"name": "Bob", "relationship": "brother", "embedding": person_vec},
    }

    with patch("src.memory.known_people.get_known_people", return_value=[{"id": "person_bob", "name": "Bob", "relationship": "brother"}]):
        result = await service.identify(b"dummy_frame", uid="user_123")
        assert result.status == FaceVerificationStatus.KNOWN_PERSON
        assert result.person_id == "person_bob"
        assert result.name == "Bob"
        assert result.relationship == "brother"
        assert result.similarity >= 0.99


@pytest.mark.asyncio
async def test_face_identity_unknown_person():
    # Face vector along axis 2 (orthogonal to both owner and known person)
    guest_vec = np.zeros(128, dtype=np.float32)
    guest_vec[2] = 1.0

    owner_vec = np.zeros(128, dtype=np.float32)
    owner_vec[0] = 1.0

    embedder = MockEmbedder(num_faces=1, vector=guest_vec)
    service = FaceIdentityService(embedder=embedder)

    service._cache["user_123"] = {
        "owner": {"name": "Alice", "embedding": owner_vec, "relationship": ""},
    }

    with patch("src.memory.known_people.get_known_people", return_value=[]):
        result = await service.identify(b"dummy_frame", uid="user_123")
        assert result.status == FaceVerificationStatus.UNKNOWN_PERSON
        assert result.faces_detected == 1


@pytest.mark.asyncio
async def test_face_identity_threshold_boundary():
    # Angle where similarity is 0.44 (just below 0.45 threshold)
    owner_vec = np.zeros(128, dtype=np.float32)
    owner_vec[0] = 1.0

    test_vec = np.zeros(128, dtype=np.float32)
    test_vec[0] = 0.44
    test_vec[1] = np.sqrt(1.0 - 0.44**2)

    embedder = MockEmbedder(num_faces=1, vector=test_vec)
    service = FaceIdentityService(embedder=embedder, owner_threshold=0.45)

    service._cache["user_123"] = {
        "owner": {"name": "Alice", "embedding": owner_vec, "relationship": ""},
    }

    with patch("src.memory.known_people.get_known_people", return_value=[]):
        result = await service.identify(b"dummy_frame", uid="user_123")
        # 0.44 is below 0.45 -> must NOT match owner!
        assert result.status == FaceVerificationStatus.UNKNOWN_PERSON


@pytest.mark.asyncio
async def test_lazy_migration_generates_and_stores_embedding(mock_db):
    _, mock_coll = mock_db
    mock_doc = MagicMock()
    mock_coll.document.return_value = mock_doc

    target_vec = np.zeros(128, dtype=np.float32)
    target_vec[0] = 1.0

    embedder = MockEmbedder(num_faces=1, vector=target_vec)
    service = FaceIdentityService(embedder=embedder)

    # Empty cache and empty Firestore initially
    mock_coll.stream.return_value = []

    # Owner photo URL provided, but no embedding yet
    import base64
    dummy_b64 = base64.b64encode(b"fake_jpeg").decode()

    with patch("src.vision.face_identity_service.fetch_reference_photo_b64", new=AsyncMock(return_value=dummy_b64)):
        result = await service.identify(
            b"live_frame",
            uid="user_lazy",
            owner_photo_url="gs://bucket/owner.jpg",
            owner_name="Lazy Owner",
        )
        assert result.status == FaceVerificationStatus.OWNER
        # Check that embedding was saved to Firestore
        mock_coll.document.assert_called_with("owner")
        mock_doc.set.assert_called_once()
        saved_data = mock_doc.set.call_args[0][0]
        assert saved_data["person_id"] == "owner"
        assert len(saved_data["embedding"]) == 128
        assert saved_data["model"] == MODEL_VERSION


@pytest.mark.asyncio
async def test_delete_person_embedding_removes_from_firestore_and_cache(mock_db):
    _, mock_coll = mock_db
    mock_doc = MagicMock()
    mock_coll.document.return_value = mock_doc

    service = FaceIdentityService(embedder=MockEmbedder())
    service._cache["user_123"] = {
        "person_1": {"name": "Bob", "embedding": np.zeros(128)},
    }

    service.delete_person_embedding("user_123", "person_1")

    # Document deleted
    mock_coll.document.assert_called_with("person_1")
    mock_doc.delete.assert_called_once()
    # Evicted from cache
    assert "person_1" not in service._cache["user_123"]


@pytest.mark.asyncio
async def test_inference_exception_fails_safe():
    embedder = MagicMock()
    embedder.detect_and_embed.side_effect = RuntimeError("OpenCV crash")

    service = FaceIdentityService(embedder=embedder)
    result = await service.identify(b"frame", uid="user_123")

    assert result.status == FaceVerificationStatus.VERIFICATION_UNAVAILABLE
    assert result.faces_detected == 0
