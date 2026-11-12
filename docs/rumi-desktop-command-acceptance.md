# Typed and spoken computer commands

Implementation date: 2026-11-12. Builds on the Windows helper in `159d12f`.
Both desktop feature flags remain disabled by default. This increment implements
command routing; it does not certify the day-four public release.

## User flow

Start and pair the local app as described in the [executor setup](rumi-desktop-executor.md).
Use Rumi's existing typed input or microphone, or the **Computer request** field.
Each request must name one supported operation:

| Request | Result |
| --- | --- |
| Open Notepad / Please launch File Explorer | Reports launch dispatch; does not claim window focus or readiness |
| List my files / Show me the text files | Lists supported text files from the chosen folder |
| Create a file called meeting-notes.txt with these notes: Call Alex tomorrow. | Creates a new file with the supplied text and verifies its bytes |
| Create meeting dash notes dot txt with these notes Call Alex tomorrow | Supports explicit spoken `dot txt` and `dash` filename spelling |
| Read meeting-notes.txt | Displays the UTF-8 contents in the private computer panel |
| Read that file / Read it | Uses only the last successfully created/read file in this paired session |
| Stop / Cancel / Please stop | Cancels local waiting, discards late results, requests helper Stop and disconnects |

Speech uses the existing browser speech recognizer. Its transcript is the request;
recognition accuracy on the user's microphone still requires physical testing.
The parser accepts polite prefixes and common terminal punctuation. It does not
infer arbitrary filenames, generate missing note contents, or perform multiple actions.
Unsupported requests and missing details produce a clarification. File content after
the delimiter is literal data, including text that resembles another command.

Rumi gives one short spoken status through its existing Gemini Live voice channel.
File reads display the contents; this phase does not read private file bodies aloud
or send them to the voice model. Only the request ID, session, expiry, operation and
coarse result state go to the authenticated voice route. The cloud speaks a client
receipt; it does not independently observe the Windows window.

## Execution and interruption

The local `/command` endpoint uses the same paired-device, real-owner, fresh-presence,
unlocked-desktop, deadline and closed action contracts as manual controls. It delegates
to the existing serialized executor and durable duplicate receipts. The backend
never executes against its own filesystem. A timeout is reported as uncertain,
with no automatic retry of a write or application launch.

Typed input and finalized speech both enter the dashboard's `sendToRumi` function.
Consumed computer commands are not also sent as conversational `user_text` or CREATE
requests. Ordinary conversation and study-tracker creation retain their existing path.
Canvas follow-ups without attachments can also invoke explicit computer requests;
attached material is not interpreted as local execution authority.

Stop is checked before the busy guard and does not wait for a Firebase token refresh.
The helper's Stop endpoint also remains available while another request waits for
authorization. It cannot undo an operation already committed. If the network stop
fails, the browser still disconnects and the UI does not claim confirmed rollback.
Restart and re-pair before further computer actions.

Old results and audio are discarded after Stop, guest transitions and session changes.
Voice acknowledgements carry the desktop request ID and existing audio generation ID.
Only matching, currently authorized audio is played. Recognition buffers are cleared
before desktop acknowledgement playback, and acknowledgement audio is suppressed while
the user is actively speaking. Receipt deduplication is bounded without evicting live
entries; a full voice-receipt budget rejects new acknowledgements until entries expire.
During a desktop acknowledgement, a separate recognition mode accepts only a finalized
Stop/Cancel utterance. It never forwards other speech as a new action or conversation.
Its microphone accuracy and echo behavior remain part of physical acceptance.

## Acceptance evidence

Automated verification on Windows, 2026-11-12:

| Check | Result |
| --- | --- |
| Backend suite with runtime/unawaited-coroutine warnings treated as errors | 462 passed |
| Isolated Firestore emulator regression suite | 19 passed |
| Frontend Jest suite | 71 passed |
| TypeScript `npx tsc --noEmit` | Passed |
| Production `npm run build` with desktop preview enabled | Passed |
| Git `diff --check` | Passed |

Automated coverage includes local parsing, real temporary file create/read/list,
literal command-looking contents, traversal/device-name rejection, missing references,
no overwrites, duplicate/reused IDs, busy execution, authorization loss, expired requests,
foreign origins, Stop during authorization, real WebSocket dispatch into the voice
callback, duplicate speech suppression, audio generation correlation, and frontend
typed/finalized-transcript routing with late-result suppression.

Application launch and Gemini speech are mocked in automated tests. These tests do
not establish that a real window opened or that physical microphone/speaker behavior
is correct. No authentication bypass or production database fixture is used.

Physical owner-session acceptance remains pending until observed:

1. Sign in normally, start a session, verify presence and pair a disposable folder.
2. Type the create request above; inspect the actual file and read it back.
3. Say the same operation with a new filename; verify one file and one acknowledgement.
4. Say **Read that file**; verify the selected file's contents appear.
5. Say **Open Notepad**; inspect the real window and truthful dispatch wording.
6. Start another request and press Stop; verify no late success speech or repeated write.
7. Switch session or lose owner presence; verify private results disappear and actions fail.
8. Check pauses, interruptions and speaker echo using the actual microphone.

Browser research, arbitrary app interaction/focus, file organization, a Windows
installer and the eight-hour measured reliability run remain later release gates.
