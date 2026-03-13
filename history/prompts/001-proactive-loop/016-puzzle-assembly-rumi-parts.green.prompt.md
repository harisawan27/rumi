---
id: "016"
title: "Puzzle assembly RumiFace from 12 extracted parts"
stage: green
date: "2026-03-08"
surface: agent
model: claude-sonnet-4-6
feature: "001-proactive-loop"
branch: "001-proactive-loop"
user: Haris
command: continue
labels: ["frontend", "svg", "animation", "ux", "robot", "rumi-face", "puzzle-assembly"]
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

Cut each part in rumi2.png as alone part and then join them like a puzzle to make the robot. (Continued from previous session — 12 parts already extracted to frontend/public/rumi-parts/ with flood-fill background removal. Assembly positions computed from rumi2.png pixel offsets relative to torso origin scaled by 0.22.)

## Response

Rewrote `frontend/src/components/RumiFace.tsx` using puzzle assembly approach:

- Container: 316×510 px (all parts positioned within, overflow visible for glow)
- Scale factor: 0.22 applied to rumi2.png pixel offsets; OFFSET_X=104.5, OFFSET_Y=117 to normalise negative coords
- **12 individual `<img>` tags** each absolutely positioned: head, torso, l-bicep, r-bicep, l-forearm, r-forearm, l-thigh, l-shin, r-shin, r-thigh, l-foot, r-foot
- **Left arm wrapper div** (l-bicep + l-forearm as children): `transformOrigin: ${lBicep.w}px 0px` (top-right = shoulder pivot), animation `rfLeftArm` ±12°
- **Right arm wrapper div** (r-bicep + r-forearm as children): `transformOrigin: 0px 0px` (top-left = shoulder pivot), animation `rfRightArm` ±12°
- **Head wrapper div**: `transformOrigin: 50% 100%` (neck bottom pivot), animation `rfHeadTilt` ±5°
- **Z-order**: legs(z=1) → arms(z=2) → torso(z=3, covers shoulder joints) → head(z=4) → SVG eyes(z=5)
- **Eye overlay** via SVG using EYE_L/EYE_R computed as fractions of head part position in container space (~36%/64% horizontal, 52% vertical of head image)
- **Speaking waveform**, blink timer, mouse pupil tracking, RAF lerp all preserved from previous version
- `filter: glowFilter` moved to the outer container div; SVG overlay has `filter: none` to avoid double-apply

Updated `.zone-head` and `.zone-chest` in `dashboard/page.tsx` to match new container (316×510):
- zone-head: `top:0%, left:38%, width:30%, height:18%`
- zone-chest: `top:22%, left:32%, width:39%, height:26%`

## Outcome

- Each body part is a separate image — no clip-path bleed (leg no longer waves with arm)
- Arms animated independently as grouped wrappers with correct shoulder pivots
- Torso naturally covers shoulder attachment seams at z=3
- Glow, blink, pupil tracking, and speaking waveform preserved
- Click zones recalibrated to new container dimensions
