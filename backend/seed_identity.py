"""
Seed Haris's core identity into Firestore.

Usage:
    python seed_identity.py <firebase_uid>

The UID comes from Firebase Auth — visible in the Firebase Console under
Authentication > Users, or printed in the backend logs on first sign-in.
"""
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from src.memory.firestore_client import get_db


IDENTITY = {
    # ── Core ──────────────────────────────────────────────────────────────────
    "name": "Haris",
    "full_name": "Muhammad Haris Awan",
    "age": 18,
    "dob": "15 April 2007",
    "location": "Karachi, Pakistan",
    "student_context": (
        "Intermediate (Humanities) student; Agentic AI Engineer student at GIAIC "
        "(Governor's Initiative for AI & Computing). Youngest son in a family-oriented home."
    ),
    "roles": [
        "Full Stack Developer",
        "Founder of WEBXES Tech (digital agency)",
        "Father's Upwork account manager (client: Rashid Javed Awan)",
        "Agentic AI student at GIAIC",
    ],
    "environment": (
        "Works from a home desk in Karachi — sensitive to cold waves and high winds. "
        "High-pressure, family-oriented environment."
    ),

    # ── Projects ──────────────────────────────────────────────────────────────
    "projects": [
        {
            "name": "Mirr'at",
            "status": "GOLD SPRINT — 9-day deadline",
            "context": (
                "Proactive AI desktop companion for the Google Gemini Live Agent Challenge. "
                "Currently battling GCP restricted account issues. Gold medal is the only option."
            ),
        },
        {
            "name": "DoneKaro",
            "status": "Phase 3/4 complete",
            "context": (
                "Cloud-native to-do application. Pain point: scaling backend on local "
                "Kubernetes (K8s) clusters."
            ),
        },
        {
            "name": "RehnumaAI",
            "status": "MVP complete",
            "context": (
                "Smart study guide for Pakistani students. Pain point: curriculum data "
                "integration and localization."
            ),
        },
        {
            "name": "Morph",
            "status": "Conceptual",
            "context": "Generative UI app builder — real-time UI generation from natural language.",
        },
        {
            "name": "WEBXES Tech",
            "status": "Ongoing",
            "context": "Digital agency. Pain point: managing client expectations via Upwork.",
        },
    ],

    # ── Work style ────────────────────────────────────────────────────────────
    "work_style": (
        "Late-night deep work sessions. High-intensity sprints followed by philosophical "
        "reflection. Follows Spec-Driven Development (SDD) methodology religiously using "
        "Spec-Kit Plus."
    ),
    "focus_breakers": [
        "Doom-scrolling",
        "Urban Karachi noise",
        "Feeling stagnant or generic in career growth",
    ],
    "communication_preference": (
        "Gentle but firm. Should not nag — inspire through wisdom (Rumi, Iqbal) or "
        "a sharp technical challenge. Urdu-English code-switching is natural and preferred."
    ),

    # ── Faith & schedule ──────────────────────────────────────────────────────
    "faith": "Practicing Muslim",
    "salah_awareness": (
        "Asr and Maghrib are natural low-energy zones in Karachi. "
        "Mirr'at should respect these times — suggest breaks around them, never push through."
    ),

    # ── Cultural anchors ──────────────────────────────────────────────────────
    "interests": [
        "Rumi's Masnavi",
        "Mahmoud Darwish poetry",
        "Ahmed Faraz poetry",
        "Allama Iqbal philosophy",
        "Turkish language and culture",
        "Istanbul scholarship aspiration",
        "Chess (currently learning)",
        "EA FC gaming",
        "Real Cricket (plays with friend Shoaib — custom scoreboard)",
        "Software craftsmanship",
        "Agentic AI",
    ],
    "turkish_goal": (
        "Haris is on a 343+ day Duolingo Turkish streak and is preparing for a "
        "future scholarship in Istanbul. Turkey is not just a destination — it is a dream."
    ),
    "leisure": (
        "Chess on Duolingo. EA FC and Real Cricket with his close friend Shoaib — "
        "they track wins on a custom scoreboard."
    ),

    # ── Goals & fears ─────────────────────────────────────────────────────────
    "immediate_goal": (
        "Win the Gold Medal in the Google Gemini Live Agent Challenge. "
        "Second place is not an option."
    ),
    "long_term_goal": (
        "Establish WEBXES as a major US/Pakistan LLC. Move to Turkey for advanced studies."
    ),
    "driving_fear": (
        "Being 'generic.' Falling into a repetitive life cycle without making a global impact."
    ),

    # ── Wellness ──────────────────────────────────────────────────────────────
    "wellness_trigger": (
        "Suggest Doodh Patti or Chai break when focus drops or frustration peaks. "
        "Five minutes away from the screen, not thirty."
    ),

    # ── Metadata ──────────────────────────────────────────────────────────────
    "last_updated": datetime.now(timezone.utc),
}


def seed(uid: str) -> None:
    db = get_db()
    ref = db.collection("users").document(uid)
    doc = ref.get()

    IDENTITY["user_id"] = uid

    if doc.exists:
        ref.update(IDENTITY)
        print(f"Updated existing identity for UID: {uid}")
    else:
        ref.set(IDENTITY)
        print(f"Created new identity document for UID: {uid}")

    print("Done. Mirr'at now knows Haris.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python seed_identity.py <firebase_uid>")
        sys.exit(1)
    seed(sys.argv[1])
