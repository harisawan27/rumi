"""One-time script: seed Haris's Core Identity document into Firestore.

Usage:
    cd backend
    python src/identity/seed_identity.py
"""

import sys
import os
from datetime import datetime, timezone

# Allow running from backend/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
load_dotenv()

from src.memory.firestore_client import get_db


if len(sys.argv) < 2:
    print("Usage: python src/identity/seed_identity.py <firebase_uid>")
    sys.exit(1)
HARIS_UID = sys.argv[1]

CORE_IDENTITY = {
    "user_id": HARIS_UID,
    "name": "Haris",
    "location": "Karachi, Pakistan",
    "projects": [
        {
            "name": "DoneKaro",
            "status": "Docker setup in progress",
            "context": "Task manager app for local market",
        },
        {
            "name": "RehnumaAI",
            "status": "Auth flow complete",
            "context": "AI guide for students",
        },
    ],
    "interests": ["Rumi", "Turkish culture", "software craftsmanship"],
    "last_updated": datetime.now(timezone.utc),
}


def seed() -> None:
    db = get_db()
    ref = db.collection("users").document(HARIS_UID)
    ref.set(CORE_IDENTITY)
    print(f"✓ Core Identity seeded for UID: {HARIS_UID}")
    print(f"  Firestore path: users/{HARIS_UID}")


if __name__ == "__main__":
    seed()
