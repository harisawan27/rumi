import base64
import json
import os
import tempfile

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client

_db: Client | None = None


def _init_app() -> None:
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        return

    # Optional storage bucket — enables firebase_admin.storage.bucket()
    bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    options = {"storageBucket": bucket} if bucket else {}

    # Service account JSON passed as base64-encoded or raw JSON env var
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        sa_json = sa_json.strip()
        try:
            if sa_json.startswith("{"):
                sa_dict = json.loads(sa_json)
            else:
                sa_dict = json.loads(base64.b64decode(sa_json).decode("utf-8"))
        except Exception:
            # Fallback to direct json parse
            sa_dict = json.loads(sa_json)
        cred = credentials.Certificate(sa_dict)
        firebase_admin.initialize_app(cred, options)
        return

    # Local dev: service account JSON file path or auto-discovery
    sa_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if not sa_path:
        for candidate in [
            "firebase-service-account.json",
            "firebase-sa.json",
            "backend/firebase-service-account.json",
            os.path.join(os.path.dirname(__file__), "..", "..", "firebase-service-account.json"),
        ]:
            if os.path.isfile(candidate):
                sa_path = candidate
                break

    if sa_path and os.path.isfile(sa_path):
        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred, options)
    else:
        # Fallback to default application credentials if available
        try:
            firebase_admin.initialize_app(options=options)
        except Exception as exc:
            raise RuntimeError(
                "Firebase initialization failed: FIREBASE_SERVICE_ACCOUNT_JSON or valid FIREBASE_SERVICE_ACCOUNT_PATH required."
            ) from exc


def get_db() -> Client:
    global _db
    if _db is None:
        _init_app()
        _db = firestore.client()
    return _db
