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

    # Cloud Run: service account JSON passed as base64-encoded env var
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        sa_dict = json.loads(base64.b64decode(sa_json).decode())
        cred = credentials.Certificate(sa_dict)
        firebase_admin.initialize_app(cred)
        return

    # Local dev: service account JSON file path
    sa_path = os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"]
    cred = credentials.Certificate(sa_path)
    firebase_admin.initialize_app(cred)


def get_db() -> Client:
    global _db
    if _db is None:
        _init_app()
        _db = firestore.client()
    return _db
