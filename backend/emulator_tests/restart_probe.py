"""Fresh backend process, fake identity/presence, real anonymous emulator storage."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.artifacts.emulator import require_emulator, create_emulator_client

require_emulator()
if __name__ == "__main__":
    with patch("firebase_admin.initialize_app", side_effect=RuntimeError("no cloud")), patch("src.memory.firestore_client.get_db", side_effect=RuntimeError("no cloud")):
        from fastapi.testclient import TestClient
        from src.api import main
        from src.artifacts import routes
        from src.artifacts.firestore_repository import FirestoreArtifactRepository
        uid, artifact_id = sys.argv[1:]
        import os
        os.environ["RUMI_ARTIFACTS_ENABLED"] = "1"
        client = create_emulator_client()
        routes.repository = FirestoreArtifactRepository(lambda: client)
        main.app.dependency_overrides[main.get_current_uid] = lambda: uid
        from src.session.session_manager import SessionManager
        manager = SessionManager()
        manager._uid = uid
        manager._session_id = "new_backend_session"
        manager._status = "active"
        main._session_managers[uid] = manager
        presence = {"mode": "owner", "session_id": "new_backend_session", "owner_verified_until": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat()}
        with patch("src.session.presence_manager.presence_manager.get_presence", return_value=presence):
            response = TestClient(main.app).get(f"/generated-artifacts/{artifact_id}?session_id=new_backend_session&request_id=750e8400-e29b-41d4-a716-446655440000")
            assert response.status_code == 200, response.text
            print(json.dumps(response.json()["result"]["artifact"]))
        client.close()
