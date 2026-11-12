# Windows executor: first implementation increment

Date: 2026-11-11. This is the first increment of the
[three-day plan](rumi-jarvis-research-and-three-day-plan.md), not a public release.
Morph template migration remains deferred. Desktop actions are disabled by default
on both the backend and dashboard.

## Implemented

- Explicit local pairing with the existing authenticated Rumi owner session.
  The code expires after five minutes and allows at most five attempts. A successful
  pairing binds the process to that owner; its device secret stays in browser memory.
- A separate Windows process listening only on `127.0.0.1:8765`. It accepts one
  configured browser origin, checks Host and peer address, and rejects oversized bodies.
  The cloud backend authorizes operations; it never executes on its own filesystem.
- Manual dashboard controls to list/read/create text files in one explicitly chosen
  folder and request launching Notepad or Explorer. Files are flat, UTF-8, and use
  `.txt`, `.md`, `.csv`, or `.json`. Existing files are never overwritten.
- File reads are limited to 64,000 bytes; creates to 16,000 characters and 64,000
  UTF-8 bytes. Listing checks at most 500 directory entries. Traversal, device names,
  alternate data streams, junctions, symbolic links and hard-linked files are rejected.
- Windows directory handles prevent ancestor replacement during file operations.
  Created bytes and file identity are checked before reporting success. This is not
  isolation from malicious processes running as the same Windows user.
- Serialized execution with durable SQLite receipts. Expired requests and changed
  arguments for an existing request ID are rejected. Receipts are scoped to the
  selected folder. An interrupted write is uncertain and is not automatically retried.
  File contents, filenames, Firebase tokens and pairing secrets are not journaled.
- Fresh backend authorization before actions and before delivering results. Lost
  owner presence, guest mode, OS lock and Stop prevent subsequent actions. Browser
  privacy transitions clear private state and attempt to stop the local process.
- Stop is independent of the model; restart and re-pair are required afterwards.
  It cannot undo a write or app launch already committed. An app result reports
  **dispatched**, not a verified or focused window.

## Local operator setup

Use the repository's existing Python dependencies and normal backend/frontend setup.
Run the local agent as the signed-in Windows user, without administrator privileges.
Choose a new disposable folder for acceptance testing, not a folder of valuable files.

1. Set `RUMI_DESKTOP_ENABLED=1` in the backend environment and restart the backend.
2. Set `NEXT_PUBLIC_RUMI_DESKTOP_ENABLED=1` in `frontend/.env.local`. Restart the
   development frontend or rebuild the production frontend: this flag is compiled in.
3. From `backend`, run the following, substituting your existing test folder:

   ```powershell
   python run_desktop_agent.py --workspace "C:\Users\YOUR_USER\Documents\RumiTest" --backend http://localhost:8000 --origin http://localhost:3000
   ```

4. Sign in to Rumi normally, start the session and pass the existing owner-presence
   check. Open **Computer** and enter the code displayed in the local terminal.
   Never share that code. No database credentials or authentication bypass is used.
5. Create `acceptance-note.txt`, read it back and list the folder. Request Notepad
   and check the actual window yourself. Try creating the same filename again;
   the original contents must remain unchanged.
6. Select **Stop and disconnect**. Restart the local process before reconnecting.
   `Ctrl+C` in its terminal also stops it. A failed network stop does not replace
   stopping the local process; requests still require fresh owner authorization.

Only local HTTP origins or HTTPS endpoints are accepted by the launcher. Hosted
HTTPS-to-loopback behavior and browser local-network permissions still need real
browser validation; automated HTTP tests do not establish deployment compatibility.

Receipts live in `%LOCALAPPDATA%\Rumi\desktop\receipts.sqlite3`. Keep this database
when restarting so duplicate suppression remains intact. Never automatically replay
an uncertain action. Inspect the selected folder or window before a new request.

## Test evidence and pending release gates

The test suite uses temporary folders, real Windows file handles and a native
junction fixture. It mocks owner authorization and application dispatch. The backend
authorization tests exercise the existing session/presence gate with fixture identity,
not a real Firebase login. Frontend tests use mocked HTTP responses.

Final automated results on Windows, 2026-11-11:

| Check | Result |
| --- | --- |
| Backend `python -m pytest tests/ -q -W error::RuntimeWarning -W error::pytest.PytestUnraisableExceptionWarning` | 418 passed |
| Isolated Firestore `run_artifact_emulator_tests.py -q -s --tb=short` | 19 passed |
| Competing-client state/spec checks after retry fix | Three consecutive runs, 2 passed each |
| Frontend `npm test -- --runInBand` | 44 passed |
| TypeScript `npx tsc --noEmit` | Passed |
| Production `npm run build` with desktop preview enabled | Passed |
| Read-only native unlocked-desktop gate | Accepted this unlocked Windows desktop |
| Git whitespace checks | Passed |

The emulator regression exposed repeated simultaneous aborted commits. Transaction
retries now wait a bounded random interval before acquiring new read locks, with
authorization checked before waiting and again before commit. The five-attempt
limit and exact one-winner/one-conflict assertions remain intact; unknown commit
outcomes do not gain an automatic retry. Unit tests also cover revocation on retry.
The emulator's transaction behavior differs from production, as documented by
[Firebase](https://firebase.google.com/docs/emulator-suite/connect_firestore#transactions).
These local tests are not a cloud-load benchmark.

Non-failing tooling notices remain: Starlette's httpx TestClient deprecation,
Google's future Python 3.11 support notice, and outdated Browserslist data.

Tests must be run with normal Windows user access: the restricted coding runner cannot acquire directory
handles on the user-profile ancestor and correctly fails closed. Do not remove the
directory locks to make that runner pass.

Pending before day-four users:

- Real signed-in owner acceptance, physical microphone and camera checks, and visible
  Notepad/Explorer outcomes. Existing CREATE acceptance remains pending where recorded.
- Typed/spoken natural-language desktop routing, interruption and single voice acknowledgement.
- Public browser research with supporting links and a verified saved result.
- App targeting/focus, guarded file organization and global stop shortcut.
- A user-friendly installer/startup experience and tested hosted-browser pairing.
- Network loss, sleep/wake and restart acceptance on the integrated candidate.
- An eight-hour measured mixed idle/active run, with CPU, memory and provider usage.

Passing this increment's automated checks does not satisfy those gates. Roll back
exposure by disabling both flags and stopping the local agent. The existing Rumi
session, CREATE renderer and artifact schema do not depend on the local process.
