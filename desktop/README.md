# Rumi Desktop — local control foundation

This Windows app runs supported typed commands without Gemini, Firebase, a browser
sign-in, a camera or a microphone. It uses the installed Microsoft Edge WebView2
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

Microphone support, Chrome/Gmail automation, Windows settings, shutdown, a global
system-wide Stop shortcut, tray/startup integration, signing and automatic updates
are not included in this increment. Ctrl+K and Ctrl+Shift+. work while the app is
focused. The existing `/desktop/` route remains a separately labelled simulation.

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

Local receipts are stored at `%LOCALAPPDATA%/Rumi/desktop/native-receipts.sqlite3`.
They contain request fingerprints and coarse outcomes, not file contents. Preserve
them across restarts. Runtime grants, credentials and last-file references stay in
memory. The loopback listener serves only bundled UI assets; it has no command API.

Packaging references: [pywebview API](https://pywebview.flowrl.com/api/) and
[freezing guide](https://pywebview.flowrl.com/guide/freezing.html). The pinned bridge
is configured with explicit function exports and no `js_api` object; private Python
attributes are not treated as an authorization boundary.
