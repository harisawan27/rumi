# Rumi — Fluid Zones UI Plan
# Status: PENDING
# Last updated: 2026-03-08

---

## Vision

One screen. Two fluid zones. No mode switching. No chat bubbles.

Default state: Rumi centered, large, full presence — ambient and alive.
Active state: Rumi slides to left corner, Artifact Canvas expands from the right.
The TRANSITION is the UI. That 0.5s animation is the demo moment.

Demo flow:
  1. User opens app → Rumi centered, breathing, ambient.
  2. User says: "Rumi, solve this" (points camera at notebook)
  3. Rumi pulses → "I see the problem, Haris. Projecting now."
  4. Canvas slides in from right. Rumi moves left. Solution renders as formatted markdown.
  5. User reads, copies, scrolls. Rumi stays present on the left.
  6. User dismisses canvas. Rumi glides back to center.

---

## What We NEVER Touch

- frontend/src/components/RumiFace.tsx      — rumi.png stays, floating animation stays, emotion states stay
- Voice pipeline logic                      — startListeningWithRef, sendToRumi, playAudio all untouched
- WS connection / auto-reconnect logic      — stable, untouched
- InterventionCard, PauseButton, ObservationIndicator components — untouched
- Auth / session flow (verifyAuth, getIdentity, startSession, endSession) — untouched
- All other pages: onboarding, profile, sign-in — untouched

---

## Phase 1 — Fluid Layout Foundation
### Status: [x] COMPLETE
### Files touched: frontend/src/app/dashboard/page.tsx

Goal: Evolve single-column rumi-stage into dual-zone layout with animation.
No new features. Zero risk.

Tasks:
  [x] 1.1 — Add state: canvasOpen (boolean, default false) to dashboard
  [x] 1.2 — Restructure main layout:
            - CSS Grid container (.app-body) replaces single rumi-stage
            - grid-template-columns: 1fr 0fr (canvas hidden) → 32fr 68fr (canvas open)
            - Left: .rumi-zone — contains all existing content
            - Right: .canvas-zone — hidden by default
  [x] 1.3 — Rumi Zone: display flex column, overflow visible (HUDs can escape)
  [x] 1.4 — Canvas Zone: opacity 0 + pointer-events none → opacity 1 on canvas-open
            - grid handles sizing; opacity handles fade-in with 0.2s delay
            - transition: grid-template-columns 0.55s cubic-bezier(0.4, 0, 0.2, 1)
  [x] 1.5 — All existing content stays inside rumi-zone — nothing moved/broken
  [x] 1.6 — rumi-stage overflow changed to visible (HUD popups no longer clipped)
  [x] 1.7 — Mobile: grid-template-rows used instead of columns (35fr/65fr split)

Acceptance: Current UI looks and works 100% the same. Toggling canvasOpen state
            produces a smooth split-screen animation.

---

## Phase 2 — Artifact Canvas Component
### Status: [x] COMPLETE
### Files touched: frontend/src/components/ArtifactCanvas.tsx (NEW)

Goal: Build the canvas panel that renders Rumi's text responses beautifully.

Tasks:
  [x] 2.1 — Created ArtifactCanvas component (CanvasContent export + Props)
  [x] 2.2 — Styling matches design system:
            - Glass morphism bg rgba(4,8,15,0.55) + blur(28px)
            - Teal corner brackets (4 absolute divs)
            - Header: "[RUMI CORE] :: {title}" with live pulsing teal dot
            - Dismiss button (X) — calls onDismiss
  [x] 2.3 — Content renderer:
            - type "text": plain paragraph, var(--text-2), lineHeight 1.78
            - type "code": full pre/code block, teal color, monospace
            - type "markdown": custom renderMarkdown() — h1/h2/h3, bold/inline-code,
              bullet lists (◆), numbered lists, fenced code blocks with lang label
  [x] 2.4 — Scrollable div with ref — auto-scrolls to top on new content
  [x] 2.5 — Mobile: canvas-zone uses grid-template-rows, fills bottom 65fr
  [x] 2.6 — Empty state: two concentric ping rings + "Awaiting projection" label
  [x] 2.7 — Imported and placed inside canvas-zone in dashboard

Acceptance: Canvas renders text, code, and markdown correctly.
            Dismiss closes canvas and Rumi animates back to center.
            Design matches Rumi's design system (gold, teal, glass).

---

## Phase 3 — Wire Canvas to Backend (text_response)
### Status: [x] FRONTEND DONE — Backend pending
### Files touched:
###   - frontend/src/app/dashboard/page.tsx (handleWsMessage) — DONE
###   - backend/src/session/session_manager.py or live_client.py — PENDING

Goal: Backend sends text alongside audio for complex responses.
      Canvas opens automatically when text_response is received.

Frontend tasks:
  [x] 3.1 — Added state: canvasContent (CanvasContent | null) to dashboard
  [x] 3.2 — handleWsMessage: text_response case added
            - Sets canvasContent from { title, content, content_type }
            - Sets canvasOpen = true
            - audio_response handler unchanged
  [x] 3.3 — canvasContent passed to ArtifactCanvas
  [x] 3.4 — handleCanvasDismiss: canvasOpen=false, clears content after 550ms

Backend tasks:
  [x] 3.5 — user_text handler in main.py is the entry point (query() → reply_text)
  [x] 3.6 — Added WS send in _respond() after query() returns:
            { "type": "text_response", "title": "...", "content": reply_text, "content_type": "markdown" }
  [x] 3.7 — Heuristic: send text_response only when len(reply_text) > 200 chars
  [x] 3.8 — _make_title() helper derives short canvas title from query text

Acceptance: Short proactive interventions = audio only, canvas stays closed.
            Complex answers = audio plays AND canvas opens with formatted content.

---

## Phase 4 — Override Command Input
### Status: [x] COMPLETE
### Files touched: frontend/src/app/dashboard/page.tsx (additive only)

Goal: Hidden text input for when mic isn't practical (noise, privacy).
      Slides up from bottom. Uses existing sendToRumi — zero new backend work.

Tasks:
  [x] 4.1 — Added state: overrideOpen (boolean, default false)
  [x] 4.2 — Added state: overrideText (string) + overrideInputRef
  [x] 4.3 — Keyboard "/" opens override; Escape closes and clears
            - Separate useEffect (does not interfere with Space bar effect)
            - Auto-focuses input 40ms after open via useEffect on overrideOpen
  [x] 4.4 — Input UI: .override-panel fixed bottom, translateY(110%) → translateY(0)
            - Teal "›" prefix, pill-shaped input, gold Send button
            - Teal border glow on focus
            - Enter submits, Escape dismisses
  [x] 4.5 — handleOverrideSubmit: calls sendToRumi, clears text, closes panel
  [x] 4.6 — sendToRumi unchanged — same function, same path
            - Hint updated: "Tap · Space · / for text"

Acceptance: "/" opens input, Enter sends via existing voice path, Escape dismisses.
            Rumi responds identically whether input came from voice or override command.

---

## Phase 5 — Notebook Mode (Camera + Voice Multimodal)
### Status: [ ] NOT STARTED
### Files touched:
###   - frontend/src/app/dashboard/page.tsx (sendToRumi modification)
###   - backend/src/session/session_manager.py (handle optional image field)
###   - backend/src/gemini/live_client.py or prompt_builder.py (pass image to Gemini)

Goal: When user speaks while camera is on, capture snapshot and send with query.
      Gemini sees the notebook + hears the question. Canvas shows the solution.

Frontend tasks:
  [x] 5.1 — sendToRumi(text, image?) — optional image param, payload includes image if present
  [x] 5.2 — captureFrameRef added; exposed via captureFrameRef.current = captureFrame in init()
            rec.onend: if cameraEnabled && captureFrameRef.current → capture then sendToRumi
  [x] 5.3 — WS payload: { type: "user_text", text, image? } — image only set when camera on

Backend tasks:
  [x] 5.4 — user_text handler: image_b64 = msg.get("image") extracted (None if absent)
  [x] 5.5 — _generate_canvas_from_image(): Gemini 2.5 Flash multimodal call in main.py
  [x] 5.6 — query() handles audio via _on_audio; Flash canvas runs as background task
            Both concurrent: audio plays immediately, canvas appears ~2-4s later
  [x] 5.7 — Camera off → unchanged voice-only path; Camera on → image attached to query

Acceptance: Camera off = voice only (existing behavior). Camera on = image+voice sent.
            Notebook solution renders on canvas. User can copy the text.

---

## Implementation Order

Phase 1 → Phase 2 → Phase 4 → Phase 3 → Phase 5

Reason: Phase 1 and 2 are pure frontend, zero risk, no backend.
        Phase 4 uses existing sendToRumi — zero backend needed.
        Phase 3 and 5 require backend coordination — do last.

---

## Design Constraints (must respect throughout)

- Design tokens: --bg, --surface, --surface-2, --border, --border-2, --gold, --teal, --text, --text-2, --muted
- Rumi avatar: rumi.png — size, animation, emotion states unchanged
- HUD panels: reuse .hud-panel, .hud-corner, .hud-header CSS already defined in dashboard
- Animations: smooth cubic-bezier transitions, never jarring snaps
- Mobile: always test — Rumi top 35vh, canvas bottom 65vh, scrollable
- No chat bubbles anywhere — subtitles or canvas only
- canvasOpen=false must look IDENTICAL to current dashboard

---

## Progress Tracker

Phase 1 — Fluid Layout Foundation       [x] 7/7 tasks COMPLETE
Phase 2 — Artifact Canvas Component     [x] 7/7 tasks COMPLETE
Phase 3 — Wire Canvas to Backend        [x] 8/8 tasks COMPLETE
Phase 4 — Override Command Input        [x] 6/6 tasks COMPLETE
Phase 5 — Notebook Mode                 [x] 7/7 tasks COMPLETE

Total: 35 / 35 tasks complete

## Notes
- HUD popups on desktop: rumi-stage overflow changed to visible so popups escape cleanly
- CSS Grid transition used for fluid zones (supported Chrome 107+, Safari 16.4+, Firefox 112+)
- canvasContent cleared 550ms after dismiss to allow exit transition to complete
- Phase 5: Gemini Live handles audio concurrently with Gemini Flash canvas (~2-4s delay for canvas)
- Phase 3: text_response sent only when reply_text > 200 chars (avoids canvas spam for short answers)
- _generate_canvas_from_image runs as asyncio.create_task — never blocks audio response
