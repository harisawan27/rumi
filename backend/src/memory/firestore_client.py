import os
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client

_db: Client | None = None


def _init_app() -> None:
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        return
    service_account_path = os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"]
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)


def get_db() -> Client:
    global _db
    if _db is None:
        _init_app()
        _db = firestore.client()
    return _db
