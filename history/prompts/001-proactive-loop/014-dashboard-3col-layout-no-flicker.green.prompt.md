---
id: "014"
title: "Dashboard 3-column layout, emotion panel no-flicker"
stage: green
date: "2026-03-07"
surface: agent
model: claude-sonnet-4-6
feature: "001-proactive-loop"
branch: "001-proactive-loop"
user: Haris
command: continue
labels: ["frontend", "layout", "ux", "fer", "emotion-detection"]
links:
  spec: "null"
  ticket: "null"
  adr: "null"
  pr: "null"
files:
  - frontend/src/app/dashboard/page.tsx
tests: []
---

## Prompt

Resume exactly from where you left off — restructure dashboard layout:
- Move emotion panel and camera PiP out of fixed corners into a 3-column row beside the main Rumi card
- Remove all dragging functionality from camera PiP
- Fix emotion panel IIFE flickering (React treats IIFE result as new element each render)
- Full responsive CSS: on mobile (<640px) hide sidebars, center column takes full width

## Response

Three targeted edits to `frontend/src/app/dashboard/page.tsx`:

1. **Removed PiP drag useEffect** (lines 157–180) — deleted `setPipPos`, `pipDragRef`, all mouse/touch drag listeners and `window.innerWidth` calculations.

2. **Added emotion vars before render** — extracted `EMOTION_COLORS`, `emotionEntries`, `dominantEmotion` as plain variables before `return (` so React never sees them as new element trees.

3. **Replaced fixed-position blocks with 3-column `.main-row` flex layout**:
   - `.emotion-sidebar` (190px, left) — shows FER bars inline, hidden on mobile
   - Center column (`flex: 0 1 380px`) — greeting + Rumi glass card + intervention card
   - `.camera-sidebar` (right) — 160×90 16:9 video + cam/mic toggles, hidden on mobile
   - CSS: `.main-row { display: flex; flex-direction: row; gap: 20px; }` with `@media (max-width: 639px)` collapsing to column and hiding sidebars

## Outcome

- No more fixed-position overlays going off-screen
- No more IIFE flickering — emotion bars animate smoothly via `transition: width 0.5s ease`
- Clean 3-column layout on desktop, single-column on mobile
- Zero `pipPos`/`pipDragRef`/`sendTranscript` references remain in file
