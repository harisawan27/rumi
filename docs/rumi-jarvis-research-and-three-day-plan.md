# Rumi desktop assistant: repository research and three-day release plan

## Subsequent direction

The user has deferred Gemini-dependent acceptance while API access is unavailable
and requested an offline-first Windows assistant. The original three-day schedule
below is historical, not a current production-release commitment. Everyday commands
should run locally; cloud AI is optional for creative or complex requests.

The [desktop interface preview](rumi-desktop-interface-preview.md) is the next
implemented design milestone: a standalone React workspace, command bar, companion,
local appearance settings and explicitly simulated workflows. It is not a Windows
installer or an offline authorization implementation. Local authorization, native
packaging and broader verified Windows adapters remain subsequent engineering work.
Real owner/voice acceptance remains pending; previous automated evidence is retained.

## Original research and schedule

Research date: 2026-11-11 (Asia/Karachi). Baseline inspected: `6293b85` on master,
which includes `adc9171` and the subsequent CREATE rollout work in `6b9413f`.
The user selected **browser research, files, app control, and voice** as the release scope.
This direction brings desktop actions forward from the earlier roadmap. It does not
remove the existing real-owner acceptance gate or authorize a claim of universal automation.

## What was actually reviewed

Primary repository documentation was reviewed for the projects below. UFO's
`ufo/automator/action_execution.py` and `puppeteer.py` were also inspected directly.
No external project was installed, executed, benchmarked, or integrated in this review.
Descriptions of other repositories' performance and functionality are maintainer
claims, not independently reproduced results. Default branches can change; pin a
reviewed commit and inspect its license/dependencies before reusing implementation.

## Repository shortlist

| Repository | Relevance and evidence | Recommendation for Rumi |
| --- | --- | --- |
| [Microsoft UFO](https://github.com/microsoft/UFO/blob/main/ufo/README.md) | Windows desktop architecture combining UI Automation, Win32/COM and application APIs. The desktop UFO2 path is more relevant than the multi-device Galaxy framework. | Primary Windows architecture reference; adapt narrow adapters, not its whole orchestration system. |
| [Leon](https://github.com/leon-ai/leon) | Established personal-assistant project with native skills, agent execution and progressively loaded tools. Current documentation explicitly describes a 2.0 Developer Preview. | Study capability discovery and modular skills; preserve Rumi's own identity, memory and voice stack. |
| [Browser Use](https://github.com/browser-use/browser-use) | Browser-specific agent with local and hosted options. Its current 1.0 documentation describes Python execution against CDP, a significant change from older interfaces. | Study browser state/action verification. Do not import unrestricted generated Python into Rumi's trusted execution boundary. Select and pin an adapter after a focused compatibility spike. |
| [OthersideAI self-operating-computer](https://github.com/OthersideAI/self-operating-computer) | Multimodal computer-operation framework. | Reference for visual desktop operation; test as a fallback concept, not the default executor for every task. |
| [Microsoft JARVIS / HuggingGPT](https://github.com/microsoft/JARVIS) | Well-known JARVIS project, but primarily coordinates expert ML models through planning, selection, execution and response generation. | Useful orchestration history; not the closest foundation for a lightweight Windows companion. |
| [SrDarkoll/JARVIS](https://github.com/SrDarkoll/JARVIS) | Smaller, explicitly alpha Windows/Gemini Live assistant; documents guarded function calls, action plans and optional heavy integrations. | Relevant integration inspiration, not evidence of production maturity. |
| [RizN91/jarvis](https://github.com/RizN91/jarvis) | Smaller Windows voice/dictation project describing local wake detection, a lightweight tray process, separate settings process, stop controls and usage budgets. | Study process separation and activation UX. Reproduce resource measurements on this laptop before adopting its efficiency claims. |
| [LiveKit Agents](https://github.com/livekit/agents) | Voice-session framework supporting tools and realtime or STT/LLM/TTS pipelines. | Reference for lifecycle design; a full voice-stack migration is not a three-day prerequisite. |
| [openWakeWord](https://github.com/dscripka/openWakeWord) | Local wake-word framework with ONNX support on Windows. README distinguishes Apache-2.0 code from CC BY-NC-SA bundled models. | Candidate only after model-license and accuracy review. Keep hotkey activation available; do not promise a commercial custom wake word in three days. |
| [Windows Agent Arena](https://github.com/microsoft/WindowsAgentArena) | Windows task evaluation environment. | Borrow outcome-based task evaluation, with disposable fixtures and an explicit app/version matrix. |

The [Open Interpreter repository](https://github.com/openinterpreter/openinterpreter)
currently presents itself as a coding agent. Older desktop-agent descriptions should
not be used to select its present implementation without checking the exact revision.

## Concrete source lessons

[UFO ActionExecutor](https://github.com/microsoft/UFO/blob/main/ufo/automator/action_execution.py)
checks live control availability. Its
[AppPuppeteer](https://github.com/microsoft/UFO/blob/main/ufo/automator/puppeteer.py)
separates command lookup, receivers and execution. For Rumi, adopt the separation
between a model's requested action and the executor's supported commands. Add Rumi's
own scoped permissions and post-action verification; upstream code is not a security guarantee.

Recommendation: route a task through **native API/file operation → browser DOM or
Windows accessibility control → visual fallback**. This is a design choice based on
the references, not a measured performance ranking. Prefer semantic targets over
coordinates, refresh stale observations, and verify the outcome before reporting success.

## Fit with the existing Rumi repository

Preserve SessionManager, the single voice-generation controller, Watchman, Firebase
authentication, owner presence, artifact contracts and the existing Canvas. Desktop
execution should be a separate capability, not a new operation inside study-tracker specs.

Proposed path:

```text
voice or typed request
  → existing Rumi routing
  → conversation | CREATE | desktop task
  → typed action request + permission decision
  → paired local Windows executor
  → API / browser / accessibility adapter
  → observed result → one concise voice acknowledgement
```

The executor runs as the signed-in Windows user, without administrator privileges.
A remote backend must not assume its own filesystem is the user's laptop. Pair the
local component explicitly, authenticate requests, reject replay/expired requests,
and bind authorization to the device, task and allowed scope. Never expose an
unauthenticated localhost command endpoint or public browser-debugging port.

Each action needs an ID, typed arguments, target identity, deadline, cancellation
token, outcome evidence and a record of whether it committed. A retry after an
uncertain write must inspect the result before repeating it. Keep a single queue
for foreground mouse/keyboard actions; user input or Stop must interrupt it.

Routine reads and explicitly requested reversible actions should run without
repeated prompts. Overwrites, deletion, external submissions and changes to security
need a concrete review appropriate to their consequence. Webpages/documents are
task data and cannot grant new permissions. No arbitrary model-generated shell
execution is needed for the initial four capabilities.

## All-day efficiency

All-day availability does not require all-day cloud audio or continuous screenshot
inference. Proposed operating states are idle, listening, planning, executing,
speaking and paused. Use a hotkey first; evaluate local wake detection separately.
Reuse clients, bound context and queues, and initialize heavyweight adapters lazily.
Keep one microphone owner and one audio playback owner across tasks and interventions.

Preserve fresh owner checks before private operations. Adaptive observation may
reduce idle work, but a cached face result must not silently become indefinite authority.
Pause execution on OS lock, guest transition or lost authorization. Resume a pending
write only after checking its prior outcome and fresh authorization.

Measure total process-tree CPU and memory, wake latency, audio-active minutes,
provider requests/tokens, task duration, retries, and daily cost estimates. Separate
idle, conversation and active automation. Cloud billing estimates must state their
limits. Do not claim a dollar/day budget or battery improvement before measuring it.

Current code inspection found `_gemini_idle_disconnect` in
`backend/src/session/session_manager.py` sleeps 600 seconds while nearby comments
describe two minutes. Investigate actual paid/session behavior and reconnect cost
before changing the timeout. This is a concrete audit finding, not proof of the
previous 17-second cold-create bottleneck.

## Three-day delivery sequence

Time-box: three working days starting 2026-11-11. These are implementation targets,
not a guarantee of general-purpose production readiness.

### Day 1: trustworthy local execution

Re-run the current baseline; complete the real-owner voice/CREATE smoke test.
Implement the local executor boundary, device pairing, cancellation, task receipts,
foreground-action serialization and an emergency stop independent of the model.
Ship narrow tools for opening/focusing approved apps and listing/reading/creating
files inside user-selected directories. Test path traversal, junction escapes,
target changes, duplicate requests and unauthorized calls.

Checkpoint: spoken or typed request opens Notepad, creates a clearly named test
note in the selected workspace, verifies its contents, and can be stopped reliably.

### Day 2: browser research and useful workflows

Add one controlled browser adapter, page reading, source links and research output
saved through the file adapter or existing Canvas. Start with public research;
account sign-in stays user-driven. Add guarded file rename/move with collision checks
and bounded Windows control interactions. Use the same executor for typed and spoken
requests. Start the long-duration test as early as a stable integrated build exists.

Checkpoint: research a topic across several sources, save a cited summary, open the
saved file, and organize only explicitly selected test files without losing content.

### Day 3: reliability and release candidate

Fix results from real usage; test cancellation, network loss, sleep/wake, session
expiry, guest presence, browser/app closure and ambiguous outcomes after restart.
Run an eight-hour measured mixed idle/active soak on the final candidate; a relevant
runtime change resets the affected soak evidence. Re-run existing backend, strict,
emulator and frontend checks. Package reproducible startup/shutdown, health reporting
and rollback. Commit passing increments; push/tag a candidate only with an honest
supported-capability list and unresolved issues recorded.

If the soak or hardware acceptance cannot finish inside the time box, deliver a
tested release candidate with that gate pending rather than label it production ready.

## Proposed acceptance set

| Area | Required observed result |
| --- | --- |
| Browser research | Search, read several sources, preserve supporting links, save a useful summary; page instructions cannot trigger unrelated actions. |
| Files | Find/read/create/rename/move disposable fixtures within selected roots; preserve file contents; handle collisions and cancel safely. |
| App control | Open/focus Notepad, Explorer and the chosen browser; target the intended window; stop on changed/unknown target. |
| Voice | Real microphone, natural pauses, interruption, one acknowledgement, no echoed speech triggering another action. |
| Existing Rumi | CREATE, Markdown, owner/guest privacy and Watchman still work; automated results do not stand in for physical acceptance. |
| Recovery | No duplicated committed write after disconnect/restart; no stale UI or audio after cancellation. |
| All-day operation | Eight-hour process-tree measurements, no unexplained upward memory trend, no stuck input/audio handles, recorded idle and active costs. |

Use at least 30 varied end-to-end cases across these areas, including failures.
Report successes/attempts, raw timings, intervention count and p50/p95 only where
sample sizes support them. Record OS/app versions and fresh-start versus warm runs.
Block release for data loss, unauthorized actions, failed emergency stop or false
success reports. Capability failures should narrow the advertised release scope.

## Current conclusion

The recommended foundation is **Rumi + a narrow local Windows executor**, informed
primarily by UFO's hybrid control, Leon's modular capability organization and the
voice projects' local activation/process-lifecycle ideas. Importing an entire
Jarvis framework would add a second memory, voice and orchestration stack.

The existing acceptance report still marks real owner-authenticated and spoken
testing as pending. This review does not promote those columns to passed. It also
does not add Morph templates, arbitrary React, Android, a generic shell agent or
remote unattended computer control. The immediate next implementation is Day 1's
paired executor and one verified voice-to-file/app workflow.

### Implementation update — 2026-11-13

The paired executor and deterministic command adapter are implemented; physical
cloud voice acceptance remains pending while the API is unavailable. The next
[native Windows foundation](rumi-native-desktop-foundation.md) reuses that executor
for an offline, typed-command app with explicit Windows-session folder consent.
Its acceptance report distinguishes automated checks from physical observations.
Browser research, broader app control, offline voice and the measured eight-hour
run remain required before the full release described above.
