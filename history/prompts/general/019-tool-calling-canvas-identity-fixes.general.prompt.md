---
name: Tool Calling, Canvas Fix, Identity Frequency Fix
description: Implemented Flash-based tool calling for canvas/profile/known-person routing; fixed _speak_verbatim canvas prompt; fixed identity_verified 10s frequency
type: general
stage: green
date: 2026-03-16
surface: agent
model: claude-sonnet-4-6
feature: 001-proactive-loop
branch: master
user: Haris
---

## Summary

Three changes implemented:

### 1. Fix: `_speak_verbatim` canvas prompt (session_manager.py:557-562)
**Problem**: When `canvas=True`, the old prompt included the first 120 words of the essay as a snippet, causing Gemini Live to read the essay content aloud instead of giving a brief acknowledgment.
**Fix**: Replaced with a simple instruction containing NO content — "Speak exactly ONE warm sentence telling them it's ready."

### 2. Fix: Identity_verified not firing every 10s (state_monitor.py:285-292)
**Problem**: `has_face()` FER pre-check was too strict — blocked Gemini face check even when person is present but FER misses them due to lighting/angle. Caused identity_verified to fire only once at session start.
**Fix**: Only skip the Gemini check when BOTH conditions are true: FER says no face AND last_state == "idle". If the state is neutral/focused/etc., proceed to Gemini even if FER missed the face.

### 3. Feature: Gemini Flash tool calling (main.py:470-570, 1068-1175)
**Replaces**: Brittle keyword matching for canvas routing + `_SAVE_PERSON_KEYWORDS` extraction
**New architecture**:
- All non-face, non-conversational queries → `_flash_smart()` which now returns `{"tool_call": {...}, "canvas_needed": bool, "title": str, "content": str}`
- Flash detects intent and extracts parameters for two tools:
  - `update_profile`: field + value extracted → `save_identity()` + `refresh_context()` + `profile_updated` WS event
  - `add_known_person`: person_name + relationship → `save_person_from_voice()` + `known_person_added` WS event
- Canvas routing: Flash decides `canvas_needed` — no more keyword lists
- Fast-path: short (≤8 words), clearly conversational queries skip Flash entirely → direct Gemini Live
- `_extract_smart_json()` updated to handle nested JSON (tool_call objects have nested dicts)

### 4. Frontend: New WS message types (session.ts, dashboard/page.tsx)
- Added `profile_updated` and `known_person_added` to `WsMessage` union type
- Dashboard shows toast notification on both events

## Files Modified
- backend/src/session/session_manager.py (canvas prompt fix)
- backend/src/watchman/state_monitor.py (FER pre-check logic)
- backend/src/api/main.py (tool calling, routing refactor, JSON extractor fix)
- frontend/src/services/session.ts (WsMessage types)
- frontend/src/app/dashboard/page.tsx (toast handlers)
