# Rumi Desktop — voice-first companion

This Windows app runs supported voice and typed commands without Gemini, Firebase,
a browser sign-in or a camera. Voice is optional and explicitly enabled. It uses
installed English Windows speech support and the Microsoft Edge WebView2
Runtime. This is an **unsigned portable development build**, not a signed public
installer. Do not bypass Windows security warnings to run it.

## Run the portable build

Extract the complete `RumiDesktop-Windows.zip` folder and open `RumiDesktop.exe`.
Keep `_internal` beside the executable. Run as a normal Windows user, not admin.
Choose a disposable local folder for first use, then review the native permission
dialog. Each grant lasts 15 minutes. Stop, detected screen lock, minimize and exit
revoke it. A one-second local watcher detects lock/expiry; every action also checks
the current unlocked desktop. Nothing automatically resumes after revocation.

Try:

- `Open Notepad` / `Open Explorer`
- `List files`
- `Create first-note.txt with content: Hello from Rumi.`
- `Read first-note.txt` / `Read that file`
- `Stop`

Only `.txt`, `.md`, `.csv` and `.json` files in that folder are supported. No
overwrites, recursive access, arbitrary shell commands or app executables are
accepted. App launch reports dispatch, not verified window focus. Inspect a file
or app before retrying any uncertain action. Closing the app ends local access.

This mode trusts the current unlocked Windows session plus explicit native consent.
It does not claim Google identity or face verification. The existing cloud helper
retains its separate protections. The renderer cannot supply a folder path; selection
and confirmation happen in native dialogs. Private results are cleared when the app
observes revocation; the screen-lock watcher and UI status updates are bounded polls.

Chrome/Gmail automation, Windows settings, shutdown, a global
system-wide Stop shortcut, tray/startup integration, signing and automatic updates
are not included in this increment. Ctrl+K and Ctrl+Shift+. work while the app is
focused. The existing `/desktop/` route remains a separately labelled simulation.

## Local voice and companion

After choosing a folder, click **Let's talk** to enable the default microphone.
Begin each request with **Rumi**, for example `Rumi open Notepad` or
`Rumi list files`. Windows recognizes and speaks locally; Rumi does not save audio,
send it to a service, or use browser speech recognition. English Windows speech
recognition and a local voice must be installed. If unavailable, use **Type**.

Spoken file creation shows the recognized request for review. Say `Rumi confirm`
within 30 seconds or click **Confirm creation**. Check spelling and content;
dictation can be wrong. `Rumi cancel` or `Rumi stop` disconnects local access.
`Rumi listen` interrupts a spoken reply; wait a moment before your next request.
Other actions are ignored during playback and its short echo guard. Voice pauses
after two quiet minutes; it never automatically re-arms. This is explicit local
listening, not a background system-wide wake word. Do not rely on speech alone for
Stop: the button, Escape and Ctrl+Shift+. also work while Rumi is focused.

The animated companion reflects listening, speaking, working and review states.
Workspace results use pages instead of scrolling; say `Rumi next page` or
`Rumi previous page`. Type remains available with
Ctrl+K. Reduce motion is supported, including the Windows accessibility preference.
Local greetings/help are predefined responses, not a general conversational model.
Existing cloud Reply/Canvas/Create features remain in the separate dashboard.

Live microphone, speaker echo, accent/noise and all-day use are release checks;
the synthetic diagnostic is not evidence that those checks passed. See
[phase evidence](https://github.com/harisawan27/rumi/blob/master/docs/rumi-voice-first-companion.md).

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
