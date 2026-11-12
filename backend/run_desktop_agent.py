"""Start Rumi's local Windows executor for an explicitly selected workspace."""
import argparse
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--origin", default="http://localhost:3000")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This local agent requires Windows")
    import ctypes
    if ctypes.windll.shell32.IsUserAnAdmin():
        parser.error("Run Rumi from a normal Windows terminal, without administrator privileges")
    for value in (args.backend, args.origin):
        url = urlsplit(value)
        if (url.scheme not in ("https", "http") or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")
                or (url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1"))):
            parser.error("Use an HTTPS origin or localhost HTTP URL")
    root = Path(args.workspace).absolute()
    data = Path(os.environ["LOCALAPPDATA"]) / "Rumi" / "desktop"
    data.mkdir(parents=True, exist_ok=True)
    # One process per local listener; durable receipt IDs survive restarts.
    code = secrets.token_urlsafe(24)
    def authorize(token, session_id):
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
            response = client.post(args.backend.rstrip("/") + "/desktop/authorize",
                headers={"Authorization": "Bearer " + token}, json={"session_id": session_id})
            response.raise_for_status()
            body = response.json()
            if body.get("session_id") != session_id:
                raise ValueError("Invalid authorization response")
            return body["uid"]
    from src.desktop.local_server import create_local_app
    app = create_local_app(root=root, journal=data / "receipts.sqlite3", origin=args.origin.rstrip("/"),
                           authorize=authorize, pairing_code=code)
    print("Rumi local executor. Only the selected workspace and Notepad/Explorer are available.")
    print("Pair within five minutes using the dashboard. Code (do not share): " + code, flush=True)
    print("Ctrl+C stops the agent. Emergency Stop requires restart and re-pairing.", flush=True)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False)


if __name__ == "__main__":
    main()
