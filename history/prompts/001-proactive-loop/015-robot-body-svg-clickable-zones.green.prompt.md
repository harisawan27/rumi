---
id: "015"
title: "Robot body SVG with clickable zones and popups"
stage: green
date: "2026-03-07"
surface: agent
model: claude-sonnet-4-6
feature: "001-proactive-loop"
branch: "001-proactive-loop"
user: Haris
command: continue
labels: ["frontend", "svg", "animation", "ux", "robot", "rumi-face"]
links:
  spec: "null"
  ticket: "null"
  adr: "null"
  pr: "null"
files:
  - frontend/src/components/RumiFace.tsx
  - frontend/src/app/dashboard/page.tsx
tests: []
---

## Prompt

If I give you an image of robot body. Will you make it in code? And replace this face with whole body as it is in image? [provided rumi.png at root] — not like a pic. I want you to code it and make it alive and movable. It's not what my image was looking. Can't you exactly make that?

## Response

Completely rewrote `frontend/src/components/RumiFace.tsx` as a full-body SVG robot matching rumi.png:

- `viewBox="0 0 200 380"`, `width="162" height="308"`
- White/gray gradient body (`#ffffff` → `#d0dde8`) via linearGradient `rbB`
- **Left arm**: chunky rect with red/yellow/blue Google color stripes stacked
- **Right arm**: chunky rect with single cyan stripe
- **Torso**: wide rounded rect (rx=26), chest inset panel, Google G (4 donut quadrant wedges + crossbar + centre cutout), blue glow dot below G
- **Head**: round blob rect, full-width dark visor (`#0b1a28`), two large green glowing eyes (r=12) with pupil tracking via mouse, eyelid blink overlay
- Hips, legs with cyan knee accents, wide feet
- Speaking: 5-bar waveform animates in mouth + chest G-centre dot pulses
- CSS `@keyframes rbAL/rbAR` for arm sway, `rumiBodyFloat` on wrapper div
- Pupil tracking: `window.addEventListener("mousemove")` → `targetRef.current` → `lerp(0.07)` RAF loop → `setPupil` state
- Clip paths `rbCL`/`rbCR` clip pupils inside eye circles

Rewrote `frontend/src/app/dashboard/page.tsx` to robot stage layout:
- Replaced 3-column layout with `.rumi-stage` (centered flex column)
- Added `showCameraPopup`, `showEmotionPopup` state + `cameraPopupVideoRef`
- Hidden `<video ref={videoRef}>` always in DOM for captureFrame; separate popup ref attached via `useEffect([showCameraPopup, liveStream])`
- **Clickable body zones**: `.zone-head` (top 3%, 64% wide, 27% tall) → expression popup to the right; `.zone-chest` (top 32%, 76% wide, 28% tall) → camera popup
- Popups: `position:absolute; left:calc(100% + 14px)` on desktop; `position:fixed; bottom:88px; left:50%; transform:translateX(-50%)` on mobile

## Outcome

- Full-body animated robot SVG coded purely in SVG+CSS — no image file used
- Floating, arm-swaying, blinking, pupil-tracking robot character on dashboard
- Clicking head zone shows live emotion detection bars; clicking chest zone shows camera preview with cam/mic toggles
- Hidden video element ensures captureFrame never breaks when popup is closed
- `rumiBodyFloat` keyframe defined in SVG `<style>` block, applied to outer wrapper div
