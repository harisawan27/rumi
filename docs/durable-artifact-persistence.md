# Durable generated-artifact persistence

This milestone extends the trusted `study_tracker_v1` path from commit
`7a4d975184b4f70fdf8eb095f9a34d9e22d31bad`. It does not connect a model planner.

## Storage and repository

`users/{authenticated_uid}/artifacts/{server_generated_uuid}` contains the full
validated envelope: artifact_id, kind, renderer, schema_version, revision,
state_revision, title, spec, state, source_session_id, created_at, updated_at,
validation_version and generation_version. No UID is accepted from a payload.
State is inline; this schema creates no artifact subcollections. Dates in study
entries remain ISO dates; created_at/updated_at are native Firestore timestamps.

`backend/src/artifacts/firestore_repository.py` provides create, get, list,
update_state, update_spec, delete and clear. Every returned stored artifact is
validated with the existing contract, including document-ID/envelope agreement.
Invalid IDs cannot select a Firestore path. Foreign and absent IDs both return
404. Malformed documents return 422 and remain explicitly deletable. Storage
exceptions become a generic 503; there is no memory fallback.

Creation reads for existence inside a transaction, uses `create`, and writes
server timestamps. State/spec mutations read authoritative storage inside a
Firestore transaction, compare the appropriate expected revision, apply only a
typed deterministic operation, and write atomically. State changes advance only
state_revision. Spec changes advance only revision and preserve entries. Spec
no-ops preserve the artifact, including timestamps. Responses normalize committed
server timestamps from Firestore write results. Existing contract fixtures stay
unchanged. Concurrent workers rely on Firestore retries/CAS, not a local lock.

## Authorization and leases

The API authenticates, checks session ownership and fresh owner presence before
storage access, then checks again before delivery. For writes, an async guard is
bridged from the transaction worker thread to the request event loop and rerun
on every transaction attempt, after reads/transforms and immediately before the
SDK commits. Cancellation/revocation observed at that check prevents the commit.

Presence and artifact storage do **not** share an atomic transaction. Revocation
after the final check can race with commit; a post-commit guard withholds private
delivery but cannot undo a successful write. A lost response can therefore mean
the write committed: reload before retrying. SessionManager authorization remains
process-local; deployment must still route requests to the worker with the live
session. Artifact CAS itself works across workers/clients.

`GET /generated-artifacts/access` refreshes the short authorization lease without
reading any artifact. The frontend polls that endpoint every two seconds while
a tracker is loaded. Content is read on explicit selection/reload or recovery
after lease expiry. Guest/away/hidden teardown, request ID, selected artifact ID,
and monotonic revision checks remain. Changes made elsewhere become visible on
reload or conflict recovery, not via live content subscriptions.

## Listing, history and deletion

`GET /generated-artifacts?session_id=...&cursor=...` returns at most 20 metadata
items and next_cursor, ordered by document ID. Metadata is artifact_id, title,
renderer, updated_at, revision and state_revision. The query reads at most 21
documents; it is not a chronological or snapshot-isolated listing.

Creation atomically writes `canvas_history/artifact_<uuid>` with only kind
`generated_ui`, artifact_id, title and timestamp. History loading strips any
unexpected state/content. Opening a reference performs an authorized artifact
fetch before the trusted renderer can mount. Deleted/invalid references render
as unavailable. Legacy Markdown history remains separate. The existing 20-item
navigation load/trim never deletes an artifact. There is no destructive artifact
retention cap. Older artifacts remain discoverable through the paginated API;
a complete library UI is a later feature.

`DELETE /generated-artifacts/{id}` transactionally removes the artifact and its
canonical history reference. All private tracker data is inline, so there is no
nested state to orphan. Noncanonical user-created references can remain harmless
unavailable references. The existing Clear Canvas data endpoint first clears all
artifacts, then deletes Canvas history, preserving its previous user-visible
meaning.

Clear uses pages of 100 artifacts (two deletes each), with fresh authorization
for each transaction. `users/{uid}/artifact_control/state` stores a clearing token.
Every artifact write reads that document transactionally. While clearing, writes
are rejected, preventing concurrent creation from escaping the scan. A failed or
revoked clear can be partial and leaves writes blocked; an authorized retry takes
over the token and completes cleanup. Success resets the token to null. The small
control document contains no tracker content. Clear across multiple pages and
the legacy-history deletion is not globally atomic; clients must not report
completion if any stage fails. No arbitrary future subcollections are recursively
deleted by this implementation.

## Rules, modes and indexes

Firestore rules explicitly deny browser reads/writes for artifacts and
artifact_control. Admin/server access still requires the API's authorization.
Existing owner-accessible Canvas reference rules do not grant artifact access;
references are untrusted navigation input. Listing uses the built-in document ID
index; no composite index was added.

* Production: `RUMI_ARTIFACTS_ENABLED=1` enables durable APIs using the existing
  configured Firestore client. `RUMI_ARTIFACT_PROOF_MODE=1` separately enables the
  explicit server-owned fixture creation route, and should normally be off.
* Development: the same durable repository; no flag selects in-memory storage.
  With FIRESTORE_EMULATOR_HOST set, the repository requires the exact fake project
  and localhost and creates an anonymous emulator client. Other application
  services retain their existing Firebase setup.
* Ordinary tests: injected memory/fake repositories; unchanged
  `backend/tests/conftest.py` blocks Admin initialization, sync and async clients,
  and the database alias, even with credentials or emulator variables set.
* Emulator tests: separate opt-in suite and anonymous localhost client; no Admin
  initialization, ADC, production project, remote host or async-client fallback.
* `/dev/study-tracker`: synthetic frontend transport only, still unavailable in
  production. No Gemini/Morph planner, generated JSX, React, or new database.

There is no migration from the old process-local proof data; it was ephemeral.

## Running the isolated emulator suite

Install Firebase CLI and a compatible Java runtime (this run used Java 21).
From the repository root, in a dedicated terminal:

```powershell
firebase emulators:start --only firestore --project demo-rumi-artifacts --config firebase.artifacts-emulator.json
```

Wait for the ready message. In a second terminal:

```powershell
cd backend
$env:FIRESTORE_EMULATOR_HOST = '127.0.0.1:8085'
$env:GCLOUD_PROJECT = 'demo-rumi-artifacts'
$env:GOOGLE_CLOUD_PROJECT = 'demo-rumi-artifacts'
python run_artifact_emulator_tests.py -q
```

Do not supply credentials. The entrypoint rejects unsafe configuration before
collection; the suite also checks readiness and guards client construction.
Fixtures use random test UIDs and clean only those users' three collections.
Ordinary `python -m pytest tests/` remains fully offline. Strict regression uses
`python -m pytest tests/ -q -W error::RuntimeWarning -W error::pytest.PytestUnraisableExceptionWarning`.

The emulator suite covers ownership, duplicate create, server timestamps,
independent-client state/spec races, preservation/no-op, precommit revocation,
metadata pagination, history trimming, deletion and interrupted clear, malformed
storage, sanitized failures, client rules and a fresh backend subprocess reload.
The restart probe constructs a new SessionManager and serves an API read with
synthetic authenticated identity/presence; real Firestore storage is the emulator.
It does not claim to test real Firebase login, camera detection or a live model.

## Validation and next step

Final validation on Windows, Python 3.11.4, Node/Next.js 16.1.0:

| Suite/check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Ordinary backend (`pytest tests/ -q`) | 289 | 0 | 0 |
| Strict backend (RuntimeWarning/unraisable as errors) | 289 | 0 | 0 |
| Explicit localhost emulator suite | 16 | 0 | 0 |
| Frontend Jest (`npm test -- --runInBand`) | 32 | 0 | 0 |

`npx tsc --noEmit`, `npm run build`, compilation of changed Python files and
`git diff --check` passed. The build used
`NEXT_TURBOPACK_EXPERIMENTAL_USE_SYSTEM_TLS_CERTS=1` and succeeded on retry after
an external Google Fonts connection failure. The existing Browserslist stale
dataset notice remains. Each backend/emulator run reports the existing single
Starlette/httpx deprecation warning; no warning was suppressed. Earlier emulator
runs exposed an unavailable startup and a timestamp mismatch, both resolved;
the table reports the complete final runs.

Acceptance evidence: `test_api_proof_update_and_clear_canvas_data` creates through
the real API, adds Economics 60 minutes, enables the graph, launches a fresh
backend subprocess with a new SessionManager and verifies the complete persisted
envelope, then clears through `/canvas/history` and checks both collections are
empty. `test_two_clients_only_one_revision_wins[state/spec]` uses independent
Firestore clients and verifies exactly one success and one 409. These are
repeatable automated API acceptance checks, not a real-login/camera browser run.

## Adversarial review

| Question | Implementation/evidence |
| --- | --- |
| A loads B's artifact? | UID-derived collection; foreign/unknown 404 in emulator ownership and API tests. |
| Artifact ID controls a path? | UUID contract before document lookup; traversal rejected. |
| Client supplies UID? | API UID is exclusively an authentication dependency; extra envelope fields fail validation. |
| Two workers accept one expected revision? | Independent-client state/spec emulator races: one success, one 409. |
| Stale state overwrites newer data? | Transaction checks authoritative state_revision on every attempt. |
| Spec edit loses entries? | 60-minute/color/graph/no-op emulator preservation test. |
| Restart loses tracker? | Fresh process/client/SessionManager API reload equality test. |
| History trim deletes tracker? | Create 23, trim history to 20, reload all 23 in emulator. |
| Clear leaves tracker state? | Inline state and canonical references removed; paginated and actual API clear tested. Failures return errors, partial clear requires retry. |
| Normal pytest reaches production? | Unchanged precollection guard plus explicit credential and sync/async constructor tests. |
| Emulator falls through to production? | Localhost/fake-project checks, anonymous client only, blocked Admin/ADC path; unsafe configuration tests. |
| Invalid storage reaches renderer? | Full envelope/document-ID validation; four malformed emulator cases rejected. |
| Failure silently uses memory? | Durable repository raises generic 503; failure test proves original state unchanged. |
| Lease polling reads artifacts? | Storage-free access endpoint and frontend one-load/three-refresh test. |
| Morph database/runtime imported? | No planner/runtime/database dependency changes; Firestore only. |

Next: connect the Morph-inspired validated output planner to the existing typed
create/edit decisions, authorization, durable repository and trusted renderer.
The planner must never produce executable JSX or bypass contract validation.
