"""Explicit localhost-only artifact emulator client; never loads credentials."""
import os
import re
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore import Client

PROJECT = "demo-rumi-artifacts"


def require_emulator():
    host = os.getenv("FIRESTORE_EMULATOR_HOST", "")
    match = re.fullmatch(r"(?:127\.0\.0\.1|localhost):([0-9]{1,5})", host)
    if not match or not 1 <= int(match[1]) <= 65535:
        raise RuntimeError("Artifact emulator requires an explicit localhost host:port")
    if os.getenv("GCLOUD_PROJECT") != PROJECT:
        raise RuntimeError("Artifact emulator requires the dedicated demo project")
    if os.getenv("GOOGLE_CLOUD_PROJECT", PROJECT) != PROJECT:
        raise RuntimeError("Conflicting emulator project")
    return host


def create_emulator_client():
    require_emulator()
    return Client(project=PROJECT, credentials=AnonymousCredentials())
