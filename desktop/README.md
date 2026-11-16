# Rumi Desktop — voice-first companion

This Windows app runs supported voice and typed commands without Gemini, Firebase,
a browser sign-in or a camera. Voice is optional and explicitly enabled. It uses
installed English Windows speech support and the Microsoft Edge WebView2
Runtime. This is an **unsigned portable development build**, not a signed public
installer. Do not bypass Windows security warnings to run it.

## Run the portable build

Extract the complete `RumiDesktop-Windows.zip` folder and open `RumiDesktop.exe`.
Keep `_internal` beside the executable. Run as a normal Windows user, not admin.
Choose a disposable local folder for file work, or use **Enable Windows control**
in the header for app control. Review the native permission dialog. Each grant
lasts up to 15 minutes. Stop, detected screen lock, minimize and exit
revoke it. A local watcher detects lock and expiry. Every action also checks
the current unlocked desktop. Nothing automatically resumes after revocation.

Try:

- `Open Notepad` / `Open Explorer`
- `List files`
- `Create first-note.txt with content: Hello from Rumi.`
- `Read first-note.txt` / `Read that file`
- `Stop`

General file commands support `.txt`, `.md`, `.csv` and `.json` in that folder.
The résumé workflow creates a Word file in one new subfolder. File creation uses
exclusive writes, and app launch uses the system Notepad or Explorer executable.
Inspect a file
or app before retrying any uncertain action. Closing the app ends local access.

This mode trusts the current unlocked Windows session plus explicit native consent.
It does not claim Google identity or face verification. The existing cloud helper
retains its separate protections. The renderer cannot supply a folder path; selection
and confirmation happen in native dialogs. Private results are cleared when the app
observes revocation; the screen-lock watcher and UI status updates are bounded polls.

Ctrl+K and Ctrl+Shift+. work while Rumi is focused. The existing `/desktop/` route
remains a separately labelled simulation.

## Local voice and companion

After choosing a folder or enabling Windows control, click **Let's talk** to enable the default microphone.
Begin each request with **Rumi**, for example `Rumi open Notepad` or
`Rumi list files`. Windows recognizes and speaks locally; Rumi does not save audio,
send it to a service, or use browser speech recognition. English Windows speech
recognition and a local voice must be installed. If unavailable, use **Type**.

Spoken file creation shows the recognized request for review. Say `Rumi confirm`
within 30 seconds or click **Confirm creation**. Check spelling and content;
dictation can be wrong. `Rumi cancel` or `Rumi stop` disconnects local access.
`Rumi listen` interrupts a spoken reply; wait a moment before your next request.
Other actions are ignored during playback and its short echo guard. Foreground
voice pauses after two quiet minutes. The Stop button, Escape and Ctrl+Shift+.
also work while Rumi is focused.

### Background wake

Enable **Background wake** in the header and accept the Windows prompt. Rumi keeps
local speech recognition running while minimized and the Windows session is
unlocked. In the portable build, the same setting launches Rumi minimized when
you sign in. Keep that copy in the same location, and turn the setting off before
moving or replacing it with a copy at a different path.

Say **Hey Rumi** followed by the request in the same breath. Rumi can restore the
window and show the words it heard. When file and app access has ended, approve a
workspace or enable Windows control and select **Use heard request** within 90
seconds. **Stop & disconnect** and **Pause microphone** end capture for this run.
Turn **Background wake** off to remove sign-in startup. Detected screen lock
pauses capture. With background wake armed, unlocking restarts listening without
renewing file or app permissions.

### Draft and save a résumé

1. Choose a workspace folder on `F:` and say `Hey Rumi, make a new folder in F
   drive and make a resume for me in it`. For any chosen drive, `Rumi, make a
   resume` uses your current workspace.
2. Give your name with `Rumi, resume name Jane Doe` and your experience,
   education and skills with `Rumi, resume details …`. Say `Rumi, resume folder
   named Job applications` to choose a folder name. The default is `Resume`.
3. Check the exact path and draft. Say `Rumi, confirm resume save` or select
   **Save Word file**. Rumi creates the new subfolder, writes `Resume.docx`, and
   checks the bytes before reporting success. An existing folder is left intact.

Local drafting uses the supplied facts. To enable optional Gemini polishing,
start the desktop app with `RUMI_GEMINI_RESUME_ENABLED=1`, set
`RUMI_GEMINI_RESUME_MODEL` to a supported Gemini model ID, and supply
`GEMINI_API_KEY` to the app process. **Polish with Gemini** shows the text to share.
**Send text to Gemini** sends that draft to Google. Review the rewrite and approve
the Word save separately.

The animated companion reflects listening, speaking, working and review states.
Workspace results use pages instead of scrolling; say `Rumi next page` or
`Rumi previous page`. Type remains available with
Ctrl+K. Reduce motion is supported, including the Windows accessibility preference.
Local greetings/help are predefined responses, not a general conversational model.
Existing cloud Reply/Canvas/Create features remain in the separate dashboard.

Click **Meet Rumi** (the sparkle in the header) to explore 17 character expressions.
This pauses voice and runs no computer commands. The activity icon cycles character
motion through **system**, **full**, and **reduced**. Choose full animation explicitly
if your Windows/browser setting reduces motion. The choice applies to this app
session. Idle Rumi blinks, breathes and follows the pointer gently; after 45 quiet
seconds it rests. Its small sparkle button says hello without enabling a microphone.
Real actions trigger reading, writing, file scanning and app-opening gestures;
success, clarification, errors and Stop have their own expressions. Speaking motion
follows native playback state; mouth shapes are stylized, not phoneme lip-sync.

Live microphone, speaker echo, accent/noise and all-day use are release checks;
the synthetic diagnostic is not evidence that those checks passed. See
[phase evidence](https://github.com/harisawan27/rumi/blob/master/docs/rumi-voice-first-companion.md).

## Control an app by voice

1. Enable Windows control and turn on the microphone. Keep Rumi open while using
   the target app. You can also say `Rumi enable Windows control` with the microphone
   already on and then approve the Windows dialog.
2. Say `Rumi list windows`, then `Rumi focus window two` using the number Rumi reads
   out. If Windows refuses the focus request, bring the app to the front yourself.
3. Say `Rumi inspect window` to hear the names of controls Rumi can use. Say
   `Rumi read result page`, `Rumi next page` or `Rumi previous page` to review results.
4. Describe the steps by name. For example, if the app exposes **Show search** and
   **Search query**, say `Rumi control window click Show search then expect Search query
   then type hello into Search query`. A click needs an `expect` step that names a
   control that should appear. You can also `expand`, `select`, `check`, `uncheck`
   or `set Search query to hello`. `Set` and `type … into` replace the field's value.
5. Listen to the plan readback and check the target, labels and text. Say
   `Rumi confirm window plan` within a minute, or say `Rumi cancel window plan`.
   Rumi checks each step before continuing and reports how many it verified.
   `Rumi stop` revokes the session. An action already sent to the app can finish.

You can also start with the outcome you want:

- `Rumi find invoice in this document` checks for a match in readable text exposed by the foreground app.
- `Rumi search for meeting notes` locates a search field or opens a search control, then checks the entered query.
- `Rumi fill subject with Weekly review` finds the named editable field and checks its value.
- `Rumi switch to details view` finds a matching view or tab and verifies selection.

The workspace shows your goal, the target window and the proposed steps. If several
controls match, say `Rumi choose option two` or the number you want. Rumi still waits
for `Rumi confirm window plan` before making changes. If speech recognition got a word
wrong, cancel the plan and ask again. The planner runs on your device.

The operator uses the named controls exposed by Windows UI Automation in the
selected foreground window. It needs a unique match and a supported control
pattern. Inaccessible controls, blocked focus changes and separate modal windows
can require direct interaction. Shell, credential and consequential controls are
outside this workflow. A plan is confined to one window. Software that uses
custom-drawn controls may expose little or nothing to the operator.

Run `desktop/.venv/Scripts/python desktop/check_windows_control.py` from the repository
root to verify a real three-step plan against a disposable WPF window. The check
uses generated audio and the local speech recognizer for the instructions. It opens
and closes only its own test window, verifies that a named button reveals a field,
checks the exact text in that field, and verifies the checkbox changes state.
Use `desktop/.venv/Scripts/python desktop/check_planner.py` to test natural goal
phrases against two disposable Windows layouts.

## Save the result of a task as a note

Choose the destination folder first. Enable Windows control as well for a document
search, then keep the document in front. Turn on voice and try either request:

- `Rumi find invoice in this document and save what you found as a note`
- `Rumi search for Windows accessibility shortcuts and save the first three links`

Rumi displays the exact draft. Say `Rumi confirm workflow save` within a minute,
or say `Rumi cancel workflow` to discard it. You can also use **Save note** and
**Discard note** in the workspace. Rumi reads the new file back before reporting
success. Add an explicit name, such as `as invoice-check.txt`, to choose a different
filename. Existing files stay untouched. The default names are
`document-search.txt` and `research-links.txt`.

Document search runs locally and records the match result and source window name.
Web research sends your stated query to DuckDuckGo and saves up to three distinct
HTTPS results in the returned order. Rumi shows which links it found and does not
open those links. If the provider returns no usable results, Rumi prepares no note.

`desktop/.venv/Scripts/python desktop/check_planner.py --note-workflow` verifies the
document-to-note path using generated speech and a disposable window and folder.
Use `--web-workflow` instead to run a live public search and verify the saved draft
in a disposable folder.

## Build from source

Use Python 3.11 on Windows and the existing frontend Node environment:

```powershell
python -m venv desktop/.venv
desktop/.venv/Scripts/python -m pip install -r desktop/requirements-lock.txt
./desktop/build.ps1
```

The build creates a portable folder and zip under `desktop/dist/`, with dependency
notices and this guide. `-SkipFrontend` packages an already verified frontend export.
Use an isolated environment: importing the cloud backend or bundling its ML models
is unnecessary for local commands. To run from source after a frontend build:

```powershell
desktop/.venv/Scripts/python desktop/main.py
```

Optional installed-engine diagnostic (temporary generated WAVs, no microphone or
speaker playback): `desktop/.venv/Scripts/python desktop/check_speech.py`.

Local receipts are stored at `%LOCALAPPDATA%/Rumi/desktop/native-receipts.sqlite3`.
They contain request fingerprints and coarse outcomes, not file contents. Preserve
them across restarts. Runtime grants, credentials and last-file references stay in
memory. The loopback listener serves only bundled UI assets; it has no command API.

Packaging references: [pywebview API](https://pywebview.flowrl.com/api/) and
[freezing guide](https://pywebview.flowrl.com/guide/freezing.html). The pinned bridge
is configured with explicit function exports and no `js_api` object; private Python
attributes are not treated as an authorization boundary.
