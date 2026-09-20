# Validated study tracker: boundary and renderer proof

This milestone supplies a secure, trusted execution and presentation path for
validated `study_tracker_v1` data. It does not connect model planning or generate
interfaces. The contracts from `3af9d53` remain unchanged.

## Security gaps and changes

The observation socket verified a Firebase ID token, then obtained/created the
UID's local manager without validating the supplied session ID. It sent Canvas
history before presence checks. Canvas generation used detached persistence
tasks without rechecking owner authorization. The existing REST privacy guard
allowed missing presence and unexpected lookup exceptions. Conversation history
also contains saved Canvas answers. Desktop privacy treatment blurred mounted
Canvas content.

`artifacts/access.py` now requires the authenticated UID, a syntactically bounded
session ID, the matching existing SessionManager, an active/paused session, no
local guest lock, and fresh distributed owner presence for that same session.
It bypasses positive presence caching. Missing, unknown, guest, away, expired,
malformed, failed and timed-out presence all deny access with the same generic
403. The lookup is bounded to three seconds. Session identity and local guest
state are checked again after the lookup. No foreign-session existence is
returned. Socket attachment rejects invalid sessions before accepting the socket.

The guard applies to generated reads/history/state/spec edits, legacy Canvas
history and generation/follow-ups, and conversation history because it carries
Canvas answers. It runs before work and again before writes and delivery. New
generated-artifact writes recheck while holding the repository lock, with no
yield between that check and the in-memory commit. Revocation during work prevents
commit; revocation detected after an authorized commit prevents delivery but does
not undo a previously authorized write. This does not claim a transaction across
the presence store and a separate artifact store. Profile, memory, voice and
identity behavior outside this boundary are unchanged.

## Repository and transport

`MemoryArtifactRepository` is an intentionally **process-local, non-durable**
repository. All generated routes require explicit `RUMI_ARTIFACT_PROOF_MODE=1`.
Use one backend worker. Restarting it loses all trackers. Do not enable this
proof mode as a production persistence solution.

Every key is `(authenticated UID, artifact ID)`. Clients supply neither owner
nor storage paths. An unknown/foreign ID returns the same 404. Invalid stored
envelopes cannot reach the renderer. There is a 20-artifact-per-UID proof cap.
The existing clear-Canvas-data endpoint also clears this UID's proof artifacts.

Routes under `/generated-artifacts` require the Firebase bearer token and
`session_id`:

- `POST /proof?request_id=<UUID4>` constructs an empty tracker from the shared
  fixture, with a server UUID, current date, timestamps and current session ID.
- `GET /` returns authorized artifact IDs; `GET /<id>?request_id=<UUID4>` reloads
  one validated artifact.
- `POST /state` accepts only `add_entry` or `remove_entry`, artifact ID,
  `expected_state_revision`, and a request UUID.
- `POST /spec?request_id=<UUID4>` accepts the existing typed edit decision:
  subject color or daily graph visibility, with `expected_revision`.

Server validation enforces the original subject/week/entry/minutes bounds.
Atomic compare-and-swap under the repository lock accepts only one update for a
given revision. State edits increment only `state_revision`; spec edits preserve
entries and advance only `revision` (no-op spec edits retain it). Conflicts return
409. The response wraps the original correlated `ArtifactResult` plus a short
authorization lease, capped at five seconds. No WebSocket model router was added.

## Frontend and privacy

`types/artifacts.ts` validates closed objects and known renderer/schema values
before mounting. Shared Python fixtures are consumed unchanged by frontend tests.
`GeneratedArtifact.tsx` selects one trusted React component through an explicit
switch. Titles/labels are React text; the application alone owns colors, styles,
controls and graph geometry. No HTML parser, runtime compiler, generated code,
dynamic component path or Morph runtime is present.

The existing ArtifactCanvas has a discriminated generated-UI branch; legacy
text/code/Markdown rendering is preserved. The tracker supports adding/removing
entries, week-bound dates, whole positive minutes, weekly/subject/daily totals,
and a simple opt-in graph with the same textual daily totals. Controls are labeled,
keyboard usable and at least 44px tall. Pure calculations have no persistence.

`ArtifactClient` owns one explicitly selected artifact ID and both revisions.
Generated payloads never enter legacy Canvas history arrays or browser storage.
An update is displayed only after the authoritative response matches the pending
request and selected ID. Errors and conflicts clear the view pending a fresh read.

Guest/away events, disconnects, page hiding, authorization failures and teardown
clear live payloads, abort requests and invalidate their generation. Owner return
reloads the retained ID from the backend. A late response from a previous
generation cannot remount content. While visible, the client refreshes every two
seconds; lease expiration removes content even if refresh hangs. Remote presence
changes without a local event are bounded by this lease rather than instant.
React also gates the generated branch on current owner/session state. Legacy
Markdown privacy UX is not otherwise redesigned.

## Deterministic test isolation

`backend/tests/conftest.py` installs guards during pytest configuration, before
test collection imports production aliases. It blocks Firebase initialization,
Admin Firestore clients, sync/async Google Firestore client constructors, and
the application `get_db` function. Tests must inject fake repositories/documents.
Local credential files and environment variables cannot enable cloud access.
No credential environment override is needed to run the suite. A dedicated test
checks that these guards remain active even with a credential path configured.

There are no emulator tests in this ordinary suite. Future emulator tests must
use a separate entrypoint with an explicit test project and localhost emulator;
do not add a production-credential escape hatch to this conftest.

## Manual acceptance

For the authenticated backend path, run one backend worker with
`RUMI_ARTIFACT_PROOF_MODE=1` and the frontend with
`NEXT_PUBLIC_ARTIFACT_PROOF_MODE=1`. Sign in normally and wait for verified owner
presence in the existing dashboard. Choose **Load study tracker**, add Economics
for 60 minutes on a date inside the shown week, choose **Show graph**, then remove
the entry. The graph edit must preserve the entered data. Simulate a real guest
transition, then return as owner: the private component disappears and reloads
from the same backend ID. This path still uses real authentication/presence.

For isolated visual verification without credentials, start the frontend in
development with that frontend flag and open `/dev/study-tracker`. This page
uses only synthetic fixture data and a fake transport, and is unavailable in a
production build. Its **Simulate guest / Return owner** controls exercise the
actual frontend request controller and the existing Canvas; they are not evidence
of live face detection or cloud integration. Reloading the page resets the fixture.

`frontend/tests/artifacts.responsive.cjs` drives this page using an externally
installed Playwright and Edge. It checks the complete add/graph/guest/reload/remove
sequence, overflow and touch sizes at 1366×768, 1440×900, 1920×1080, 320×568,
375×667, 390×844 and 430×932. Playwright is not a product dependency.

## Validation and remaining work

Focused tests cover session substitution, presence failure/expiry, revocation
before commit and delivery, malformed stored artifacts, foreign ownership,
concurrent revisions, bounded operations, fixture parity, literal labels,
mount/unmount behavior and stale results. Run backend pytest normally and with
`-W error::RuntimeWarning -W error::pytest.PytestUnraisableExceptionWarning`, then
frontend `npm test -- --runInBand`, `npx tsc --noEmit`, and `npm run build`.

Two pre-existing FastAPI startup deprecations were removed by converting the
touched app initialization to lifespan handling without changing startup work.
The remaining Starlette test-client warning comes from its deprecated httpx
integration. It remains visible; a dependency migration is outside this task.

Verification on 2026-09-20:

| Check | Result |
| --- | --- |
| Full backend suite, normal | 276 passed; one existing Starlette deprecation |
| Full backend suite, RuntimeWarning and unraisable warnings treated as errors | 276 passed; same deprecation |
| Frontend Jest suites | 29 passed (22 artifact tests plus 7 existing turn tests) |
| TypeScript without emit | Passed |
| Production Next.js build | Passed with system TLS certificates and font-download network access |
| Changed Python compilation | Passed |
| Browser acceptance | All seven required sizes passed add/graph/guest/reload/remove, overflow and 44px control checks |

Desktop and 320px screenshots were inspected. Browser checks used the synthetic
fixture harness, not live Firebase or face detection; the restricted development
server used fallback fonts when Google Fonts could not be fetched. The production
build fetched the existing fonts successfully. Browserslist reports old browser
data; no dependency upgrades or warning suppression were introduced.

The next implementation step is a UID-scoped durable Firestore repository with
transactional spec/state CAS, deletion semantics and emulator tests. After that,
connect the small validated output planner to this trusted path. Authentication
still uses the existing local SessionManager: an unknown session after a worker
restart fails closed and requires starting a fresh session. Multi-worker session
recovery and durable tracker history are not implemented here.
