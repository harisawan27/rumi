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
The executable was launched from this package's source folder. The user-assisted
command smoke test below passed on this laptop. Clean-machine installation and the
remaining reliability/release gates have not been completed.

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
- The user then ran listing, attempted to overwrite the note with `replacement`,
  read it with `Read that file`, launched Notepad and clicked Stop. The user
  confirmed that all behaved as expected, including the original read result.
- Read-only inspection of the native journal found this complete ordered receipt
  sequence: `succeeded` with `bytes: 32`, `succeeded`, `failed` with
  `reason: already_exists`, `succeeded`, and `dispatched` with `dispatched: true`
  and `verified_window: false`. This corroborates the reported command sequence;
  list/read contents and operation names are intentionally absent from the journal.
- Independent file readback after the overwrite test still matched the original
  32 bytes exactly. The current Windows inventory contained `Untitled - Notepad`
  from `C:\Windows\System32\notepad.exe`; it was absent before the test. The
  executor correctly reported dispatch rather than claiming verified focus.
- The final Rumi accessibility tree showed `Local permission cleared`, no selected
  folder path or private result, an empty disabled command field, and disabled
  command/shortcut buttons. No access was re-enabled for verification.

**User-assisted smoke test: passed** for folder consent, create, list, collision
protection, read, Notepad launch and idle Stop. List/read display correctness is
user-confirmed and supported by successful receipts; it was not captured by the
agent before Stop cleared the output. The create result, final stopped controls,
Notepad window inventory and unchanged file bytes were independently observed.

The Windows automation tool reported `FrameArrived` and `window capture` timeouts,
then `coordinate input geometry is unavailable`. Accessibility reads and setting
the command field worked, but clicks and keyboard submission could not be verified
reliably, so the user performed the remaining steps. This was not an unattended
automated UI pass.

Physical minimize/lock revocation, timed expiry, in-flight Stop, Explorer launch,
visual layout, restart/sleep recovery, clean-machine installation and the measured
eight-hour run remain open. Automated tests cover several of these boundaries but
do not substitute for their physical acceptance. The public-release limitations
above remain in force; this smoke test does not establish general PC control.

Non-failing tooling notices: stale Browserslist data; backend Starlette/httpx and
Google Python-version deprecations; PyInstaller optional module warnings. No live
Gemini calls or Firebase authentication bypass were used in these checks.
