# Rumi validated CREATE planner

Continuation of `d1ef08327362ecf642be7ffe39daab2934c2cfc4`. The existing trusted
renderer, Firestore repository, revision domains and private-artifact access
guard remain authoritative. This feature does not execute generated code.

## 1. Final routing architecture

Dashboard speech transcripts and typed requests both reach the existing
`user_text` WebSocket dispatcher. The output planner advises conversation,
Markdown artifact, or `study_tracker_v1` create/edit. `artifacts/service.py`
assembles validated server-owned envelopes and calls the existing repository.
Raw Gemini Live audio and proactive Watchman paths are unchanged.

## 2. Morph logic adapted

Adapted only explicit output modes, build/edit awareness, examples, active-tool
context and separation of planning from execution. The prior Morph source audit
is the conceptual reference. No Morph auth, runtime, templates, database, cache,
search, model constants or React generation were imported. Failed edits never
fall back to a fresh build.

## 3. Planner input and context

The projection contains at most 4,000 request characters, a Canvas-context
Boolean, authoritative current-week start, and (if selected and authorized)
renderer, title, revision, subject labels and graph visibility. It excludes
entries, artifact IDs, UID, provenance, identity/profile data, memory, images,
camera/screen frames and unrelated history. Context is loaded under the existing
owner/session/presence guard. Selection comes from the current frontend artifact,
not the newest history item or an array index.

## 4. Structured schema

The installed Google GenAI SDK 1.75.0 supports `response_json_schema`; the
planner uses it with JSON MIME type and validates again with Pydantic. See
[Google's structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output).
Provider output is a closed typed projection: conversation, artifact title,
current-week tracker creation with subject labels/colors, or a color/graph edit.
The projection deliberately omits server-owned IDs, dates and revisions.
The host resolves it into the existing validated `OutputDecision` union before
anything can execute. Unknown fields, renderers, operations, URLs/capabilities,
state or ownership fields are rejected. Labels are escaped text, never executable
HTML/CSS/JavaScript. Only a bounded `AddSubject` edit was added to the trusted
manual spec endpoint; the model's edit capability remains color/graph only.

## 5. Precedence and configuration

1. Existing authentication/session handling and interruption.
2. Existing face queries with image context.
3. Existing profile/person operations.
4. Explicit image attachments and legacy Canvas follow-ups retain their route.
5. Explicit Canvas requests bypass planning and use Markdown.
6. Relevant creation/edit or substantial written-response candidates use the
   planner; greetings, ordinary questions and simple explanations bypass it.
7. Other requests retain the existing Gemini Live conversation path.

Enable `RUMI_CREATE_PLANNER_ENABLED=1` **and** `RUMI_ARTIFACTS_ENABLED=1` before
starting the backend. If either is off, the previous routing remains active.
The planner cannot create while durable artifacts are disabled. The explicit
proof route still separately uses `RUMI_ARTIFACT_PROOF_MODE`; it is not needed
for natural-language CREATE. No additional frontend rollout flag is required.
`RUMI_CREATE_PLANNER_MODEL` optionally overrides the existing first Flash model;
otherwise the planner uses Rumi's existing `_make_genai_client` and model boundary.
Client setup runs off the voice loop during enabled startup, connections are
reused within the event loop, and shutdown closes them. No model warm-up prompt
is sent. Restart after changing rollout/provider configuration.

## 6. Creation and subjects

“I need to track how much I study this week” creates an empty tracker with no
invented subjects or entries. Empty subject arrays are now valid in v1; old
artifacts remain valid. The trusted UI can add up to 20 subjects using typed
`AddSubject`, a stable ID, bounded label and allowed color token. The server
rejects duplicate IDs and normalized duplicate labels. Adding subjects advances
spec revision and preserves entries/state_revision. Subject removal is not
exposed, so existing entries cannot disappear through deletion of a subject.

Only subject labels explicitly present in the request may initialize a tracker.
Server-generated artifact/initial subject IDs and an empty state are assembled
after planning. “Current week” is Monday through Sunday in the timezone loaded
from the user's saved identity when the session starts; invalid/missing timezone
falls back to UTC. The model cannot invent dates. Other weeks/ranges are not
supported yet and must not be represented as a current-week tracker.

## 7. Targeted edits

The server fetches the selected artifact and freezes its authoritative revision
for planning. It resolves a typed edit and uses Firestore CAS with that revision.
Color/graph edits keep artifact ID, entries and state_revision. A concurrent
spec change returns conflict; the UI reloads authoritative content and asks the
user to repeat the change. No automatic rebase or overwrite occurs.

## 8. Subject resolution

Labels use Unicode NFKC normalization, case folding and collapsed whitespace.
Only exact, unique normalized matches are accepted; no substring/fuzzy matching.
Economics and Microeconomics therefore resolve distinctly. Two subjects whose
labels normalize to Economics are ambiguous and cannot be edited by that label.
The selected human label must also occur as a complete phrase in the request.
The server inserts the matching authoritative subject ID. Unknown or vague
targets produce clarification without mutation.

## 9. Failure and repair

Each provider attempt has a 12-second deadline. Invalid schema/capability output
may receive exactly one repair using only a safe validation summary, original
synthetic/request projection and allowed schema. Timeout/provider failure does
not trigger an additional paid retry. There are no regex JSON extraction or
unbounded repair loops. Failure leaves the last good artifact intact. Explicit
failed tool requests receive a short readable explanation; ordinary ambiguous
requests fall back to conversation. Storage failures never downgrade to memory.

## 10. Authorization and cancellation

Authorization occurs before context loading, after planning, before persistence,
on every repository transaction attempt, and before private delivery. A request
token and existing speak-task cancellation reject superseded work. Guest/away
transitions revoke frontend access and cancel pending presentation. New requests,
manual cancellation, navigation and dismissal invalidate the frontend request
gate; late results cannot open Canvas. Socket disconnect cancels planner work.

Presence and Firestore commit are separate authority domains. A cancellation or
revocation observed before the final check prevents persistence. A race after
the final check may leave a committed artifact/reference while withholding
delivery; reload/history can recover it later. This is not cross-store atomic
authorization and no rollback is claimed after successful persistence.

## 11. Progress, automatic open and voice

Real lifecycle events drive “Understanding request…”, “Creating tracker…”,
“Saving…”, “Updating tracker…”, “Writing on Canvas…” and “Ready”. No reasoning,
raw JSON, model identifiers or storage internals are displayed. Successful
socket results use the existing correlated `ArtifactResult` envelope. The
frontend verifies request/target, discards the socket payload after extracting
navigation metadata, then performs an authenticated leased artifact load before
mounting the trusted renderer. Only then does it select/add the history reference
and open existing desktop/mobile Canvas. The extra content read is an explicit
authorized load; two-second refresh still checks presence only.

Success uses the existing `voice_query` companion path for a brief acknowledgment,
without also sending the original request for a long explanation. Ordinary
conversation keeps its existing voice route. There is no new TTS implementation.

## 12. Mocked tests

Focused tests cover routing, structured validation/repair, missing/ambiguous
subjects, empty creation, wrong-target isolation, preserved entries, forbidden
capabilities, timezone boundaries, no build-on-edit-failure, guest changes and
cancellation. WebSocket integration checks progress, correlation, single
acknowledgement, flags and protected/ordinary/Markdown precedence. React tests
check empty tracker mounting, subject controls, stale responses and wrong targets.
Shared empty-tracker and AddSubject fixtures maintain backend/frontend parity.
The ordinary Firebase-blocking conftest remains unchanged.

## 13. Emulator acceptance

The separate localhost fake-project suite adds planner-directed empty creation,
manual subject/data entry, model-directed color/graph edits, durable history,
fresh-process/new-session reload and concurrent revision conflict without a new
build. Provider output is mocked here; persistence uses real Firestore Emulator
transactions. Existing isolation, rules, deletion and revision tests remain.
Startup commands are in [the persistence walkthrough](durable-artifact-persistence.md).
Final result: **19 passed**, including the new planner persistence and restart cases.

## 14. Live model evaluation

Run `python evaluate_create_planner.py --live` from backend. It uses 40 synthetic
prompts, the existing provider configuration, and blocks Firestore access. Of
the final 40 cases, 25 called the real configured `gemini-3.5-flash-lite` provider;
the remainder exercised deterministic routing. Final result: **40/40 correct,
zero schema-invalid outputs, zero repairs, zero inappropriate UI generations,
zero missed UI requests**. This bounded evaluation is not a general reliability
guarantee. [Final results](create-planner-evaluation.json) include every case.
Initial 36/40 and intermediate 37/40 runs are retained separately, including
timeouts, rather than hidden from the latency/accuracy record.

## 15. Latency

Final live planner decision latency (25 samples): p50 **976.456 ms**, p95
**1489.611 ms**. Provider setup before request handling: **158.558 ms**.
Ordinary deterministic routing overhead (13 samples): p50 **0.019 ms**, p95
**1.579 ms**. These timings do not measure Gemini Live speech onset or camera
verification. Emulator persistence (20 samples each): create p50 **18.816 ms**,
p95 **25.786 ms**; load p50 **5.474 ms**, p95 **7.123 ms**.
The local browser harness measured submit through authorized-client load and
history refresh: cold create **17077 ms**, color edit **1364 ms**, graph edit
**1580 ms**. Three heterogeneous samples do not justify a p95 or a production
interactive-Canvas latency claim. Browser latency is not inferred by adding p95s.

## 16. Regression results

* Ordinary backend: `python -m pytest tests/ -q` — **343 passed**.
* Strict backend: `python -m pytest tests/ -q -W error::RuntimeWarning -W error::pytest.PytestUnraisableExceptionWarning` — **343 passed**.
* Emulator: `python run_artifact_emulator_tests.py -q -s --tb=short` — **19 passed**.
* Frontend: `npm test -- --runInBand` — **35 passed**, two suites.
* TypeScript: `npx tsc --noEmit` — passed.
* Production build: `npm run build` — passed, including the local harness changes.
* Changed Python compilation: **13 files passed**.
* Repository whitespace check: `git diff --check` — passed.

The existing Starlette/httpx deprecation warning and stale Browserslist notice
remain visible. An initial unscoped `pytest -q` hit the emulator suite's intentional
opt-in guard; the ordinary suite was then run with the required `tests/` scope.

Local browser acceptance used the real configured planner, real emulator storage,
and the shared ArtifactCanvas/StudyTracker/ArtifactClient components. Verified:
empty creation; Economics added manually; 60 minutes saved; natural-language red
color edit; graph enabled; history reopen after page reload preserving both data
and edits; readable controls at a 390 × 844 viewport. This is a synthetic identity
test, not owner-authenticated dashboard, Google, camera, Watchman, Gemini Live audio,
or full dashboard mobile navigation acceptance. Those remain manual rollout checks;
existing regression suites and WebSocket dispatch tests provide narrower coverage.

To repeat without Google login, start the dedicated demo Firestore emulator, then
from backend set `FIRESTORE_EMULATOR_HOST=127.0.0.1:8085` and
`GCLOUD_PROJECT=demo-rumi-artifacts` and run
`python run_create_browser_acceptance.py --emulator-browser`.
Start the frontend development server with `NEXT_PUBLIC_ARTIFACT_PROOF_MODE=1`
and visit `http://localhost:3000/dev/study-tracker?acceptance=1`.
The separate acceptance server binds only 127.0.0.1:8005, accepts only the local
frontend origin, and always uses one synthetic UID and anonymous emulator client.
It does not expose production session/auth routes or retrieve Google credentials.
The development page is unavailable in production. Its acknowledgements are text;
it does not simulate voice or Markdown delivery. Stop the test server when finished.

## 17. Remaining limits

Only study_tracker_v1, the current seven-day week, explicit subjects, subject
addition and color/graph edits are supported. No subject removal, arbitrary date
ranges, timer, integrations, generalized apps or generated executable code.
Existing SessionManager routing still needs the worker holding the active
session. Concurrent remote edits become visible on explicit reload/conflict, not
a subscription. Exact subject matching may require clarification. Model routing
can still be wrong outside the bounded evaluation; rollout defaults off.

## 18. Recommended next step

Complete the owner-authenticated desktop/mobile acceptance scenario, then enable
the flag for a controlled user trial and monitor safe mode/failure/latency metrics.
Expand the evaluation with real phrasing (redacted and authorized) before adding
more trusted capabilities. General generated applications require a separate
isolation design; this milestone does not provide it.
