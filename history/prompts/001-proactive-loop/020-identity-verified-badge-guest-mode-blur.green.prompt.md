---
id: 020
title: Identity Verified Badge and Guest Mode Blur Overlay
stage: green
date: 2026-03-16
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: 001-proactive-loop
user: Haris
command: do both and remember the face detection should check every 5 or 10 seconds for best privacy
labels: ["demo", "identity", "guest-mode", "ui", "privacy", "websocket"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/src/watchman/state_monitor.py
  - frontend/src/app/dashboard/page.tsx
tests:
  - manual: owner sits down → Identity Verified badge appears in navbar
  - manual: guest sits down → badge swaps to Guest Mode red, canvas blurs, lock overlay appears
  - manual: owner returns → unblur, Identity Verified reappears, Rumi face goes happy for 3s
  - manual: face_check_interval = 2 cycles × 5s = 10s verified unchanged
---

## Prompt

do both and remember the face detection should check every 5 or 10 seconds for best privacy

(Context: user agreed to implement "The Hook" — Identity Verified badge on owner camera confirm — and "The Moat" — canvas blur + Guest Mode badge + unblur on owner return, from the Gemini demo script. Face detection already runs at 2 cycles × 5s = 10s intervals, which is correct.)

## Response snapshot

**Backend (state_monitor.py):**
- Added `_owner_verified_sent: bool = False` flag to StateMonitor.__init__
- In `_run_face_check()` owner branch:
  - When `_guest_active` was True, re-arm `_owner_verified_sent = False` before sending `owner_returned`
  - Then: if `not _owner_verified_sent`, send `{"type": "identity_verified"}` WS event and set flag
  - This fires once per ownership period; re-fires after every guest visit
- In guest branch (Step 3): set `_owner_verified_sent = False` so owner return re-sends identity_verified
- Face check interval unchanged at 2 cycles × 5s = every 10 seconds

**Frontend (dashboard/page.tsx):**
- Added `identityVerified` state (boolean)
- WS handler updates:
  - `identity_verified` → `setIdentityVerified(true)`
  - `guest_detected` → `setGuestMode(true)` + `setIdentityVerified(false)`
  - `owner_returned` → `setGuestMode(false)` + `setIdentityVerified(true)` + `setRumiEmotion("happy")` + 3s timeout reset to neutral
- Navbar: "Identity Verified" teal shield badge when `identityVerified && !guestMode`
- Navbar: "Guest Mode" red warning badge when `guestMode` (replaces verified badge)
- canvas-zone div: `filter: blur(10px) saturate(0.2)` + `pointerEvents: none` when `guestMode`
- Added `position: relative` to app-body div for overlay positioning
- Guest mode lock overlay: fixed inside app-body, shows lock icon + "Session Locked" message

## Outcome

- ✅ Impact: The Hook and The Moat demo sections are fully implemented — judges see instant identity verification and dramatic canvas privacy protection
- 🧪 Tests: manual only — requires owner photo in Firebase and face visible to camera
- 📁 Files: 2 files modified (backend state_monitor, frontend dashboard)
- 🔁 Next prompts: FIREBASE_STORAGE_BUCKET env var on Cloud Run; DEMO_MODE=true on Cloud Run for demo day
- 🧠 Reflection: Face check at 10s is the right privacy/latency balance — fast enough for demo, slow enough to not spam the API
