# Rumi desktop interface preview

Implementation: 2026-11-12. Route: `/desktop/`. This is the interactive interface
milestone, not a Windows installer or a replacement for the authenticated executor.
It follows the user's decision to build while Gemini access is unavailable.

## Scope and boundaries

- Standalone React route with no Firebase/session imports, model calls, WebSocket,
  microphone access, browser automation or local-helper dispatch.
- Original SVG companion and scoped CSS tokens for graphite and daylight themes.
  Only the existing React and font dependencies are used. No external design-system
  source or Apple design assets were copied.
- Workspace, command dialog (`Ctrl+K` / `Cmd+K` within the page), activity, routines,
  preferences, a three-step introduction, and a movable compact companion within
  the browser viewport. It is not an always-on-top Windows overlay.
- Explicitly labelled browser/file rehearsals; closed sample grammar. Unsupported
  requests clarify locally. No catch-all model fallback.
- Progress comes from simulation timers, never evidence of OS execution. Stop,
  `Ctrl+Shift+.` / `Cmd+Shift+.`, and hiding the page cancel running rehearsals.
  A second task is not queued. Stale completion events cannot modify a new task.
- Shutdown only demonstrates a review state, with a dismissal control. It has no
  real shutdown action, countdown, or executor connection.
- Voice preview uses a sample transcript. Microphone and cloud AI remain off.
- Appearance changes affect only the preview and support undo from a theme command.
  Reduced motion respects both OS preference and a local setting.
- A prewritten welcome note can be edited and explicitly downloaded as `.txt`.
  The UI reports a download request, not a verified filesystem write.
- Notes and up to 30 activity records stay in tab memory and clear on reload.
  Only theme and reduced-motion preferences are stored in localStorage. Storage
  failures do not prevent use.
- Real operations remain behind the existing dashboard's authentication, fresh
  presence and helper pairing. The connection-details dialog explains that opening
  that dashboard may use cloud services. It never opens it automatically.

## Visual and interaction system

Three surfaces share one vocabulary: a quiet companion, a fast command bar and a
workspace that exposes the task's details. Graphite/ivory surfaces, soft green
accents, existing serif display typography and fine borders establish the visual
direction. Motion runs during a rehearsal or the explicitly labelled voice demo;
the idle companion is static. There is no background screenshot or audio polling.

Native HTML dialogs provide modal focus containment and Escape behavior. Closing
restores focus to the launching element. Inputs have accessible names, progress has
a polite status region, and controls expose selected/disabled state. Navigation
collapses at smaller sizes; editor and task content remain in normal document flow.

## Component-library decision

Meta's [Astryx](https://github.com/meta/astryx) is a candidate for later evaluation;
its documentation currently labels it beta. This increment establishes Rumi's
interaction and visual direction with the repository's existing React/CSS stack.
It does not claim an Astryx integration or benchmark. Before adopting it, compare
a pinned version's dialogs, menus, accessibility and bundle cost against the actual
prototype. Apple design-kit assets are not used in this Windows-oriented interface.

## Acceptance

Automated interaction coverage: cancellation with timers pending, stale event
rejection, duplicate task exclusion, simulation labelling, local activity,
unknown requests, shutdown non-execution, theme undo, tab-only note storage, sample
voice without microphone access, keyboard invocation, compact Stop and visibility
cancellation. Existing frontend regressions are included in the full Jest run.

Browser verification exercised the 1366px desktop and 390px mobile layouts, with
no horizontal overflow observed. Both themes, the introduction and focus return,
browser-task rehearsal, note editing/export and the compact companion were checked.
The downloaded acceptance note was read back from disk and matched the text entered
in the UI. These observations verify prototype behavior, not OS execution.

The final browser build also verified command-field focus on Ctrl+K, Escape focus
return, immediate Ctrl+Shift+. cancellation, direct Preferences access on mobile,
navigation scroll reset, and disabled animation with reduced motion enabled.

| Final automated check | Result |
| --- | --- |
| Full frontend Jest suite | 79 passed across 6 suites |
| TypeScript `npx tsc --noEmit` | Passed |
| Production `npm run build` | Passed; `/desktop/` statically exported |
| Git whitespace checks | Passed |

The backend was unchanged in this increment. Its earlier test results are documented
in the executor/command acceptance reports and were not relabelled as a new run.

This phase does not complete physical voice acceptance, Windows control, local authorization,
installer/update signing or the all-day resource measurement gates.
