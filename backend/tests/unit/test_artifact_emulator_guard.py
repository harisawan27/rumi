"""Safety checks run offline and never construct a Firestore client."""
import pytest
from src.artifacts.emulator import PROJECT, require_emulator, create_emulator_client


@pytest.mark.parametrize("host,project", [
    ("", PROJECT), ("firestore.googleapis.com:443", PROJECT),
    ("127.0.0.1:8085", "production"), ("localhost:0", PROJECT),
    ("localhost:65536", PROJECT), ("https://localhost:8085", PROJECT),
    ("localhost.attacker.example:8085", PROJECT),
])
def test_reject_unsafe_emulator_configuration(monkeypatch, host, project):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", host)
    monkeypatch.setenv("GCLOUD_PROJECT", project)
    with pytest.raises(RuntimeError):
        require_emulator()


def test_emulator_setting_cannot_bypass_offline_client_guard(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8085")
    monkeypatch.setenv("GCLOUD_PROJECT", PROJECT)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", PROJECT)
    assert require_emulator() == "127.0.0.1:8085"
    with pytest.raises(RuntimeError, match="forbidden"):
        create_emulator_client()


def test_conflicting_project_rejected(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8085")
    monkeypatch.setenv("GCLOUD_PROJECT", PROJECT)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "production")
    with pytest.raises(RuntimeError, match="Conflicting"):
        require_emulator()
