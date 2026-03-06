import os
from firebase_admin import auth
from src.memory.firestore_client import get_db


class AuthError(Exception):
    pass


def verify_id_token(token: str) -> dict:
    """Verify a Firebase ID token and enforce the single-authorised-user policy.

    Returns the decoded token dict on success.
    Raises AuthError if the token is invalid or the UID is not authorised.
    """
    # Ensure firebase_admin app is initialised before verifying tokens
    get_db()
    try:
        decoded = auth.verify_id_token(token)
    except Exception as exc:
        raise AuthError(f"INVALID_TOKEN: {exc}") from exc

    authorised_uid = os.environ["AUTHORISED_USER_UID"]
    if decoded["uid"] != authorised_uid:
        raise AuthError("UNAUTHORISED_USER")

    return decoded
