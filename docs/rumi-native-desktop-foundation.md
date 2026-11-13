# Native Windows local control foundation

This increment adds a portable Windows host for the existing desktop design. The
`/desktop-local/` page connects only to the embedded native bridge. A normal browser
shows a disabled workspace. `/desktop/` remains the separate simulated preview.

## What runs locally

Typed commands can launch the fixed Windows Notepad and Explorer entry points,
list supported files, read a text file, or create a new text file in one selected
folder. The existing deterministic parser and Windows executor are reused. No model
tokens, Firebase session, camera, microphone, arbitrary shell, or downloaded model
are required. Unsupported requests ask for clarification.

The new mode trusts the current unlocked Windows account and an explicit native
folder-selection/confirmation flow. It does not represent Google or face identity.
The existing cloud helper's owner/presence authorization is unchanged.

## Permission and execution boundaries

- A native folder picker supplies the root; renderer requests cannot supply it.
  The native confirmation describes the supported actions and 15-minute grant.
- Expiry uses a monotonic clock and never renews on activity. Stop, minimize,
  navigation, closing and detected lock revoke permission. A one-second watcher
  checks active grants; each action also checks the unlocked Windows desktop.
- The renderer sees a session identifier, never the executor credential. It can
  call only four explicitly exported closures. No runtime-bearing `js_api` object
  is exposed to pywebview's generic Python attribute resolver.
- Commands have fresh IDs, short deadlines and strict fields. One action runs at
  a time; extra requests are rejected rather than queued. The existing persistent
  receipt journal prevents duplicate execution and records uncertain outcomes.
- Windows handle-based folder protections and exclusive file creation are reused.
  No overwrites, subfolder traversal, recursive access or arbitrary executable
  paths are accepted. Text contents render as text, never interpreted HTML.
- Stop can revoke while an action or picker is pending. Generation checks reject
  late consent and receipts. The UI clears private output after observed revocation.
  Actions already committed cannot be undone by Stop; uncertain actions are never
  retried automatically. App launch reports dispatch, not verified focus.
- A randomized loopback document address serves bundled UI and static assets only.
  There is no HTTP command endpoint. Host validation and a content-security policy
  block remote connections, frames, forms and non-bundled scripts. The native bridge
  checks the current document address before accepting calls.

The app runs as a normal Windows user and refuses administrator mode. These controls
constrain Rumi's UI and executor; they are not isolation against malware already
running as the same Windows account or an administrator.

## Build and distribution

See [desktop setup](../desktop/README.md). Python dependencies are isolated and
pinned in `desktop/requirements-lock.txt`. The package reuses installed Edge
WebView2 and includes the static frontend, Python runtime and dependency notices.
Build artifacts under `desktop/dist/` are ignored by Git. No backend ML model or
cloud backend service is needed for supported native commands.

This is an unsigned portable development build. A signed installer, update signing,
fresh-machine installation checks and measured all-day resource usage remain release
gates. Voice, browser automation, Windows settings, shutdown, global shortcuts,
tray/startup integration and general computer control are separate future work.

## Acceptance

Automated native tests exercise real temporary Windows files with injected desktop
authorization and app-launch fixtures. They cover permission expiry/revocation,
native consent, stale consent, stale/invalid requests, duplicate receipts, path and
command rejection, Stop during execution, closure-only exports and static-server
access restrictions. They do not substitute for physical window/lock acceptance.

Frontend tests cover the absent bridge, plain-text results, Stop with late receipts,
late consent, permission loss, timeout without retry, receipt mismatch and shortcuts.
The offline backend regression suite blocks live Firebase connections.

Validation on 2026-11-13:

| Check | Result |
| --- | --- |
| Native Windows test suite | 15 passed |
| Frontend Jest suite | 87 passed across 7 suites |
| Backend regression suite, strict runtime/unraisable warnings | 462 passed |
| TypeScript `npx tsc --noEmit` | Passed; final production build also type-checked |
| Production Next.js build | Passed; native route statically exported |
| PyInstaller Windows executable | Built successfully |
| Portable ZIP integrity and bundled notices | Passed; 234 entries, 19,307,733 bytes |
| Git whitespace checks | Passed |

Local artifact: `desktop/dist/RumiDesktop-Windows.zip` (about 18.4 MiB).
SHA-256: `0E831795C4D628BB2583E8B5AC6EDDF3FA2AD7189E8058D476B5CF574CF217D1`.
The executable was launched from this package's source folder. Full clean-machine
installation and command acceptance have not been completed.

The packaged executable started on this laptop. Its actual WebView2 accessibility
tree showed the rendered local UI, **Native connection ready**, cloud/microphone
off, and disabled command controls before folder consent. This establishes startup
and bridge initialization, not end-to-end command success.

Live follow-up observations on the same build:

- After the user completed the native consent flow, the actual window showed
  `Connected to your folder`, the disposable `desktop/build/acceptance` path,
  enabled command controls and a decreasing permission countdown.
- The create request for `native-acceptance.txt` completed through the app. Its
  result panel showed `File created and its contents verified.` Independent
  filesystem readback matched exactly `Rumi offline Windows acceptance.` (32
  bytes). The persistent receipt recorded `succeeded` with `bytes: 32`.
- These observations establish native consent and one real UI-to-file operation.
  They do not establish the read-command path from an independent file readback.

Live listing, overwrite rejection, read command, app launching, Stop, minimize/lock
and visual layout acceptance remain pending. The Windows automation tool reported
`FrameArrived` and `window capture` timeouts, then `coordinate input geometry is
unavailable`. Accessibility reads and setting the command field worked, but clicks
and keyboard submission could not be verified reliably. A user handoff is pending
for the remaining commands. Do not report those checks as passed from mocked
permission/launch tests or from the successful create alone.

Non-failing tooling notices: stale Browserslist data; backend Starlette/httpx and
Google Python-version deprecations; PyInstaller optional module warnings. No live
Gemini calls or Firebase authentication bypass were used in these checks.
