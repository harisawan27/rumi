# Voice-first Windows companion

Phase built on `9da2f5474c9f0e994cce2f06204654cfd362c80d`, November 2026.

## Scope

The native `/desktop-local/` surface now centers an original animated SVG robot
inside a fixed-height space. Listening, speaking, working, confirmation and success
have distinct expressions. A focused workspace opens for results; long text is
paged without discarding characters. Voice is the primary input, with typed input,
keyboard Stop, reduced motion and a visible microphone state always available.

This phase adds local English speech to the existing native action boundary. It
does not expand executable capabilities: Notepad/Explorer launch and bounded text
file list/read/create still use the same parser, executor, receipts and folder
grant. No shell, Chrome/Gmail, Windows settings or shutdown is exposed. Existing
cloud Reply/Canvas/Create and the simulated `/desktop/` remain separate routes.
There is no generative cloud UI or general offline conversational model in this
phase; local greetings and help are explicit predefined responses.

## Speech behavior

- The microphone starts only from **Let's talk**, after native folder permission.
- Windows `System.Speech` is loaded lazily from the installed .NET Framework.
  An installed English recognizer and voice are required; missing support leaves
  typing available. No new model download, browser speech fallback or cloud API.
- Common commands use an explicit grammar; addressed dictation supports other
  parser requests. Utterances must begin with Rumi (or accepted name spelling).
  Low-confidence requests ask for repetition. This is not speaker authentication.
- Requests enter the same serialized executor as typed input. Repeated event IDs,
  old sessions and late results cannot execute a second action or restore access.
- Spoken create requests display the recognized words and wait up to 30 seconds
  for confirmation. Dictation text is not rewritten or treated as code. The existing
  no-overwrite rule remains mandatory. Typed creation retains its existing flow.
- `Rumi stop` revokes the grant from the native callback without waiting for the
  renderer. `Rumi listen` cancels playback; wait one second before speaking again.
  Other speech that begins during playback or its guard interval is discarded,
  including a recognition result delivered after playback has finished. This is
  an echo guard, not acoustic echo cancellation or unrestricted natural barge-in.
- `Rumi next page`, `Rumi previous page`, `Rumi show workspace` and
  `Rumi show companion` navigate the interface without executing a native action.
- Voice pauses after two minutes without an addressed utterance/reply; Stop,
  minimize, hidden UI, detected lock, grant expiry and exit revoke listening. No
  automatic re-arm. Stop invalidates callbacks immediately; hardware disposal runs
  on a separate thread so a slow Windows device cannot block permission revocation.
  Hardware release latency still requires live device acceptance.
- Audio is never saved or sent by Rumi. Transcripts/events are bounded in memory;
  overflow pauses voice. Typed/recognized file contents are written only through
  an authorized explicit create action. Receipts retain the existing coarse data.

The bridge exports eight closures, with no `js_api` object or HTTP command endpoint.
Speech responses require the current grant and voice generation. The native asset
server's closed network policy remains unchanged. No Gemini calls were made during
this work.

## Validation

Automated checks and observed UI results are recorded below; pending checks are
not represented as passed.

- Native regression suite: 26 passing tests, including Stop during engine creation
  and microphone startup, late callback rejection, playback-tail suppression,
  lock/quiet expiry, queue bounds and no automatic microphone restart.
- Installed-engine diagnostic: synthetic WAV input/output, no microphone capture
  or speaker playback. `Rumi stop`, `Rumi open Notepad`, `Rumi list files` recognized
  exactly at confidence 0.979, 0.978 and 0.986. General dictation initially misheard
  the name, motivating the explicit vocabulary. Confidence is not an accuracy rate.
- Frontend: 95 tests passed across seven suites. Tests include explicit voice
  start, delayed startup/poll after Stop, duplicate transcripts, confirmation and
  expiry, microphone failure, literal text pagination and voice page navigation.
- Backend: 462 offline tests passed with runtime/unraisable warnings treated as
  errors; the existing Starlette/httpx deprecation warning remains.
- Production Next.js build passed for all existing routes. Browserslist reports
  that its bundled browser data is old; it does not block compilation.
- Standalone TypeScript check passed. Windows PyInstaller portable package built;
  packaged executable opened and exposed the native connection, companion screen,
  explicit folder control and MIC OFF state. No grant or microphone was enabled
  by the agent. Physical voice acceptance was requested from the user.
- Browser inspection at 1280x720, 700x560 and 700x520: companion/workspace,
  typing expansion, result pagination and reduced motion verified. Found and fixed
  focus-induced internal scrolling; header remains at y=0 and footer at the
  viewport bottom with typing open. Native actions are disabled in browser preview.

Reproduce using `python -m unittest discover -s desktop/tests -v`,
`desktop/.venv/Scripts/python desktop/check_speech.py`, frontend `npm test --
--runInBand`, `npx tsc --noEmit`, `npm run build`, and `git diff --check`.
Backend ordinary tests are offline and reject real Firestore access.

## Required live acceptance before public release

1. Open the packaged executable as a normal user and choose a disposable folder.
   Enable local voice yourself; confirm recognition and audible replies.
2. Say `Rumi open Notepad`, `Rumi list files`, and
   `Rumi create voice-check dot txt with content hello from Rumi`. Review the
   recognized filename/content before confirming. Read it back and test collision.
3. Verify no action from unaddressed speech, playback or background conversations.
   Repeat with speakers/headphones, your accent and realistic room noise.
4. Interrupt playback with `Rumi listen`; test spoken Stop, keyboard Stop,
   pause/re-arm, minimize, screen lock, microphone unplug and quiet expiry.
   Check Windows microphone-use status after stopping.
5. Validate supported display scaling, clean-machine prerequisites, startup,
   recovery and an eight-hour resource/reliability run before release. Signing,
   installer, updater and broader Windows/browser actions remain separate work.

The prior typed native smoke test is documented in
[foundation evidence](rumi-native-desktop-foundation.md). It does not establish
that this phase's new live voice behavior has passed.

Implementation references: Microsoft [GrammarBuilder](https://learn.microsoft.com/en-us/dotnet/api/system.speech.recognition.grammarbuilder?view=netframework-4.8.1)
and [asynchronous recognition](https://learn.microsoft.com/en-us/dotnet/api/system.speech.recognition.speechrecognitionengine.recognizeasync?view=netframework-4.8.1).
